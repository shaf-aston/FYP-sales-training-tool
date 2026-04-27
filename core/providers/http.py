"""Minimal HTTP helpers for provider integrations."""

from __future__ import annotations

import json
import uuid
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


def post_bytes(
    url: str,
    body: bytes,
    headers: dict[str, str],
    timeout: int = 30,
):
    """POST raw bytes and return response bytes plus response headers."""
    request = urlrequest.Request(
        url,
        data=body,
        method="POST",
        headers=headers,
    )
    try:
        with urlrequest.urlopen(request, timeout=timeout) as response:
            return response.read(), dict(response.info())
    except urlerror.HTTPError as exc:
        raise ProviderHTTPError(exc.code, _read_http_error(exc), exc.reason) from exc


def _build_multipart_body(
    fields: dict[str, str],
    file_field: str,
    filename: str,
    content_type: str,
    file_bytes: bytes,
) -> tuple[bytes, str]:
    """Build a multipart form body and return it with the boundary string."""
    boundary = f"codex-{uuid.uuid4().hex}"
    body = bytearray()

    for key, value in fields.items():
        body.extend(f"--{boundary}\r\n".encode("utf-8"))
        body.extend(
            f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode("utf-8")
        )
        body.extend(str(value).encode("utf-8"))
        body.extend(b"\r\n")

    body.extend(f"--{boundary}\r\n".encode("utf-8"))
    body.extend(
        (
            f'Content-Disposition: form-data; name="{file_field}"; '
            f'filename="{filename}"\r\n'
        ).encode("utf-8")
    )
    body.extend(f"Content-Type: {content_type}\r\n\r\n".encode("utf-8"))
    body.extend(file_bytes)
    body.extend(b"\r\n")
    body.extend(f"--{boundary}--\r\n".encode("utf-8"))
    return bytes(body), boundary


def post_multipart(
    url: str,
    fields: dict[str, str],
    file_field: str,
    filename: str,
    content_type: str,
    file_bytes: bytes,
    headers: dict[str, str],
    timeout: int = 30,
):
    """POST multipart form data and return response bytes plus response headers."""
    body, boundary = _build_multipart_body(
        fields=fields,
        file_field=file_field,
        filename=filename,
        content_type=content_type,
        file_bytes=file_bytes,
    )
    request = urlrequest.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            **headers,
        },
    )
    try:
        with urlrequest.urlopen(request, timeout=timeout) as response:
            return response.read(), dict(response.info())
    except urlerror.HTTPError as exc:
        raise ProviderHTTPError(exc.code, _read_http_error(exc), exc.reason) from exc
