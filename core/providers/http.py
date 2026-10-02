"""Minimal HTTP helpers for provider integrations."""

from __future__ import annotations

import json
from urllib import error as urlerror
from urllib import request as urlrequest


class ProviderHTTPError(Exception):
    def __init__(self, status_code: int, body: str, reason: str = ""):
        """Wrap HTTP failures with status code and decoded body text."""
        super().__init__(reason or body or f"HTTP {status_code}")
        self.status_code = status_code
        self.body = body
        self.reason = reason or body or f"HTTP {status_code}"


def _read_http_error(exc: urlerror.HTTPError) -> str:
    """Read and decode the response body from an HTTP error object."""
    try:
        return exc.read().decode("utf-8", errors="ignore")
    except Exception:
        return ""


def post_json(url: str, payload: dict, headers: dict[str, str], timeout: int = 30):
    """POST a JSON payload and return response bytes plus response headers."""
    data = json.dumps(payload).encode("utf-8")
    request = urlrequest.Request(
        url,
        data=data,
        method="POST",
        headers={
            "Content-Type": "application/json",
            **headers,
        },
    )
    try:
        with urlrequest.urlopen(request, timeout=timeout) as response:
            return response.read(), dict(response.info())
    except urlerror.HTTPError as exc:
        raise ProviderHTTPError(exc.code, _read_http_error(exc), exc.reason) from exc
