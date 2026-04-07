from __future__ import annotations

import hashlib
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from .config import load_catalog, load_overrides, save_catalog
from .logging_utils import get_logger
from .metadata import MetadataResolver
from .title_parser import episode_sort_key, extract_episode_info, extract_title_candidates, unique_strings


VIDEO_EXTENSIONS = {".mkv", ".mp4", ".avi", ".m4v", ".wmv", ".flv", ".ts"}
SKIP_FOLDER_NAMES = {"$RECYCLE.BIN", "System Volume Information"}
ProgressCallback = Callable[[int, int, str], None]
logger = get_logger(__name__)


class LibraryScanner:
    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        self.metadata = MetadataResolver(config)

    def scan_all(self, refresh_metadata: bool = False, progress: ProgressCallback | None = None) -> dict[str, Any]:
        existing_catalog = load_catalog()
        overrides = load_overrides()
        existing_by_path = {
            item.get("folder_path"): item
            for item in existing_catalog.get("items", [])
            if item.get("folder_path")
        }

        issues: list[str] = []
        folders = collect_library_folders(self.config.get("library_paths", []), issues)
        total = len(folders)
        items: list[dict[str, Any]] = []

        for index, folder in enumerate(folders, start=1):
            if progress:
                progress(index, total, f"Scanning {folder.name}")
            existing = existing_by_path.get(str(folder))
            override = normalize_override_payload(overrides.get(str(folder), {}))
            try:
                item = self._scan_folder(folder, existing, refresh_metadata, issues, override)
                items.append(item)
            except Exception as error:  # noqa: BLE001
                message = f"Failed to scan folder '{folder}': {error}"
                issues.append(message)
                logger.exception(message)

        items.sort(key=lambda entry: (entry.get("resolved_title") or entry.get("folder_name") or "").lower())
        catalog = {
            "items": items,
            "last_scan_at": utc_now(),
            "issues": issues,
        }
        if issues:
            logger.warning("Scan finished with %s issue(s)", len(issues))
        save_catalog(catalog)
        return catalog

    def refresh_item(self, folder_path: str, refresh_metadata: bool = True) -> tuple[dict[str, Any], dict[str, Any]]:
        folder = Path(folder_path)
        if not folder.exists() or not folder.is_dir():
            raise FileNotFoundError(folder_path)

        catalog = load_catalog()
        overrides = load_overrides()
        issues = list(catalog.get("issues", []))
        existing_by_path = {
            item.get("folder_path"): item
            for item in catalog.get("items", [])
            if item.get("folder_path")
        }
        override = normalize_override_payload(overrides.get(str(folder), {}))
        item = self._scan_folder(folder, existing_by_path.get(str(folder)), refresh_metadata, issues, override)

        items: list[dict[str, Any]] = []
        replaced = False
        for existing in catalog.get("items", []):
            if existing.get("folder_path") == str(folder):
                items.append(item)
                replaced = True
            else:
                items.append(existing)
        if not replaced:
            items.append(item)
        items.sort(key=lambda entry: (entry.get("resolved_title") or entry.get("folder_name") or "").lower())
        updated_catalog = {
            "items": items,
            "last_scan_at": utc_now(),
            "issues": issues,
        }
        save_catalog(updated_catalog)
        return item, updated_catalog

    def _scan_folder(
        self,
        folder: Path,
        existing: dict[str, Any] | None,
        refresh_metadata: bool,
        issues: list[str],
        override: dict[str, Any],
    ) -> dict[str, Any]:
        title_info = extract_title_candidates(folder.name)
        search_titles = merge_search_titles(title_info, override)
        year_hint = override.get("year") or title_info["year_hint"]
        video_files, content_signature = collect_video_inventory(folder, issues)
        existing_override = normalize_override_payload(existing.get("user_override", {})) if existing else {}
        folder_name_changed = not existing or existing.get("folder_name") != folder.name
        override_changed = existing_override != override
        content_changed = not existing or existing.get("content_signature") != content_signature
        if existing and not refresh_metadata and not folder_name_changed and not override_changed and not content_changed:
            return existing

        episodes = build_episode_records(folder, video_files)
        should_refresh_metadata = refresh_metadata or not existing or folder_name_changed or override_changed
        user_override_present = bool(override)

        if should_refresh_metadata:
            if existing and user_override_present and not refresh_metadata:
                resolved = {
                    "resolved_title": existing.get("resolved_title") or title_info["cleaned_title"],
                    "aliases": existing.get("aliases", []),
                    "year": existing.get("year"),
                    "overview": existing.get("overview", ""),
                    "poster_url": existing.get("poster_url"),
                    "poster_cached": existing.get("poster_cached"),
                    "tags": existing.get("tags", []),
                    "producers": existing.get("producers", []),
                    "directors": existing.get("directors", []),
                    "sources": existing.get("sources", {}),
                    "cross_check": existing.get("cross_check", {"provider_count": 0, "confidence": 0.0, "notes": []}),
                }
            else:
                try:
                    resolved = self.metadata.resolve(folder.name, search_titles, year_hint, hints=override)
                except Exception as error:  # noqa: BLE001
                    issues.append(f"Metadata lookup failed for '{folder.name}': {error}")
                    logger.exception("Metadata lookup failed for %s", folder)
                    resolved = empty_resolved_metadata(title_info["cleaned_title"])
        else:
            resolved = {
                "resolved_title": existing.get("resolved_title") or title_info["cleaned_title"],
                "aliases": existing.get("aliases", []),
                "year": existing.get("year"),
                "overview": existing.get("overview", ""),
                "poster_url": existing.get("poster_url"),
                "poster_cached": existing.get("poster_cached"),
                "tags": existing.get("tags", []),
                "producers": existing.get("producers", []),
                "directors": existing.get("directors", []),
                "sources": existing.get("sources", {}),
                "cross_check": existing.get("cross_check", {"provider_count": 0, "confidence": 0.0, "notes": []}),
            }

        base_item = {
            "id": stable_item_id(folder),
            "folder_name": folder.name,
            "folder_path": str(folder),
            "content_signature": content_signature,
            "cleaned_title": title_info["cleaned_title"],
            "search_titles": search_titles,
            "resolved_title": resolved["resolved_title"],
            "aliases": resolved["aliases"],
            "year": resolved["year"],
            "overview": resolved["overview"],
            "poster_url": resolved["poster_url"],
            "poster_cached": resolved["poster_cached"],
            "tags": resolved["tags"],
            "producers": resolved["producers"],
            "directors": resolved["directors"],
            "sources": resolved["sources"],
            "cross_check": resolved["cross_check"],
            "episodes": episodes,
            "seasons": build_season_groups(episodes),
            "last_scanned_at": utc_now(),
        }
        overridden_item = apply_override_fields(base_item, override)
        overridden_item["user_override"] = override
        overridden_item["known_as"] = list(override.get("known_as", []))
        overridden_item["seasons"] = build_season_groups(overridden_item["episodes"])
        return overridden_item


