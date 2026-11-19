"""Sending an email (the sign-in link). Through Resend's HTTPS API when RESEND_API_KEY and MAIL_FROM are set; else
email is off and the features that need it are hidden. Never logs an address or a link."""

from __future__ import annotations

import json
import urllib.request

from core.infra.env import env_str

RESEND_URL = "https://api.resend.com/emails"


def mail_ready() -> bool:
    return bool(env_str("RESEND_API_KEY") and env_str("MAIL_FROM"))


def send_mail(to: str, subject: str, text: str) -> None:
    """Raises on any failure (the caller says sending failed)."""
    body = json.dumps({"from": env_str("MAIL_FROM"), "to": [to], "subject": subject, "text": text}).encode()
    req = urllib.request.Request(RESEND_URL, data=body, headers={
        "Authorization": f"Bearer {env_str('RESEND_API_KEY')}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as res:   # noqa: S310 (a fixed https URL)
        if res.status >= 300:
            raise OSError(f"mail service answered {res.status}")
