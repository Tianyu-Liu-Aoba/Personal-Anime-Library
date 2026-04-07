from __future__ import annotations

import re
from difflib import SequenceMatcher
from pathlib import Path


BRACKETED_SEGMENTS = [
    (r"\[[^\]]*\]", " "),
    (r"\([^)]*\)", " "),
    (r"【[^】]*】", " "),
    (r"（[^）]*）", " "),
    (r"<[^>]*>", " "),
]
VIDEO_TOKEN_PATTERN = re.compile(
    r"\b(?:ma10p|10bit|2160p|1080p|720p|4k|x264|x265|hevc|aac|flac|bdrip|bluray|web-dl|remux|mkv|mp4|avi|m4v|wmv|flv)\b",
    re.IGNORECASE,
)
VIDEO_NOISE_TOKENS = (
    "ma10p",
    "10bit",
    "2160p",
    "1080p",
    "720p",
    "4k",
    "x264",
    "x265",
    "hevc",
    "aac",
    "flac",
    "bdrip",
    "bluray",
    "web-dl",
    "remux",
    "mkv",
    "mp4",
    "avi",
    "m4v",
    "wmv",
    "flv",
)
YEAR_PATTERN = re.compile(r"(?<!\d)(19\d{2}|20\d{2})(?!\d)")
EPISODE_HINT_PATTERN = re.compile(
    r"(?:^|[\s._\-\[\(【])(?:ep?|episode|ova|oad|special|sp|第)\s*([0-9]{1,3})(?:話|集)?",
    re.IGNORECASE,
)
SEASON_IN_FILE_PATTERN = re.compile(r"\bs(?:eason)?\s*0*([0-9]{1,2})\s*[-_. ]*e(?:pisode)?\s*0*([0-9]{1,3})\b", re.IGNORECASE)
SEASON_ALT_FILE_PATTERN = re.compile(r"\b([0-9]{1,2})x([0-9]{1,3})\b", re.IGNORECASE)
BRACKET_CONTENT_PATTERN = re.compile(r"[\[\(【（]([^\]\)】）]+)[\]\)】）]")
SEASON_FOLDER_PATTERNS = [
    re.compile(r"\bseason\s*0*([0-9]{1,2})\b", re.IGNORECASE),
    re.compile(r"\b([0-9]{1,2})(?:st|nd|rd|th)\s+season\b", re.IGNORECASE),
    re.compile(r"\bs0*([0-9]{1,2})\b", re.IGNORECASE),
    re.compile(r"第\s*([0-9]{1,2})\s*[季期部]", re.IGNORECASE),
]
SPECIAL_GROUP_PATTERNS = [
    re.compile(r"\bsp(?:ecial)?s?\b", re.IGNORECASE),
    re.compile(r"\bspecials?\b", re.IGNORECASE),
    re.compile(r"\bova\b", re.IGNORECASE),
    re.compile(r"\boad\b", re.IGNORECASE),
    re.compile(r"\bextras?\b", re.IGNORECASE),
]
NOISE_NUMBERS = {360, 480, 540, 576, 720, 900, 960, 1080, 1440, 2160, 265, 264}


