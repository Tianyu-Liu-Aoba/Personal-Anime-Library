from __future__ import annotations

import json
import hashlib
import mimetypes
import re
import shutil
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from .config import (
    get_custom_cover_dir,
    get_poster_cache_dir,
    load_catalog,
    load_config,
    load_overrides,
    save_catalog,
    save_config,
    save_overrides,
)
from .logging_utils import get_log_path, get_logger, read_recent_log_lines, setup_logging
from .metadata import MetadataResolver
from .scanner import (
    LibraryScanner,
    apply_override_fields,
    build_season_groups,
    merge_search_titles,
    normalize_override_payload,
    normalize_string_list,
)
from .title_parser import extract_title_candidates
from .windows import choose_directory, choose_image_file, open_default_player


STATIC_DIR = Path(__file__).parent / "static"
logger = get_logger(__name__)
BANGUMI_SUBJECT_PATTERN = re.compile(r"(?:bangumi\.tv|bgm\.tv|chii\.in)/subject/(\d+)", re.IGNORECASE)


@dataclass
class ScanState:
    running: bool = False
    current: int = 0
    total: int = 0
    message: str = "Idle"
    error: str | None = None
    last_started_at: str | None = None
    last_finished_at: str | None = None
    thread: threading.Thread | None = field(default=None, repr=False)


