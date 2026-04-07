from __future__ import annotations

import argparse

from .config import find_open_port
from .logging_utils import get_logger, setup_logging
from .server import AnimeLibraryServer, AppContext, AppHandler
from .windows import open_browser

logger = get_logger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Anime library scanner and local web UI for Windows.")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind the local web server to.")
    parser.add_argument("--port", type=int, default=None, help="Port to bind to. Defaults to 48321 or the next free port.")
    parser.add_argument("--no-browser", action="store_true", help="Start the server without opening the browser.")
    return parser


def main(argv: list[str] | None = None) -> int:
    setup_logging()
    parser = build_parser()
    args = parser.parse_args(argv)
    host = args.host
    port = args.port or find_open_port(host)
    app_context = AppContext()
    server = AnimeLibraryServer((host, port), AppHandler, app_context)
    url = f"http://{host}:{port}/"
    logger.info("Starting Anime Library at %s", url)
    if not args.no_browser:
        open_browser(url)
    print(f"Anime Library is running at {url}")
    print("Press Ctrl+C to stop the server.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server...")
        logger.info("Stopping Anime Library server")
    finally:
        server.server_close()
    return 0
