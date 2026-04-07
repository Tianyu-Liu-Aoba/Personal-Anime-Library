from __future__ import annotations

import json
import time
from collections import defaultdict
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


DEFAULT_HEADERS = {
    "User-Agent": "AnimeLibraryExpressive/1.0 (+https://localhost)",
    "Accept": "application/json, text/html;q=0.9, */*;q=0.8",
}

_LAST_REQUEST_AT: dict[str, float] = defaultdict(float)


class HttpRequestError(RuntimeError):
    pass


def throttle(key: str, minimum_interval: float) -> None:
    if minimum_interval <= 0:
        return
    elapsed = time.monotonic() - _LAST_REQUEST_AT[key]
    if elapsed < minimum_interval:
        time.sleep(minimum_interval - elapsed)
    _LAST_REQUEST_AT[key] = time.monotonic()


def fetch_bytes(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    timeout: float = 20.0,
    throttle_key: str | None = None,
    minimum_interval: float = 0.0,
) -> bytes:
    if throttle_key:
        throttle(throttle_key, minimum_interval)
    request_headers = dict(DEFAULT_HEADERS)
    if headers:
        request_headers.update(headers)
    request = Request(url, headers=request_headers)
    try:
        with urlopen(request, timeout=timeout) as response:
            return response.read()
    except HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        raise HttpRequestError(f"{error.code} {error.reason}: {body[:280]}") from error
    except URLError as error:
        raise HttpRequestError(str(error.reason)) from error


def fetch_text(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    timeout: float = 20.0,
    throttle_key: str | None = None,
    minimum_interval: float = 0.0,
) -> str:
    payload = fetch_bytes(
        url,
        headers=headers,
        timeout=timeout,
        throttle_key=throttle_key,
        minimum_interval=minimum_interval,
    )
    return payload.decode("utf-8", errors="replace")


def fetch_json(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    timeout: float = 20.0,
    throttle_key: str | None = None,
    minimum_interval: float = 0.0,
) -> Any:
    if throttle_key:
        throttle(throttle_key, minimum_interval)
    request_headers = dict(DEFAULT_HEADERS)
    if headers:
        request_headers.update(headers)
    data = None
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request_headers.setdefault("Content-Type", "application/json")
    request = Request(url, data=data, headers=request_headers, method=method)
    try:
        with urlopen(request, timeout=timeout) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            return json.loads(response.read().decode(charset, errors="replace"))
    except HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        raise HttpRequestError(f"{error.code} {error.reason}: {body[:280]}") from error
    except URLError as error:
        raise HttpRequestError(str(error.reason)) from error


def encode_path(value: str) -> str:
    return quote(value, safe="")
