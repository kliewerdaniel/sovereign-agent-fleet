"""Sessions (strengthened): 32-byte tokens + optional device binding."""
from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from dataclasses import dataclass, field
from typing import Optional

TOKEN_BYTES = 32
DEFAULT_TTL = 60 * 60 * 12


@dataclass
class Session:
    token: str
    username: str
    created: float = field(default_factory=time.time)
    expires: float = field(default_factory=lambda: time.time() + DEFAULT_TTL)
    binding: str = ""
    revoked: bool = False

    def is_valid(self, now: Optional[float] = None) -> bool:
        now = time.time() if now is None else now
        return (not self.revoked) and (self.expires > now)

    def to_dict(self) -> dict:
        return {"id": self.token, "token": self.token, "username": self.username, "created": self.created, "expires": self.expires, "binding": self.binding, "revoked": self.revoked}

    @classmethod
    def from_dict(cls, d: dict) -> "Session":
        return cls(token=d["token"], username=d["username"], created=d.get("created", time.time()), expires=d.get("expires", time.time()), binding=d.get("binding", ""), revoked=bool(d.get("revoked", False)))


class SessionAuth:
    def __init__(self, store, kek: bytes, ttl: int = DEFAULT_TTL):
        self.store = store
        self.ttl = ttl
        self._kek = kek

    def _bind(self, token: str, device_fp: str) -> str:
        return hmac.new(self._kek, f"{token}|{device_fp}".encode(), hashlib.sha256).hexdigest()

    def create_session(self, username: str, device_fp: str = "") -> Session:
        tok = secrets.token_urlsafe(TOKEN_BYTES)
        s = Session(token=tok, username=username, expires=time.time() + self.ttl, binding=self._bind(tok, device_fp))
        self.store.put("sessions", s.to_dict(), event="session.created")
        return s

    def validate(self, token: str, device_fp: str = "", now: Optional[float] = None) -> Optional[str]:
        if not token:
            return None
        rec = self.store.get("sessions", token)
        if not rec:
            return None
        s = Session.from_dict(rec)
        if not s.is_valid(now):
            return None
        if s.binding and device_fp and not hmac.compare_digest(s.binding, self._bind(token, device_fp)):
            return None
        return s.username

    def revoke(self, token: str) -> None:
        rec = self.store.get("sessions", token)
        if not rec:
            return
        rec["revoked"] = True
        self.store.put("sessions", rec, event="session.revoked")