def clean_folder_title(name: str) -> str:
    value = name
    for pattern, replacement in BRACKETED_SEGMENTS:
        value = re.sub(pattern, replacement, value)
    value = value.replace("\\", " ").replace("/", " ")
    value = value.replace("_", " ").replace(".", " ")
    value = VIDEO_TOKEN_PATTERN.sub(" ", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip(" -_./")


def split_title_variants(cleaned: str) -> list[str]:
    if not cleaned:
        return []
    parts = [cleaned]
    parts.extend(re.split(r"\s+[|/／]+\s+|\s+\+\s+|\s+;\s+", cleaned))
    expanded = []
    for part in parts:
        expanded.extend(expand_ampersand_title(part))
    return unique_strings([text for text in expanded if text and len(text) > 1])


def expand_ampersand_title(value: str) -> list[str]:
    if "&" not in value and "＆" not in value:
        return [value.strip()]
    tokens = [token.strip() for token in re.split(r"[&＆]", value) if token.strip()]
    if len(tokens) <= 1:
        return [value.strip()]
    first = tokens[0]
    prefix = infer_shared_prefix(first)
    variants = [first]
    for token in tokens[1:]:
        if prefix and not token.startswith(prefix):
            variants.append(f"{prefix}{token}")
        else:
            variants.append(token)
    variants.append(value.strip())
    return unique_strings(variants)


def infer_shared_prefix(first: str) -> str:
    separators = ["的", "之", ":", "：", "-", " ", "·", "・"]
    best = ""
    for separator in separators:
        index = first.rfind(separator)
        if index > 0:
            prefix = first[: index + 1].strip()
            if len(prefix) >= 2:
                best = prefix
                break
    return best


def extract_year_hint(value: str) -> int | None:
    match = YEAR_PATTERN.search(value)
    if not match:
        return None
    return int(match.group(1))


def normalize_for_match(value: str) -> str:
    cleaned = clean_folder_title(value).lower()
    cleaned = re.sub(r"[^0-9a-z\u3040-\u30ff\u3400-\u9fff]+", "", cleaned)
    return cleaned


def title_similarity(left: str, right: str) -> float:
    if not left or not right:
        return 0.0
    left_norm = normalize_for_match(left)
    right_norm = normalize_for_match(right)
    if not left_norm or not right_norm:
        return 0.0
    if left_norm == right_norm:
        return 1.0
    if left_norm in right_norm or right_norm in left_norm:
        return 0.92
    return SequenceMatcher(a=left_norm, b=right_norm).ratio()


def best_title_similarity(queries: list[str], candidates: list[str]) -> float:
    best = 0.0
    for query in queries:
        for candidate in candidates:
            best = max(best, title_similarity(query, candidate))
    return best


def unique_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for value in values:
        trimmed = str(value or "").strip()
        if not trimmed:
            continue
        key = normalize_for_match(trimmed)
        if key and key not in seen:
            seen.add(key)
            unique.append(trimmed)
    return unique


def extract_title_candidates(folder_name: str) -> dict[str, object]:
    cleaned = clean_folder_title(folder_name)
    candidates = split_title_variants(cleaned)
    if cleaned and cleaned not in candidates:
        candidates.insert(0, cleaned)
    return {
        "cleaned_title": cleaned or folder_name,
        "search_titles": unique_strings(candidates or [folder_name]),
        "year_hint": extract_year_hint(folder_name),
    }


def episode_sort_key(path_name: str) -> tuple[int, int, str]:
    info = extract_episode_info(path_name)
    return (
        0 if info["episode_number"] is not None else 1,
        int(info["season_number"] or 1),
        int(info["episode_number"] or 9999),
        str(path_name).lower(),
    )


def format_episode_label(file_stem: str) -> str:
    info = extract_episode_info(file_stem)
    return info["label"]


def extract_episode_info(path_name: str) -> dict[str, object]:
    season_number, episode_number = extract_season_episode_pair(path_name)
    if season_number is None:
        season_number = extract_season_number(path_name)
    group = extract_episode_group(path_name, season_number)
    if episode_number is None:
        episode_number = extract_episode_number(path_name)
    cleaned = clean_folder_title(Path(path_name).stem)
    if episode_number is not None:
        label = f"Episode {episode_number:02d}"
    else:
        label = cleaned or path_name
    return {
        "season_number": season_number,
        "episode_number": episode_number,
        "label": label,
        "group_key": group["key"],
        "group_label": group["label"],
    }


def extract_season_episode_pair(path_name: str) -> tuple[int | None, int | None]:
    lowered = path_name.lower()
    match = SEASON_IN_FILE_PATTERN.search(lowered)
    if match:
        return int(match.group(1)), int(match.group(2))
    match = SEASON_ALT_FILE_PATTERN.search(lowered)
    if match:
        return int(match.group(1)), int(match.group(2))
    return None, None


def extract_season_number(path_name: str) -> int | None:
    for pattern in SEASON_FOLDER_PATTERNS:
        match = pattern.search(path_name)
        if match:
            return int(match.group(1))
    return None


def extract_episode_number(path_name: str) -> int | None:
    raw_name = Path(path_name).stem
    match = EPISODE_HINT_PATTERN.search(raw_name)
    if match:
        return int(match.group(1))
    bracket_number = extract_episode_number_from_brackets(raw_name)
    if bracket_number is not None:
        return bracket_number
    trailing_number = extract_trailing_episode_number(raw_name)
    if trailing_number is not None:
        return trailing_number
    return None


def extract_episode_group(path_name: str, season_number: int | None = None) -> dict[str, object]:
    relative = Path(path_name)
    folder_parts = [part for part in relative.parts[:-1] if part.strip()]
    group_source = folder_parts[0] if folder_parts else ""
    if group_source:
        label = classify_episode_group(group_source, season_number)
        return {
            "key": normalize_for_match(label) or label.lower(),
            "label": label,
        }
    if looks_like_special_group(relative.stem):
        return {"key": "specials", "label": "Specials"}
    if season_number is not None:
        return {"key": f"season-{season_number}", "label": f"Season {season_number}"}
    return {"key": "episodes", "label": "Episodes"}


def classify_episode_group(value: str, season_number: int | None = None) -> str:
    cleaned = clean_folder_title(value) or value.strip()
    if looks_like_special_group(value):
        if normalize_for_match(cleaned) in {"sp", "sps"}:
            return "SPs"
        return cleaned or "Specials"
    if season_number is None:
        season_number = extract_season_number(value)
    if season_number is not None:
        return f"Season {season_number}"
    return cleaned


def looks_like_special_group(value: str) -> bool:
    return any(pattern.search(value) for pattern in SPECIAL_GROUP_PATTERNS)


def extract_episode_number_from_brackets(file_stem: str) -> int | None:
    for chunk in reversed(BRACKET_CONTENT_PATTERN.findall(file_stem)):
        candidate = extract_candidate_number(chunk)
        if candidate is not None:
            return candidate
    return None


def extract_trailing_episode_number(file_stem: str) -> int | None:
    return extract_candidate_number(file_stem)


def extract_candidate_number(text: str) -> int | None:
    lowered = text.lower()
    if any(token in lowered for token in VIDEO_NOISE_TOKENS):
        return None
    explicit = EPISODE_HINT_PATTERN.search(text)
    if explicit:
        return int(explicit.group(1))
    candidates = [int(value) for value in re.findall(r"(?<!\d)(\d{1,3})(?!\d)", text)]
    filtered = [value for value in candidates if value not in NOISE_NUMBERS and value < 200]
    return filtered[-1] if filtered else None
