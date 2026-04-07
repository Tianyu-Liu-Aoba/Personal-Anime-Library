from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from .config import get_app_data_dir


_LOGGING_READY = False
_ACTIVE_LOG_PATH: Path | None = None


def get_log_path() -> Path:
    if _ACTIVE_LOG_PATH is not None:
        return _ACTIVE_LOG_PATH
    return get_app_data_dir() / "anime-library.log"


def setup_logging() -> Path:
    global _LOGGING_READY, _ACTIVE_LOG_PATH
    path = get_app_data_dir() / "anime-library.log"
    if _LOGGING_READY:
        return get_log_path()

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    try:
        file_handler = RotatingFileHandler(
            path,
            maxBytes=1_000_000,
            backupCount=3,
            encoding="utf-8",
        )
    except OSError:
        path = Path.cwd() / ".anime-library-data" / "anime-library.log"
        path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            path,
            maxBytes=1_000_000,
            backupCount=3,
            encoding="utf-8",
        )
    file_handler.setFormatter(formatter)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.handlers.clear()
    root.addHandler(file_handler)
    root.addHandler(stream_handler)

    logging.getLogger(__name__).info("Logging initialized at %s", path)
    _ACTIVE_LOG_PATH = path
    _LOGGING_READY = True
    return path


def get_logger(name: str) -> logging.Logger:
    setup_logging()
    return logging.getLogger(name)


def read_recent_log_lines(limit: int = 120) -> dict[str, object]:
    path = get_log_path()
    if not path.exists():
        return {"path": str(path), "lines": []}
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        lines = handle.readlines()
    return {
        "path": str(path),
        "lines": [line.rstrip("\n") for line in lines[-max(limit, 1) :]],
    }