def collect_library_folders(paths: list[str], issues: list[str]) -> list[Path]:
    folders: list[Path] = []
    for raw in paths:
        root = Path(raw)
        if not root.exists() or not root.is_dir():
            message = f"Library root is missing or not a folder: {root}"
            issues.append(message)
            logger.warning(message)
            continue
        try:
            child_dirs: list[Path] = []
            with os.scandir(root) as entries:
                for entry in entries:
                    try:
                        if entry.is_dir() and not should_skip_folder(entry.name):
                            child_dirs.append(Path(entry.path))
                    except OSError as error:
                        message = f"Could not inspect '{entry.path}': {error}"
                        issues.append(message)
                        logger.warning(message)
            folders.extend(sorted(child_dirs, key=lambda entry: entry.name.lower()))
        except OSError as error:
            message = f"Could not access library root '{root}': {error}"
            issues.append(message)
            logger.warning(message)
    return folders


def collect_video_inventory(folder: Path, issues: list[str]) -> tuple[list[Path], str]:
    video_files: list[Path] = []
    signature_parts = [f"folder:{folder.name}"]
    walk_error: OSError | None = None

    def on_error(error: OSError) -> None:
        nonlocal walk_error
        walk_error = error
        message = f"Could not read '{getattr(error, 'filename', folder)}': {error}"
        issues.append(message)
        logger.warning(message)

    for dirpath, _dirnames, filenames in os.walk(folder, onerror=on_error):
        for filename in filenames:
            path = Path(dirpath) / filename
            if path.suffix.lower() not in VIDEO_EXTENSIONS:
                continue
            video_files.append(path)
            try:
                stat = path.stat()
                relative = path.relative_to(folder).as_posix()
                signature_parts.append(f"{relative}|{stat.st_size}|{stat.st_mtime_ns}")
            except OSError as error:
                message = f"Could not inspect '{path}': {error}"
                issues.append(message)
                logger.warning(message)

    if walk_error:
        logger.info("Continuing with partial episode list for %s", folder)

    try:
        folder_stat = folder.stat()
        signature_parts.append(f"root:{folder_stat.st_mtime_ns}")
    except OSError:
        signature_parts.append("root:missing")

    digest = hashlib.sha1("\n".join(sorted(signature_parts)).encode("utf-8")).hexdigest()
    return video_files, digest


