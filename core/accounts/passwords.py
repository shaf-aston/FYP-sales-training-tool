"""Password hashing with scrypt (stdlib). Stored as "scrypt$n$r$p$salt$hash" so the cost can rise later
without breaking old hashes: each hash carries the settings it was made with."""

from __future__ import annotations

import hashlib
import hmac
import secrets

from core.infra.constants import SCRYPT_N, SCRYPT_P, SCRYPT_R

_SALT_BYTES, _KEY_BYTES = 16, 32


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(_SALT_BYTES)
    key = _scrypt(password, salt, SCRYPT_N, SCRYPT_R, SCRYPT_P)
    return f"scrypt${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${salt.hex()}${key.hex()}"


def check_password(password: str, stored: str) -> bool:
    """True when `password` matches `stored`; False for any malformed stored value."""
    try:
        scheme, n, r, p, salt, key = stored.split("$")
        if scheme != "scrypt":
            return False
        made = _scrypt(password, bytes.fromhex(salt), int(n), int(r), int(p))
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(made, bytes.fromhex(key))


def _scrypt(password: str, salt: bytes, n: int, r: int, p: int) -> bytes:
    return hashlib.scrypt(password.encode("utf-8"), salt=salt, n=n, r=r, p=p, dklen=_KEY_BYTES, maxmem=2**26)
