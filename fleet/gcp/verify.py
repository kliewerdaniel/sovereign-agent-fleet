"""14.8 Integration verifier: proves the GCP copy is verifiable DATA, not authority.

Runs against the Firestore mirror (``GcpBridge.mirror_docs()``) using ONLY the
agent **public** keys. It must reproduce the same tamper detection the local
runtime enforces -- confirming GCP holds verifiable artifacts but no signing
authority (D3/D6). Reuses ``Ledger.verify_chain`` so the on-cloud and on-local
verification paths are identical.

The verifier never receives a private key. ``audit_pub_pem`` is the ledger
signer's Ed25519 public key (the Control Plane audit key). Certs/approvals are
individually verified against the root public key (also public).
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List, Optional

from fleet.crypto.chriscrypt.ledger import (
    GENESIS,
    LedgerIntegrityError,
    _entry_body,
)
from fleet.crypto.foundation import canonical_bytes


class FirestoreVerifier:
    def __init__(self, docs: List[Dict[str, Any]], audit_pub_pem: bytes,
                 root_pub_pem: Optional[bytes] = None):
        # ONLY public material is accepted. No private key, no secret crosses here.
        self._docs = docs
        self._audit_pub = audit_pub_pem
        self._root_pub = root_pub_pem

    # -- entry extraction ---------------------------------------------------
    def ledger_entries(self) -> List[Dict[str, Any]]:
        """Reconstruct the audit ledger from the Firestore doc mirror.

        Each doc's ``payload`` is the verbatim signed ledger entry; the mirror
        reproduces it byte-for-byte so ``Ledger.verify_chain`` applies unchanged.
        """
        entries = [
            d["payload"] for d in self._docs
            if d.get("payload", {}).get("kind") is not None and "seq" in d.get("payload", {})
        ]
        return sorted(entries, key=lambda e: int(e.get("seq", 0)))

    def checkpoint_doc(self) -> Optional[Dict[str, Any]]:
        for d in self._docs:
            p = d.get("payload", {})
            if p.get("id") == "checkpoint":
                return p
        return None

    # -- 14.8: verify the GCP copy with public keys only --------------------
    def verify(self) -> bool:
        """Reproduce tamper detection against the Firestore copy (D3/D6)."""
        try:
            self.verify_or_raise()
            return True
        except LedgerIntegrityError:
            return False

    def verify_or_raise(self) -> None:
        entries = self.ledger_entries()
        checkpoint = self.checkpoint_doc()
        ok = self._verify_chain(entries, self._audit_pub, checkpoint)
        if not ok:
            raise LedgerIntegrityError(
                "Firestore copy failed integrity verification (public-key verify)"
            )

    @staticmethod
    def _verify_chain(entries, audit_pub_pem: bytes,
                      checkpoint: Optional[dict]) -> bool:
        from cryptography.hazmat.primitives import serialization
        pub = serialization.load_pem_public_key(audit_pub_pem)
        entries = [e for e in entries if e.get("id") != "checkpoint"]
        prev = GENESIS
        for expected_seq, e in enumerate(entries):
            if int(e.get("seq", -1)) != expected_seq:
                return False
            if e.get("prev") != prev.hex():
                return False
            try:
                h = hashlib.sha256(prev + _entry_body(e)).digest()
            except Exception:
                return False
            try:
                pub.verify(bytes.fromhex(e["sig"]), h)
            except Exception:
                return False
            prev = h
        if checkpoint is not None:
            # MUST match Ledger._write_checkpoint: the signed body INCLUDES the
            # "id" field (unlike the entry body, which excludes it). Reuse the
            # exact same construction so a valid Firestore copy verifies.
            cp_body = json.dumps(
                {k: v for k, v in checkpoint.items() if k != "sig"},
                sort_keys=True, separators=(",", ":"),
            ).encode()
            try:
                pub.verify(
                    bytes.fromhex(checkpoint["sig"]), hashlib.sha256(cp_body).digest()
                )
            except Exception:
                return False
            if int(checkpoint.get("count", -1)) != len(entries):
                return False
            if checkpoint.get("head") != prev.hex():
                return False
        return True

    # -- individual artifact verification (certs / approvals) ---------------
    def verify_cert(self, cert: Dict[str, Any], root_pub_pem: bytes) -> bool:
        from fleet.crypto.foundation import IdentityRoot

        # IdentityRoot.verify_cert requires the root PRIVATE key to re-derive the
        # public key; for a read-only public-key verifier we check the signature
        # directly against the root public key (no authority needed).
        from cryptography.hazmat.primitives import serialization

        root_pub = serialization.load_pem_public_key(root_pub_pem)
        candidate = dict(cert)
        candidate["root_sig"] = ""
        try:
            root_pub.verify(bytes.fromhex(cert["root_sig"]), canonical_bytes(candidate))
        except Exception:
            return False
        return True