def scan_episodes(folder: Path, issues: list[str]) -> list[dict[str, Any]]:
    video_files, _content_signature = collect_video_inventory(folder, issues)
    return build_episode_records(folder, video_files)


def build_episode_records(folder: Path, video_files: list[Path]) -> list[dict[str, Any]]:
    video_files.sort(key=lambda path: episode_sort_key(str(path.relative_to(folder))))
    episodes = []
    fallback_positions: dict[str, int] = {}
    for path in video_files:
        relative = path.relative_to(folder)
        relative_path = relative.as_posix()
        episode_info = extract_episode_info(relative_path)
        season_number = int(episode_info["season_number"] or 1)
        group_key = str(episode_info["group_key"] or f"season-{season_number}")
        fallback_positions[group_key] = fallback_positions.get(group_key, 0) + 1
        episode_number = int(episode_info["episode_number"] or fallback_positions[group_key])
        episodes.append(
            {
                "id": hashlib.sha1(str(path).encode("utf-8")).hexdigest()[:16],
                "label": str(episode_info["label"] or f"Episode {episode_number:02d}"),
                "browse_label": f"Ep {episode_number:02d}" if episode_info["episode_number"] is not None else str(
                    episode_info["label"] or relative.stem
                ),
                "season_number": season_number,
                "episode_number": episode_number,
                "group_key": group_key,
                "group_label": str(episode_info["group_label"] or f"Season {season_number}"),
                "path": str(path),
                "relative_path": relative_path,
            }
        )
    return episodes


def stable_item_id(folder: Path) -> str:
    return hashlib.sha1(str(folder).encode("utf-8")).hexdigest()[:16]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def empty_resolved_metadata(title: str) -> dict[str, Any]:
    return {
        "resolved_title": title,
        "aliases": [],
        "year": None,
        "overview": "",
        "poster_url": None,
        "poster_cached": None,
        "tags": [],
        "producers": [],
        "directors": [],
        "sources": {},
        "cross_check": {
            "provider_count": 0,
            "confidence": 0.0,
            "notes": ["Metadata lookup failed for this item. See diagnostics for details."],
        },
    }


def should_skip_folder(name: str) -> bool:
    if name in SKIP_FOLDER_NAMES:
        return True
    if name.startswith(".") or name.startswith("$"):
        return True
    return False


