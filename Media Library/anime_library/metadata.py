from __future__ import annotations

import hashlib
from collections import Counter

from .config import get_poster_cache_dir
from .http_utils import HttpRequestError, fetch_bytes
from .logging_utils import get_logger
from .providers import BangumiProvider, MyAnimeListProvider, TmdbProvider
from .providers.base import BaseProvider, ProviderRecord
from .title_parser import normalize_for_match, unique_strings

logger = get_logger(__name__)


class MetadataResolver:
    def __init__(self, config: dict[str, object]) -> None:
        provider_config = config.get("providers", {}) if isinstance(config, dict) else {}
        if not isinstance(provider_config, dict):
            provider_config = {}
        self.providers: list[BaseProvider] = [
            MyAnimeListProvider(provider_config),
            TmdbProvider(provider_config),
            BangumiProvider(provider_config),
        ]
        self.providers_by_name = {provider.provider_name: provider for provider in self.providers}

    def availability(self) -> list[dict[str, object]]:
        return [provider.availability() for provider in self.providers]

    def resolve(
        self,
        folder_name: str,
        search_titles: list[str],
        year_hint: int | None,
        hints: dict[str, object] | None = None,
    ) -> dict[str, object]:
        manual_provider = str((hints or {}).get("manual_source_provider") or "").strip().lower()
        manual_source_id = str((hints or {}).get("manual_source_id") or "").strip()
        if manual_provider and manual_source_id:
            provider = self.providers_by_name.get(manual_provider)
            if provider:
                manual_record = provider.fetch_by_id(manual_source_id)
                if manual_record:
                    return metadata_from_locked_record(folder_name, year_hint, manual_record)

        records: dict[str, ProviderRecord] = {}
        for provider in self.providers:
            record = provider.resolve(search_titles, year_hint, hints)
            if record:
                records[provider.provider_name] = record
        if not records:
            logger.info("No metadata match for '%s'", folder_name)
        return aggregate_metadata(folder_name, search_titles, year_hint, records)

    def search_candidates(
        self,
        search_titles: list[str],
        year_hint: int | None,
        hints: dict[str, object] | None = None,
        limit: int = 12,
    ) -> list[dict[str, object]]:
        candidates: list[ProviderRecord] = []
        for provider in self.providers:
            candidates.extend(provider.score_candidates(search_titles, year_hint, hints))
        ranked = sorted(
            dedupe_candidate_records(candidates),
            key=lambda item: (
                1 if any(normalize_for_match(title) == normalize_for_match(item.title) for title in search_titles if title) else 0,
                item.score,
            ),
            reverse=True,
        )
        return [serialize_candidate(record) for record in ranked[:limit]]

    def apply_manual_source(
        self,
        folder_name: str,
        provider_name: str,
        source_id: str,
        search_titles: list[str],
        year_hint: int | None,
    ) -> dict[str, object] | None:
        provider = self.providers_by_name.get(provider_name)
        if not provider:
            return None
        record = provider.fetch_by_id(source_id)
        if not record:
            return None
        return metadata_from_locked_record(folder_name, year_hint, record)


def metadata_from_locked_record(
    folder_name: str,
    year_hint: int | None,
    record: ProviderRecord,
) -> dict[str, object]:
    resolved_title = record.title or (record.titles[0] if record.titles else folder_name)
    aliases = [
        alias
        for alias in unique_strings([*record.titles])
        if normalize_for_match(alias) != normalize_for_match(resolved_title)
    ]
    poster_url = record.poster_url
    poster_cached = cache_poster(poster_url) if poster_url else None
    notes = [f"Locked to the selected {record.provider} source."]
    if not any([record.overview.strip(), record.tags, record.producers, record.directors]):
        notes.append("This source returned limited metadata fields.")
    return {
        "resolved_title": resolved_title,
        "aliases": aliases,
        "year": record.year or year_hint,
        "overview": (record.overview or "").strip(),
        "poster_url": poster_url,
        "poster_cached": poster_cached,
        "tags": unique_strings(record.tags),
        "producers": unique_strings(record.producers),
        "directors": unique_strings(record.directors),
        "sources": {
            record.provider: {
                "title": record.title,
                "year": record.year,
                "url": record.url,
                "score": round(record.score, 3),
            }
        },
        "cross_check": {
            "provider_count": 1,
            "confidence": 1.0,
            "notes": notes,
        },
    }


