"""SovereignCrypto - facade tying the hardened primitives together."""
from __future__ import annotations

import base64
import os
import secrets
import time
from typing import Optional

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from . import auth, envelope, kdf, ledger
from .store import JsonStore


def _ledger_key(kek: bytes) -> Ed25519PrivateKey:
    raw = HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=b"chriscrypt:ledger").derive(kek)
    return Ed25519PrivateKey.from_private_bytes(raw)


class SovereignCrypto:
    _SENTINEL = "chriscrypt-sentinel-v1"

    def __init__(self, workspace: str, passphrase: bytes):
        os.makedirs(workspace, exist_ok=True)
        self.store = JsonStore(os.path.join(workspace, "state.json"))
        # Per-workspace salt (not secret) -- persisted so the SAME passphrase
        # yields the SAME KEK for a workspace but DIFFERENT KEKs across
        # workspaces. A static salt (previous behaviour) made every workspace
        # rainbow-tableable with one table.
        salt_rec = self.store.get("workspace", "salt")
        if salt_rec is None:
            salt = secrets.token_bytes(16)
            self.store.put("workspace", {"id": "salt", "salt": base64.b64encode(salt).decode()})
        else:
            salt = base64.b64decode(salt_rec["salt"])
        self.kek = envelope.derive_kek(passphrase, salt)
        self.env = envelope.Envelope(kek=self.kek)
        # SEC-6 (deepened): a wrong master passphrase must fail CLOSED at open
        # time, not silently yield a session with a wrong KEK. A sealed sentinel
        # lets us verify the passphrase before anything else happens.
        self._check_or_init_sentinel()
        self.sessions = auth.SessionAuth(self.store, kek=self.kek)
        self.ledger = ledger.Ledger(_ledger_key(self.kek), store=self.store)

    def _check_or_init_sentinel(self) -> None:
        rec = self.store.get("sentinel", "workspace")
        if rec is None:
            self.store.put("sentinel", self.env.seal("workspace", self._SENTINEL))
            return
        try:
            pt = self.env.open(rec)
        except Exception:
            raise envelope.EnvelopeError("incorrect master passphrase for this workspace")
        if pt != self._SENTINEL:
            raise envelope.EnvelopeError("incorrect master passphrase for this workspace")

    def register(self, username: str, password: str) -> str:
        if self.store.get("users", username):
            raise ValueError("user exists")
        rec = {"id": username, "username": username, "pw_hash": kdf.hash_password(password), "disabled": False, "created": time.time()}
        self.store.put("users", rec, event="user.created")
        self.ledger.append("user.created", {"username": username})
        return username

    def authenticate(self, username: str, password: str, device_fp: str = "") -> Optional[auth.Session]:
        rec = self.store.get("users", username)
        if not rec or rec.get("disabled"):
            kdf.verify_password(password or "x", "")
            return None
        if not kdf.verify_password(password, rec["pw_hash"]):
            return None
        s = self.sessions.create_session(username, device_fp)
        self.ledger.append("session.created", {"username": username})
        return s

    def set_secret(self, name: str, value: str, actor: str = "system") -> dict:
        rec = self.env.seal(name, value)
        self.store.put("secrets", rec, event="secret.stored")
        self.ledger.append("secret.stored", {"name": name, "fingerprint": rec["fingerprint"]})
        return rec

    def get_secret(self, name: str) -> str:
        rec = self.store.get("secrets", name)
        if not rec:
            raise KeyError(name)
        return self.env.open(rec)

    def verify_ledger(self) -> bool:
        entries = self.store.find("ledger")
        cp = self.ledger.checkpoint()
        return ledger.Ledger.verify_chain(entries, self.ledger.public_key_pem(), checkpoint=cp)