def normalize_override_payload(payload: dict[str, Any] | None) -> dict[str, Any]:
    payload = payload or {}
    normalized: dict[str, Any] = {}

    for field in ("title", "overview"):
        value = str(payload.get(field, "")).strip()
        if value:
            normalized[field] = value

    custom_cover = str(payload.get("custom_cover", "")).strip()
    if custom_cover:
        normalized["custom_cover"] = custom_cover

    manual_provider = str(payload.get("manual_source_provider", "")).strip().lower()
    manual_source_id = str(payload.get("manual_source_id", "")).strip()
    if manual_provider and manual_source_id:
        normalized["manual_source_provider"] = manual_provider
        normalized["manual_source_id"] = manual_source_id

    year_value = payload.get("year")
    if year_value not in (None, ""):
        try:
            normalized["year"] = int(year_value)
        except (TypeError, ValueError):
            pass

    for field in ("known_as", "producers", "directors", "tags"):
        normalized_values = normalize_string_list(payload.get(field))
        if normalized_values:
            normalized[field] = normalized_values

    return normalized


def normalize_string_list(raw: Any) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, str):
        parts = re.split(r"[,\n;|]+", raw)
    elif isinstance(raw, list):
        parts = [str(item) for item in raw]
    else:
        return []
    return unique_strings([part.strip() for part in parts if str(part).strip()])


def merge_search_titles(title_info: dict[str, Any], override: dict[str, Any]) -> list[str]:
    merged = unique_strings(
        [
            override.get("title", ""),
            *override.get("known_as", []),
            *list(title_info["search_titles"]),
        ]
    )
    return merged or [str(title_info["cleaned_title"])]


def apply_override_fields(item: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(item)
    if override.get("title"):
        merged["resolved_title"] = override["title"]
    if override.get("year") is not None:
        merged["year"] = override["year"]
    if override.get("overview"):
        merged["overview"] = override["overview"]
    if "custom_cover" in override:
        merged["custom_cover"] = f"/custom-covers/{override['custom_cover']}" if override.get("custom_cover") else None
    else:
        merged["custom_cover"] = item.get("custom_cover")
    for field in ("producers", "directors", "tags"):
        if override.get(field):
            merged[field] = list(override[field])

    merged["aliases"] = unique_strings(
        [
            *override.get("known_as", []),
            *merged.get("aliases", []),
        ]
    )
    return merged


def build_season_groups(episodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not episodes:
        return []

    grouped: dict[str, dict[str, Any]] = {}
    for episode in episodes:
        season_number = int(episode.get("season_number") or 1)
        group_key = str(episode.get("group_key") or f"season-{season_number}")
        bucket = grouped.setdefault(
            group_key,
            {
                "key": group_key,
                "label": episode.get("group_label") or f"Season {season_number}",
                "season_number": season_number,
                "episodes": [],
            },
        )
        bucket["episodes"].append(episode)

    multiple_groups = len(grouped) > 1
    seasons: list[dict[str, Any]] = []
    for bucket in sorted(grouped.values(), key=season_group_sort_key):
        season_episodes = sorted(
            bucket["episodes"],
            key=lambda entry: (
                int(entry.get("episode_number") or 9999),
                str(entry.get("relative_path") or ""),
            ),
        )
        seasons.append(
            {
                "key": bucket["key"],
                "season_number": bucket["season_number"],
                "label": bucket["label"] if multiple_groups else (bucket["label"] or "Episodes"),
                "episodes": season_episodes,
            }
        )
    return seasons


def season_group_sort_key(group: dict[str, Any]) -> tuple[int, int, str]:
    label = str(group.get("label") or "")
    normalized = label.lower()
    season_number = int(group.get("season_number") or 1)
    if normalized.startswith("season "):
        return (0, season_number, normalized)
    if "special" in normalized or normalized.startswith("sp"):
        return (1, season_number, normalized)
    return (2, season_number, normalized)
