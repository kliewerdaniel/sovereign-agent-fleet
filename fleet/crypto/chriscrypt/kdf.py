"""Password key derivation (strengthened).

Preferred: Argon2id (OWASP/PHC recommended; memory-hard). Fallback: PBKDF2-HMAC-
SHA256 @ 600k (up from sworker's 200k) when argon2 is unavailable.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
from typing import Optional

try:
    from argon2 import PasswordHasher
    from argon2.exceptions import VerifyMismatchError, InvalidHashError
    _ARGON = PasswordHasher()
except Exception:
    PasswordHasher = None
    _ARGON = None

PBKDF2_ROUNDS = 600_000


def hash_password(password: str) -> str:
    if _ARGON is not None:
        return _ARGON.hash(password)
    return _pbkdf2_hash(password)


def _pbkdf2_hash(password: str, salt: Optional[bytes] = None) -> str:
    if salt is None:
        salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ROUNDS)
    return f"{salt.hex()}${PBKDF2_ROUNDS}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    if not stored:
        _pbkdf2_hash(password or "x")
        return False
    if _ARGON is not None and stored.startswith("$argon2id$"):
        try:
            _ARGON.verify(stored, password)
            return True
        except (VerifyMismatchError, InvalidHashError):
            return False
    try:
        salt_hex, rounds_s, hash_hex = stored.split("$")
    except ValueError:
        return False
    salt = bytes.fromhex(salt_hex)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, int(rounds_s))
    return hmac.compare_digest(dk.hex(), hash_hex)
