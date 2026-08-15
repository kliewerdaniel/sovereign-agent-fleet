"""Envelope encryption (hardened).

Backends (never silent about which is used -- the ``algo`` field records it):
  * Primary:  XChaCha20-Poly1305 (24-byte nonce) via PyNaCl. Reuse is
    practically impossible because the nonce is 192 bits.
  * Secondary: AES-256-GCM (12-byte nonce) via cryptography. Chosen only when
    PyNaCl is unavailable; per-record subkeys bound nonce reuse to one key.

KEK derivation: Argon2id (memory-hard) via argon2-cffi. This FAILS CLOSED if
argon2-cffi is absent -- no weaker KDF is accepted, because a weak KDF is the
single most exploitable link in the chain.

Per-record subkeys via HKDF from the KEK; key versioning supports rotation.
The record ``name`` is used as AEAD associated data, binding ciphertext to its
identity (prevents record swapping). The fingerprint is a KEYED HMAC over a
KEK-derived key, so a passive attacker holding only the encrypted store cannot
brute-force it. Fail-closed: raises rather than persisting plaintext.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
import time
from typing import Optional

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

try:
    from nacl.bindings import (  # type: ignore
        crypto_aead_xchacha20poly1305_ietf_decrypt as _xc_dec,
        crypto_aead_xchacha20poly1305_ietf_encrypt as _xc_enc,
    )
    _X_AVAIL = True
except Exception:  # pragma: no cover - exercised only without PyNaCl
    _xc_enc = _xc_dec = None
    _X_AVAIL = False

try:
    import argon2.low_level as _al
    _ARGON = True
except Exception:  # pragma: no cover
    _al = None
    _ARGON = False

_NONCE_LEN_X = 24
_NONCE_LEN_A = 12
_TAG_LEN = 16
_FP_LEN = 32


class CryptoUnavailable(RuntimeError):
    pass


class EnvelopeError(RuntimeError):
    pass


def derive_kek(passphrase: bytes, salt: bytes) -> bytes:
    """Argon2id (memory-hard) KEK derivation. Fail-closed: refuses weaker KDFs."""
    if not _ARGON:
        raise CryptoUnavailable(
            "Argon2id (argon2-cffi) is required for KEK derivation; "
            "refusing to fall back to a weaker KDF"
        )
    return _al.hash_secret_raw(
        secret=passphrase,
        salt=salt,
        time_cost=3,
        memory_cost=65536,
        parallelism=1,
        hash_len=32,
        type=_al.Type.ID,
    )


def _resolve_kek(key: Optional[bytes], path: Optional[str]) -> bytes:
    """Resolve a caller-supplied KEK. Never auto-generates or mints a key."""
    if key is not None:
        if len(key) != 32:
            raise EnvelopeError("kek must be 32 bytes")
        return key
    env = os.environ.get("CHRISCRYPT_KEK")
    if env:
        raw = base64.b64decode(env)
        if len(raw) != 32:
            raise EnvelopeError("CHRISCRYPT_KEK must decode to 32 bytes")
        return raw
    if path and os.path.exists(path):
        with open(path, "rb") as f:
            raw = base64.b64decode(f.read().strip())
        if len(raw) != 32:
            raise EnvelopeError("key file must decode to 32 bytes")
        return raw
    raise EnvelopeError(
        "no KEK provided and none resolvable; refusing to generate one"
    )


class Envelope:
    def __init__(self, kek: Optional[bytes] = None, key_path: Optional[str] = None, version: int = 1):
        self.version = version
        if _X_AVAIL:
            self.algo = "xchacha20poly1305"
        elif AESGCM is not None:
            self.algo = "aes256gcm"
        else:
            raise CryptoUnavailable("no AEAD backend available; refusing to persist plaintext")
        self._kek = _resolve_kek(kek, key_path)
        self._fp_key = HKDF(
            algorithm=hashes.SHA256(), length=32, salt=None, info=b"chriscrypt:fingerprint"
        ).derive(self._kek)

    def _subkey(self, name: str, v: int) -> bytes:
        info = f"chriscrypt:v{v}:{name}".encode()
        return HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=info).derive(self._kek)

    def _fp(self, value: str) -> str:
        """Keyed fingerprint: useless to an attacker without the KEK."""
        return hmac.new(self._fp_key, value.encode("utf-8"), hashlib.sha256).hexdigest()[:_FP_LEN]

    def seal(self, name: str, value: str) -> dict:
        if not name or not isinstance(value, str) or not value:
            raise EnvelopeError("name/value must be non-empty strings")
        sub = self._subkey(name, self.version)
        pt = value.encode("utf-8")
        aad = name.encode("utf-8")
        if _X_AVAIL:
            nonce = secrets.token_bytes(_NONCE_LEN_X)
            ct = _xc_enc(pt, aad, nonce, sub)
        else:
            nonce = secrets.token_bytes(_NONCE_LEN_A)
            ct = AESGCM(sub).encrypt(nonce, pt, aad)
        ciphertext, tag = ct[:-_TAG_LEN], ct[-_TAG_LEN:]
        return {
            "id": name,
            "name": name,
            "algo": self.algo,
            "version": self.version,
            "created_at": time.time_ns(),
            "nonce": base64.b64encode(nonce).decode(),
            "ciphertext": base64.b64encode(ciphertext).decode(),
            "authentication_tag": base64.b64encode(tag).decode(),
            "fingerprint": self._fp(value),
        }

    def open(self, rec: dict) -> str:
        sub = self._subkey(rec["name"], rec.get("version", 1))
        nonce = base64.b64decode(rec["nonce"])
        ct = base64.b64decode(rec["ciphertext"]) + base64.b64decode(rec["authentication_tag"])
        aad = rec["name"].encode("utf-8")
        if rec["algo"] == "xchacha20poly1305":
            if not _X_AVAIL:
                raise CryptoUnavailable("XChaCha requested but PyNaCl unavailable")
            pt = _xc_dec(ct, aad, nonce, sub)
        elif rec["algo"] == "aes256gcm":
            if AESGCM is None:
                raise CryptoUnavailable("AES-GCM requested but cryptography unavailable")
            pt = AESGCM(sub).decrypt(nonce, ct, aad)
        else:
            raise EnvelopeError(f"unknown algo: {rec.get('algo')}")
        return pt.decode("utf-8")