def aggregate_metadata(
    folder_name: str,
    search_titles: list[str],
    year_hint: int | None,
    records: dict[str, ProviderRecord],
) -> dict[str, object]:
    record_list = list(records.values())
    resolved_title = choose_title(search_titles, record_list) or search_titles[0] or folder_name
    aliases = unique_strings(
        [
            *search_titles,
            *[title for record in record_list for title in record.titles],
        ]
    )
    year = choose_year(record_list, year_hint)
    overview = choose_overview(record_list)
    poster_url = choose_poster(record_list)
    poster_cached = cache_poster(poster_url) if poster_url else None
    tags = unique_strings([tag for record in record_list for tag in record.tags])
    producers = unique_strings([producer for record in record_list for producer in record.producers])
    directors = unique_strings([director for record in record_list for director in record.directors])
    confidence = calculate_confidence(record_list)

    return {
        "resolved_title": resolved_title,
        "aliases": [alias for alias in aliases if normalize_for_match(alias) != normalize_for_match(resolved_title)],
        "year": year,
        "overview": overview,
        "poster_url": poster_url,
        "poster_cached": poster_cached,
        "tags": tags,
        "producers": producers,
        "directors": directors,
        "sources": {
            record.provider: {
                "title": record.title,
                "year": record.year,
                "url": record.url,
                "score": round(record.score, 3),
            }
            for record in record_list
        },
        "cross_check": {
            "provider_count": len(record_list),
            "confidence": confidence,
            "notes": build_cross_check_notes(record_list),
        },
    }


def choose_title(search_titles: list[str], records: list[ProviderRecord]) -> str | None:
    if not records:
        return search_titles[0] if search_titles else None
    cjk_query = next((query for query in search_titles if contains_cjk(query)), None)
    if cjk_query:
        cjk_titles = []
        for record in records:
            cjk_titles.extend([title for title in record.titles if contains_cjk(title)])
        if cjk_titles:
            return cjk_titles[0]
    ranked = sorted(records, key=lambda item: item.score, reverse=True)
    return ranked[0].title


def choose_year(records: list[ProviderRecord], year_hint: int | None) -> int | None:
    years = [record.year for record in records if record.year]
    if not years:
        return year_hint
    counter = Counter(years)
    return counter.most_common(1)[0][0]


def choose_overview(records: list[ProviderRecord]) -> str:
    options = [record.overview.strip() for record in records if record.overview.strip()]
    if not options:
        return ""
    return max(options, key=len)


def choose_poster(records: list[ProviderRecord]) -> str | None:
    preference = {"tmdb": 0, "myanimelist": 1, "bangumi": 2}
    ranked = sorted(
        [record for record in records if record.poster_url],
        key=lambda item: (preference.get(item.provider, 9), -item.score),
    )
    return ranked[0].poster_url if ranked else None


def calculate_confidence(records: list[ProviderRecord]) -> float:
    if not records:
        return 0.0
    average = sum(record.score for record in records) / len(records)
    provider_bonus = min(len(records), 3) * 0.08
    return round(min(average + provider_bonus, 1.0), 3)


def build_cross_check_notes(records: list[ProviderRecord]) -> list[str]:
    if not records:
        return ["No online sources matched this folder confidently."]
    notes = []
    if len(records) == 1:
        notes.append("Matched one source. Add a TMDB key in Settings for a stronger cross-check.")
    else:
        notes.append(f"Cross-checked {len(records)} sources.")
    years = unique_strings([str(record.year) for record in records if record.year])
    if len(years) > 1:
        notes.append(f"Sources disagree on the year: {', '.join(years)}.")
    return notes


def contains_cjk(value: str) -> bool:
    return any("\u3040" <= char <= "\u9fff" for char in value)


def cache_poster(url: str) -> str | None:
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()
    extension = ".jpg"
    if "." in url.rsplit("/", 1)[-1]:
        suffix = "." + url.rsplit(".", 1)[-1].split("?", 1)[0][:5]
        if 2 <= len(suffix) <= 6:
            extension = suffix
    destination = get_poster_cache_dir() / f"{digest}{extension}"
    if destination.exists():
        return f"/posters/{destination.name}"
    try:
        payload = fetch_bytes(url, timeout=30)
        destination.write_bytes(payload)
        return f"/posters/{destination.name}"
    except (HttpRequestError, OSError):
        logger.warning("Poster cache failed for %s", url)
        return None


def dedupe_candidate_records(records: list[ProviderRecord]) -> list[ProviderRecord]:
    seen: dict[tuple[str, str], ProviderRecord] = {}
    for record in records:
        key = (record.provider, record.source_id)
        existing = seen.get(key)
        if not existing or record.score > existing.score:
            seen[key] = record
    return list(seen.values())


def serialize_candidate(record: ProviderRecord) -> dict[str, object]:
    return {
        "provider": record.provider,
        "source_id": record.source_id,
        "title": record.title,
        "titles": record.titles,
        "year": record.year,
        "overview": record.overview,
        "poster_url": record.poster_url,
        "tags": record.tags,
        "producers": record.producers,
        "directors": record.directors,
        "url": record.url,
        "score": round(record.score, 3),
    }
