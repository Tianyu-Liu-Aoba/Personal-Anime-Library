from __future__ import annotations

import json
import os
import socket
from copy import deepcopy
from pathlib import Path
from typing import Any


APP_NAME = "AnimeLibraryExpressive"
DEFAULT_PORT = 48321
DEFAULT_CONFIG: dict[str, Any] = {
    "library_paths": [],
    "appearance": {
        "theme_mode": "system",
        "accent": "sunrise",
        "font_body": '"Trebuchet MS", "Segoe UI", sans-serif',
        "font_display": '"Bahnschrift", "Segoe UI", sans-serif',
        "background_start": "#fff5ef",
        "background_end": "#fff0e6",
    },
    "providers": {
        "mal_client_id": "",
        "tmdb_api_key": "",
        "tmdb_read_access_token": "",
    },
}


def get_app_data_dir() -> Path:
    root = os.getenv("APPDATA")
    if root:
        base = Path(root)
    else:
        base = Path.cwd() / ".anime-library-data"
    app_dir = base / APP_NAME
    try:
        app_dir.mkdir(parents=True, exist_ok=True)
        (app_dir / "cache").mkdir(parents=True, exist_ok=True)
        (app_dir / "cache" / "posters").mkdir(parents=True, exist_ok=True)
        (app_dir / "cache" / "custom_covers").mkdir(parents=True, exist_ok=True)
        return app_dir
    except OSError:
        fallback = Path.cwd() / ".anime-library-data" / APP_NAME
        fallback.mkdir(parents=True, exist_ok=True)
        (fallback / "cache").mkdir(parents=True, exist_ok=True)
        (fallback / "cache" / "posters").mkdir(parents=True, exist_ok=True)
        (fallback / "cache" / "custom_covers").mkdir(parents=True, exist_ok=True)
        return fallback


def get_config_path() -> Path:
    return get_app_data_dir() / "config.json"


def get_catalog_path() -> Path:
    return get_app_data_dir() / "catalog.json"


def get_overrides_path() -> Path:
    return get_app_data_dir() / "overrides.json"


def get_poster_cache_dir() -> Path:
    return get_app_data_dir() / "cache" / "posters"


def get_custom_cover_dir() -> Path:
    return get_app_data_dir() / "cache" / "custom_covers"


def load_json_file(path: Path, default: Any) -> Any:
    if not path.exists():
        return deepcopy(default)
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def save_json_file(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)


def load_config() -> dict[str, Any]:
    config = deepcopy(DEFAULT_CONFIG)
    disk = load_json_file(get_config_path(), {})
    merge_dicts(config, disk)
    return config


def save_config(config: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(DEFAULT_CONFIG)
    merge_dicts(merged, config)
    dedupe_paths(merged)
    save_json_file(get_config_path(), merged)
    return merged


def load_catalog() -> dict[str, Any]:
    return load_json_file(get_catalog_path(), {"items": [], "last_scan_at": None})


def save_catalog(catalog: dict[str, Any]) -> None:
    save_json_file(get_catalog_path(), catalog)


def load_overrides() -> dict[str, Any]:
    return load_json_file(get_overrides_path(), {})


def save_overrides(overrides: dict[str, Any]) -> None:
    save_json_file(get_overrides_path(), overrides)


def merge_dicts(target: dict[str, Any], patch: dict[str, Any]) -> None:
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            merge_dicts(target[key], value)
        else:
            target[key] = value


def dedupe_paths(config: dict[str, Any]) -> None:
    seen: set[str] = set()
    cleaned: list[str] = []
    for raw in config.get("library_paths", []):
        path = str(Path(raw).expanduser())
        key = os.path.normcase(os.path.normpath(path))
        if key not in seen:
            seen.add(key)
            cleaned.append(path)
    config["library_paths"] = cleaned


def find_open_port(host: str = "127.0.0.1", preferred: int = DEFAULT_PORT) -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        if sock.connect_ex((host, preferred)) != 0:
            return preferred

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((host, 0))
        return int(sock.getsockname()[1])