class AppContext:
    def __init__(self) -> None:
        setup_logging()
        self.lock = threading.Lock()
        self.scan_state = ScanState()

    def get_bootstrap(self) -> dict[str, Any]:
        config = load_config()
        catalog = load_catalog()
        resolver = MetadataResolver(config)
        return {
            "config": config,
            "catalog": catalog,
            "needs_setup": not config.get("library_paths"),
            "source_availability": resolver.availability(),
            "scan_status": self.scan_status(),
            "log_path": str(get_log_path()),
        }

    def save_settings(self, payload: dict[str, Any]) -> dict[str, Any]:
        config = load_config()
        config["library_paths"] = payload.get("library_paths", config.get("library_paths", []))
        appearance = config.setdefault("appearance", {})
        appearance["theme_mode"] = payload.get("theme_mode", appearance.get("theme_mode", "system"))
        appearance["accent"] = payload.get("accent", appearance.get("accent", "sunrise"))
        appearance["font_body"] = payload.get("font_body", appearance.get("font_body", '"Trebuchet MS", "Segoe UI", sans-serif'))
        appearance["font_display"] = payload.get(
            "font_display",
            appearance.get("font_display", '"Bahnschrift", "Segoe UI", sans-serif'),
        )
        appearance["background_start"] = payload.get(
            "background_start",
            appearance.get("background_start", "#fff5ef"),
        )
        appearance["background_end"] = payload.get(
            "background_end",
            appearance.get("background_end", "#fff0e6"),
        )
        providers = config.setdefault("providers", {})
        providers["mal_client_id"] = payload.get("mal_client_id", providers.get("mal_client_id", ""))
        providers["tmdb_api_key"] = payload.get("tmdb_api_key", providers.get("tmdb_api_key", ""))
        providers["tmdb_read_access_token"] = payload.get(
            "tmdb_read_access_token",
            providers.get("tmdb_read_access_token", ""),
        )
        saved = save_config(config)
        logger.info("Settings saved. Library roots: %s", len(saved.get("library_paths", [])))
        return saved

    def save_item_override(self, item_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        payload_copy = dict(payload)
        refresh_metadata = bool(payload_copy.pop("refresh_metadata", False))
        reset_override = bool(payload_copy.pop("reset_override", False))
        reset_fields = bool(payload_copy.pop("reset_fields", False))
        catalog = load_catalog()
        item = next((entry for entry in catalog.get("items", []) if entry.get("id") == item_id), None)
        if not item:
            raise KeyError(item_id)

        folder_path = str(item.get("folder_path"))
        overrides = load_overrides()
        existing_override = normalize_override_payload(overrides.get(folder_path, {}))
        if reset_override:
            override = {}
        elif reset_fields:
            override = {
                field: existing_override[field]
                for field in ("custom_cover", "manual_source_provider", "manual_source_id")
                if existing_override.get(field)
            }
        else:
            override = dict(existing_override)
            if "title" in payload_copy:
                title_value = str(payload_copy.get("title") or "").strip()
                if title_value:
                    override["title"] = title_value
                else:
                    override.pop("title", None)
            if "overview" in payload_copy:
                overview_value = str(payload_copy.get("overview") or "").strip()
                if overview_value:
                    override["overview"] = overview_value
                else:
                    override.pop("overview", None)
            if "year" in payload_copy:
                year_value = payload_copy.get("year")
                if year_value in (None, ""):
                    override.pop("year", None)
                else:
                    try:
                        override["year"] = int(year_value)
                    except (TypeError, ValueError):
                        override.pop("year", None)
            for field in ("known_as", "producers", "directors", "tags"):
                if field in payload_copy:
                    normalized_values = normalize_string_list(payload_copy.get(field))
                    if normalized_values:
                        override[field] = normalized_values
                    else:
                        override.pop(field, None)
        if override:
            overrides[folder_path] = override
        else:
            overrides.pop(folder_path, None)
        save_overrides(overrides)
        logger.info(
            "Saved override for %s refresh_metadata=%s reset_override=%s reset_fields=%s",
            folder_path,
            refresh_metadata,
            reset_override,
            reset_fields,
        )

        if reset_override or reset_fields:
            scanner = LibraryScanner(load_config())
            refreshed_item, updated_catalog = scanner.refresh_item(folder_path, refresh_metadata=True)
            return {"item": refreshed_item, "catalog": updated_catalog}

        if refresh_metadata:
            scanner = LibraryScanner(load_config())
            refreshed_item, updated_catalog = scanner.refresh_item(folder_path, refresh_metadata=True)
            return {"item": refreshed_item, "catalog": updated_catalog}

        updated_item = self._apply_override_without_refresh(item, override)
        items = []
        for existing in catalog.get("items", []):
            if existing.get("id") == item_id:
                items.append(updated_item)
            else:
                items.append(existing)
        items.sort(key=lambda entry: (entry.get("resolved_title") or entry.get("folder_name") or "").lower())
        updated_catalog = {
            "items": items,
            "last_scan_at": catalog.get("last_scan_at"),
            "issues": catalog.get("issues", []),
        }
        save_catalog(updated_catalog)
        return {"item": updated_item, "catalog": updated_catalog}

    def save_item_custom_cover(self, item_id: str, source_path: str) -> dict[str, Any]:
        catalog = load_catalog()
        item = next((entry for entry in catalog.get("items", []) if entry.get("id") == item_id), None)
        if not item:
            raise KeyError(item_id)

        folder_path = str(item.get("folder_path"))
        stored_name = store_custom_cover(Path(source_path))
        overrides = load_overrides()
        override = normalize_override_payload(overrides.get(folder_path, {}))
        override["custom_cover"] = stored_name
        overrides[folder_path] = override
        save_overrides(overrides)
        logger.info("Saved custom cover for %s from %s", folder_path, source_path)
        return self._update_item_in_catalog(item_id, item, override, catalog)

    def clear_item_custom_cover(self, item_id: str) -> dict[str, Any]:
        catalog = load_catalog()
        item = next((entry for entry in catalog.get("items", []) if entry.get("id") == item_id), None)
        if not item:
            raise KeyError(item_id)

        folder_path = str(item.get("folder_path"))
        overrides = load_overrides()
        override = normalize_override_payload(overrides.get(folder_path, {}))
        override.pop("custom_cover", None)
        if override:
            overrides[folder_path] = override
        else:
            overrides.pop(folder_path, None)
        save_overrides(overrides)
        logger.info("Cleared custom cover for %s", folder_path)
        display_override = dict(override)
        display_override["custom_cover"] = ""
        return self._update_item_in_catalog(item_id, item, override, catalog, display_override=display_override)

    def metadata_candidates(self, item_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        catalog = load_catalog()
        item = next((entry for entry in catalog.get("items", []) if entry.get("id") == item_id), None)
        if not item:
            raise KeyError(item_id)
        hints, search_titles, year_hint = self._build_item_search_context(item, payload)
        resolver = MetadataResolver(load_config())
        return {
            "candidates": resolver.search_candidates(search_titles, year_hint, hints=hints, limit=18),
        }

    def apply_manual_metadata_source(self, item_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        catalog = load_catalog()
        item = next((entry for entry in catalog.get("items", []) if entry.get("id") == item_id), None)
        if not item:
            raise KeyError(item_id)

        provider_name = str(payload.get("provider") or "").strip().lower()
        source_id = str(payload.get("source_id") or "").strip()
        if not provider_name or not source_id:
            source_id = parse_bangumi_subject_id(str(payload.get("bangumi_url") or "").strip())
            provider_name = "bangumi" if source_id else provider_name
        if not provider_name or not source_id:
            raise ValueError("Choose a metadata match or paste a valid Bangumi subject URL.")

        folder_path = str(item.get("folder_path"))
        overrides = load_overrides()
        existing_override = normalize_override_payload(overrides.get(folder_path, {}))
        override: dict[str, Any] = {}
        if existing_override.get("custom_cover"):
            override["custom_cover"] = existing_override["custom_cover"]
        override["manual_source_provider"] = provider_name
        override["manual_source_id"] = source_id
        overrides[folder_path] = override
        save_overrides(overrides)
        logger.info("Applied manual metadata source for %s: %s %s", folder_path, provider_name, source_id)

        scanner = LibraryScanner(load_config())
        refreshed_item, updated_catalog = scanner.refresh_item(folder_path, refresh_metadata=True)
        return {"item": refreshed_item, "catalog": updated_catalog}

    def _update_item_in_catalog(
        self,
        item_id: str,
        current_item: dict[str, Any],
        override: dict[str, Any],
        catalog: dict[str, Any],
        display_override: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        updated_item = self._apply_override_without_refresh(current_item, display_override if display_override is not None else override)
        updated_item["user_override"] = override
        updated_item["known_as"] = list(override.get("known_as", []))
        items = []
        for existing in catalog.get("items", []):
            if existing.get("id") == item_id:
                items.append(updated_item)
            else:
                items.append(existing)
        items.sort(key=lambda entry: (entry.get("resolved_title") or entry.get("folder_name") or "").lower())
        updated_catalog = {
            "items": items,
            "last_scan_at": catalog.get("last_scan_at"),
            "issues": catalog.get("issues", []),
        }
        save_catalog(updated_catalog)
        return {"item": updated_item, "catalog": updated_catalog}

    def _apply_override_without_refresh(self, item: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
        updated = apply_override_fields(item, override)
        updated["user_override"] = override
        updated["known_as"] = list(override.get("known_as", []))
        updated["seasons"] = build_season_groups(updated.get("episodes", []))
        return updated

    def _build_item_search_context(self, item: dict[str, Any], payload: dict[str, Any]) -> tuple[dict[str, Any], list[str], int | None]:
        title_info = extract_title_candidates(str(item.get("folder_name") or item.get("resolved_title") or ""))
        existing_override = normalize_override_payload(item.get("user_override", {}))
        incoming_override = normalize_override_payload(payload)
        hints = dict(existing_override)
        hints.update(incoming_override)
        search_titles = merge_search_titles(title_info, hints)
        year_hint = hints.get("year") or title_info.get("year_hint")
        return hints, search_titles, int(year_hint) if isinstance(year_hint, int) else None

    def scan_status(self) -> dict[str, Any]:
        with self.lock:
            return {
                "running": self.scan_state.running,
                "current": self.scan_state.current,
                "total": self.scan_state.total,
                "message": self.scan_state.message,
                "error": self.scan_state.error,
                "last_started_at": self.scan_state.last_started_at,
                "last_finished_at": self.scan_state.last_finished_at,
            }

    def start_scan(self, refresh_metadata: bool = False) -> dict[str, Any]:
        with self.lock:
            if self.scan_state.running:
                return {
                    "running": self.scan_state.running,
                    "current": self.scan_state.current,
                    "total": self.scan_state.total,
                    "message": self.scan_state.message,
                    "error": self.scan_state.error,
                    "last_started_at": self.scan_state.last_started_at,
                    "last_finished_at": self.scan_state.last_finished_at,
                }
            self.scan_state = ScanState(
                running=True,
                current=0,
                total=0,
                message="Preparing scan",
                error=None,
                last_started_at=datetime.now(timezone.utc).isoformat(),
                last_finished_at=None,
            )
            thread = threading.Thread(
                target=self._run_scan,
                kwargs={"refresh_metadata": refresh_metadata},
                daemon=True,
            )
            self.scan_state.thread = thread
            thread.start()
            return {
                "running": self.scan_state.running,
                "current": self.scan_state.current,
                "total": self.scan_state.total,
                "message": self.scan_state.message,
                "error": self.scan_state.error,
                "last_started_at": self.scan_state.last_started_at,
                "last_finished_at": self.scan_state.last_finished_at,
            }

    def _run_scan(self, refresh_metadata: bool) -> None:
        config = load_config()
        scanner = LibraryScanner(config)

        def on_progress(current: int, total: int, message: str) -> None:
            with self.lock:
                self.scan_state.current = current
                self.scan_state.total = total
                self.scan_state.message = message

        try:
            logger.info("Starting library scan. refresh_metadata=%s", refresh_metadata)
            catalog = scanner.scan_all(refresh_metadata=refresh_metadata, progress=on_progress)
            with self.lock:
                self.scan_state.running = False
                self.scan_state.current = self.scan_state.total
                self.scan_state.message = "Scan complete"
                self.scan_state.last_finished_at = catalog.get("last_scan_at")
                self.scan_state.error = None
            logger.info(
                "Scan complete. items=%s issues=%s",
                len(catalog.get("items", [])),
                len(catalog.get("issues", [])),
            )
        except Exception as error:  # noqa: BLE001
            logger.exception("Scan failed")
            with self.lock:
                self.scan_state.running = False
                self.scan_state.error = str(error)
                self.scan_state.message = "Scan failed"
        finally:
            with self.lock:
                self.scan_state.thread = None


class AppHandler(SimpleHTTPRequestHandler):
    server_version = "AnimeLibraryExpressive/1.0"

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/"):
            self.handle_api_get(parsed.path, parse_qs(parsed.query))
            return
        self.handle_static(parsed.path)

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if not parsed.path.startswith("/api/"):
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        content_length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(content_length) if content_length else b"{}"
        try:
            payload = json.loads(raw_body.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            payload = {}
        self.handle_api_post(parsed.path, payload)

    @property
    def app(self) -> AppContext:
        return self.server.app_context  # type: ignore[attr-defined]

    def handle_api_get(self, path: str, query: dict[str, list[str]]) -> None:
        if path == "/api/bootstrap":
            self.respond_json(self.app.get_bootstrap())
            return
        if path == "/api/library":
            self.respond_json(load_catalog())
            return
        if path == "/api/scan/status":
            self.respond_json(self.app.scan_status())
            return
        if path == "/api/settings":
            self.respond_json(
                {
                    "config": load_config(),
                    "scan_status": self.app.scan_status(),
                    "logs": read_recent_log_lines(120),
                }
            )
            return
        if path == "/api/logs":
            requested = query.get("limit", ["120"])[0]
            try:
                limit = max(20, min(int(requested), 400))
            except ValueError:
                limit = 120
            self.respond_json(read_recent_log_lines(limit))
            return
        if path.startswith("/api/library/"):
            item_id = path.rsplit("/", 1)[-1]
            catalog = load_catalog()
            item = next((entry for entry in catalog.get("items", []) if entry.get("id") == item_id), None)
            if not item:
                self.respond_json({"error": "Not found"}, status=HTTPStatus.NOT_FOUND)
                return
            self.respond_json(item)
            return
        self.respond_json({"error": "Not found"}, status=HTTPStatus.NOT_FOUND)

    def handle_api_post(self, path: str, payload: dict[str, Any]) -> None:
        if path == "/api/system/select-folder":
            selected = choose_directory(payload.get("title") or "Choose an anime library folder")
            self.respond_json({"path": selected})
            return
        if path == "/api/system/select-image":
            selected = choose_image_file(payload.get("title") or "Choose a custom cover image")
            self.respond_json({"path": selected})
            return
        if path == "/api/settings/save":
            saved = self.app.save_settings(payload)
            should_scan = payload.get("scan_after_save", True)
            if should_scan and saved.get("library_paths"):
                self.app.start_scan(refresh_metadata=bool(payload.get("refresh_metadata")))
            self.respond_json({"config": saved, "scan_status": self.app.scan_status()})
            return
        if path == "/api/scan/start":
            state = self.app.start_scan(refresh_metadata=bool(payload.get("refresh_metadata")))
            self.respond_json(state)
            return
        if path == "/api/play":
            target = payload.get("path")
            if not target:
                self.respond_json({"error": "Missing path"}, status=HTTPStatus.BAD_REQUEST)
                return
            try:
                open_default_player(target)
            except FileNotFoundError:
                self.respond_json({"error": "File does not exist"}, status=HTTPStatus.NOT_FOUND)
                return
            logger.info("Opening media file: %s", target)
            self.respond_json({"ok": True})
            return
        if path.startswith("/api/library/") and path.endswith("/override"):
            item_id = path.removeprefix("/api/library/").removesuffix("/override").strip("/")
            try:
                result = self.app.save_item_override(item_id, payload)
            except KeyError:
                self.respond_json({"error": "Not found"}, status=HTTPStatus.NOT_FOUND)
                return
            except FileNotFoundError:
                self.respond_json({"error": "Folder no longer exists"}, status=HTTPStatus.NOT_FOUND)
                return
            self.respond_json(result)
            return
        if path.startswith("/api/library/") and path.endswith("/metadata/candidates"):
            item_id = path.removeprefix("/api/library/").removesuffix("/metadata/candidates").strip("/")
            try:
                result = self.app.metadata_candidates(item_id, payload)
            except KeyError:
                self.respond_json({"error": "Not found"}, status=HTTPStatus.NOT_FOUND)
                return
            self.respond_json(result)
            return
        if path.startswith("/api/library/") and path.endswith("/metadata/apply-source"):
            item_id = path.removeprefix("/api/library/").removesuffix("/metadata/apply-source").strip("/")
            try:
                result = self.app.apply_manual_metadata_source(item_id, payload)
            except KeyError:
                self.respond_json({"error": "Not found"}, status=HTTPStatus.NOT_FOUND)
                return
            except ValueError as error:
                self.respond_json({"error": str(error)}, status=HTTPStatus.BAD_REQUEST)
                return
            self.respond_json(result)
            return
        if path.startswith("/api/library/") and path.endswith("/cover/select"):
            item_id = path.removeprefix("/api/library/").removesuffix("/cover/select").strip("/")
            selected = choose_image_file("Choose a custom cover image")
            if not selected:
                self.respond_json({"cancelled": True})
                return
            try:
                result = self.app.save_item_custom_cover(item_id, selected)
            except KeyError:
                self.respond_json({"error": "Not found"}, status=HTTPStatus.NOT_FOUND)
                return
            except FileNotFoundError:
                self.respond_json({"error": "Image file no longer exists"}, status=HTTPStatus.NOT_FOUND)
                return
            except OSError as error:
                self.respond_json({"error": str(error)}, status=HTTPStatus.BAD_REQUEST)
                return
            self.respond_json(result)
            return
        if path.startswith("/api/library/") and path.endswith("/cover/clear"):
            item_id = path.removeprefix("/api/library/").removesuffix("/cover/clear").strip("/")
            try:
                result = self.app.clear_item_custom_cover(item_id)
            except KeyError:
                self.respond_json({"error": "Not found"}, status=HTTPStatus.NOT_FOUND)
                return
            self.respond_json(result)
            return
        self.respond_json({"error": "Not found"}, status=HTTPStatus.NOT_FOUND)

    def handle_static(self, path: str) -> None:
        if path.startswith("/posters/"):
            self.serve_file((get_poster_cache_dir() / path.rsplit("/", 1)[-1]).resolve())
            return
        if path.startswith("/custom-covers/"):
            self.serve_file((get_custom_cover_dir() / path.rsplit("/", 1)[-1]).resolve())
            return
        requested = path.lstrip("/") or "index.html"
        if requested == "settings":
            requested = "settings.html"
        elif requested == "index":
            requested = "index.html"
        self.serve_file((STATIC_DIR / requested).resolve(), root=STATIC_DIR.resolve())

    def serve_file(self, target: Path, root: Path | None = None) -> None:
        if root is None:
            root = target.parent
        if not str(target).startswith(str(root)) or not target.exists() or target.is_dir():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        content_type, _ = mimetypes.guess_type(target.name)
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type or "application/octet-stream")
        self.send_header("Cache-Control", "no-store, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        self.end_headers()
        self.wfile.write(target.read_bytes())

    def respond_json(self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
        return


class AnimeLibraryServer(ThreadingHTTPServer):
    def __init__(self, server_address: tuple[str, int], handler: type[AppHandler], app_context: AppContext) -> None:
        super().__init__(server_address, handler)
        self.app_context = app_context


def store_custom_cover(source: Path) -> str:
    if not source.exists() or not source.is_file():
        raise FileNotFoundError(source)
    suffix = source.suffix.lower() or ".png"
    if suffix not in {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"}:
        raise OSError("Unsupported image format. Use PNG, JPG, WebP, BMP, or GIF.")
    payload = source.read_bytes()
    digest = hashlib.sha1(payload).hexdigest()
    destination = get_custom_cover_dir() / f"{digest}{suffix}"
    if not destination.exists():
        shutil.copy2(source, destination)
    return destination.name


def parse_bangumi_subject_id(url: str) -> str:
    match = BANGUMI_SUBJECT_PATTERN.search(url.strip())
    return match.group(1) if match else ""
