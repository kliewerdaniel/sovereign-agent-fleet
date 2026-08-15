"""Tamper-evident append-only ledger signed with Ed25519 (new in ChrisCryptSN).

Integrity properties:
  * each entry commits to the previous entry's hash (chain)
  * each entry hash is signed with Ed25519 (authenticity)
  * a signed checkpoint records the chain head + length, so TRUNCATION of the
    tail is detectable -- a plain chain walk cannot see records that are gone.

Persistence contract: ``store.put`` indexes records by ``record["id"]``, so
every entry carries a zero-padded sequence id. Chain state is reloaded from the
store on construction, so restarting the process continues the existing chain
instead of silently starting a second one.
"""
from __future__ import annotations

import hashlib
import json
import time
from typing import List, Optional

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

GENESIS = b"\x00" * 32
CHECKPOINT_ID = "checkpoint"

#: fields excluded from the signed body (they are envelope, not content)
_UNSIGNED = ("sig", "id")


def _entry_body(entry: dict) -> bytes:
    """Canonical signed body for an entry. Excludes signature and storage id."""
    return json.dumps(
        {k: v for k, v in entry.items() if k not in _UNSIGNED},
        sort_keys=True,
        separators=(",", ":"),
    ).encode()


class LedgerIntegrityError(RuntimeError):
    """Raised when persisted chain state cannot be trusted."""


class Ledger:
    def __init__(self, signing_key: Ed25519PrivateKey, store=None):
        self._key = signing_key
        self._pub = signing_key.public_key()
        self.store = store
        self._seq = 0
        self._prev = GENESIS
        self._resume()

    # -- chain state ------------------------------------------------------

    def _resume(self) -> None:
        """Reload head state from the store so restarts extend one chain."""
        if self.store is None:
            return
        entries = self.entries()
        if not entries:
            return
        last = entries[-1]
        self._seq = int(last["seq"]) + 1
        self._prev = hashlib.sha256(
            bytes.fromhex(last["prev"]) + _entry_body(last)
        ).digest()

    def entries(self) -> List[dict]:
        """All ledger entries in sequence order (excludes the checkpoint)."""
        if self.store is None:
            return []
        rows = [r for r in self.store.find("ledger") if r.get("id") != CHECKPOINT_ID]
        return sorted(rows, key=lambda r: int(r["seq"]))

    # -- append -----------------------------------------------------------

    def append(self, kind: str, payload: dict) -> dict:
        entry = {
            "seq": self._seq,
            "prev": self._prev.hex(),
            "ts": time.time(),
            "kind": kind,
            "payload": payload,
        }
        h = hashlib.sha256(self._prev + _entry_body(entry)).digest()
        entry["sig"] = self._key.sign(h).hex()
        # storage identity: zero-padded so lexical order == sequence order
        entry["id"] = f"{self._seq:012d}"
        self._seq += 1
        self._prev = h
        if self.store is not None:
            self.store.put("ledger", entry, event=f"ledger.{kind}")
            self._write_checkpoint()
        return entry

    def _write_checkpoint(self) -> None:
        """Signed head marker: makes tail truncation detectable."""
        cp = {
            "id": CHECKPOINT_ID,
            "count": self._seq,
            "head": self._prev.hex(),
            "ts": time.time(),
        }
        body = json.dumps(
            {k: v for k, v in cp.items() if k != "sig"}, sort_keys=True, separators=(",", ":")
        ).encode()
        cp["sig"] = self._key.sign(hashlib.sha256(body).digest()).hex()
        self.store.put("ledger", cp)

    def checkpoint(self) -> Optional[dict]:
        if self.store is None:
            return None
        return self.store.get("ledger", CHECKPOINT_ID)

    def public_key_pem(self) -> bytes:
        return self._pub.public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
        )

    # -- verification -----------------------------------------------------

    @classmethod
    def verify_chain(
        cls, entries: List[dict], pub_pem: bytes, checkpoint: Optional[dict] = None
    ) -> bool:
        """Verify signatures + linkage, and (when given) head/length vs checkpoint.

        Without a checkpoint this detects tampering and reordering but NOT
        truncation of the tail; pass ``checkpoint`` to close that gap.
        """
        pub = serialization.load_pem_public_key(pub_pem)
        entries = [e for e in entries if e.get("id") != CHECKPOINT_ID]
        prev = GENESIS
        for expected_seq, e in enumerate(entries):
            if int(e.get("seq", -1)) != expected_seq:
                return False
            if e.get("prev") != prev.hex():
                return False
            h = hashlib.sha256(prev + _entry_body(e)).digest()
            try:
                pub.verify(bytes.fromhex(e["sig"]), h)
            except Exception:
                return False
            prev = h

        if checkpoint is not None:
            body = json.dumps(
                {k: v for k, v in checkpoint.items() if k != "sig"},
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
            try:
                pub.verify(
                    bytes.fromhex(checkpoint["sig"]), hashlib.sha256(body).digest()
                )
            except Exception:
                return False
            if int(checkpoint["count"]) != len(entries):
                return False
            if checkpoint["head"] != prev.hex():
                return False
        return True
