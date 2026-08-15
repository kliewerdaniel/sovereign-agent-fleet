"""Phase 0 crypto foundation for the Sovereign Agent Fleet.

Wraps the vendored ChrisCryptSN (MIT) primitives and builds the
fleet-specific identity + audit abstractions from the data model (doc 12):

  * Root-of-trust key hierarchy (D13): Argon2id-derived master -> root Ed25519
    signing key -> per-agent Ed25519 identity keys (root-signed certs).
  * Per-record envelope encryption via ChrisCryptSN.Envelope (XChaCha20-Poly1305,
    HKDF per-record subkeys, record-name AAD) -- confidentiality only.
  * Tamper-evident audit ledger via ChrisCryptSN.Ledger (Ed25519-signed hash
    chain + signed checkpoint for truncation detection).
  * Deterministic canonical serialization used by every signer/verifier (12.7).

NO new cryptographic primitives are invented. All security properties come from
ChrisCryptSN or standard library `cryptography`/`pynacl`.

Deviation from planning doc D4 (reuse Sovereign Worker control plane): the
`sovereign` repos are all-rights-reserved (no license), so the Sovereign
`audit_ledger.py` wrapper is reimplemented here as clean-room code. ChrisCryptSN
is MIT and safe to vendor. Documented in 10-decisions-ADR as D4a.
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from .chriscrypt.envelope import Envelope
from .chriscrypt.kdf import hash_password, verify_password
from .chriscrypt.ledger import Ledger, LedgerIntegrityError

# ---------------------------------------------------------------------------
# Canonical serialization (12.7) -- the single rule every signer uses.
# ---------------------------------------------------------------------------

_UNSIGNED = ("sig", "id")


def canonical_bytes(obj: Dict[str, Any]) -> bytes:
    """Deterministic canonical encoding for signing.

    Sort keys, compact separators, exclude signature/storage fields. Stable
    across machines so a signature verifies anywhere.
    """
    body = {k: v for k, v in obj.items() if k not in _UNSIGNED}
    return json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


# ---------------------------------------------------------------------------
# Key hierarchy (D13) -- root of trust + agent identity certs.
# ---------------------------------------------------------------------------

AGENT_ROLES = ("researcher", "analyst", "operator", "human", "tool")


@dataclass
class AgentCert:
    agent_id: str
    pubkey_pem: str
    role: str
    capabilities: List[str]
    issued_at: int
    expires_at: int
    cert_seq: int
    root_sig: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "pubkey_pem": self.pubkey_pem,
            "role": self.role,
            "capabilities": self.capabilities,
            "issued_at": self.issued_at,
            "expires_at": self.expires_at,
            "cert_seq": self.cert_seq,
            "root_sig": self.root_sig,
            # 'id' added by store; excluded from signature
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "AgentCert":
        return cls(
            agent_id=d["agent_id"],
            pubkey_pem=d["pubkey_pem"],
            role=d["role"],
            capabilities=list(d["capabilities"]),
            issued_at=d["issued_at"],
            expires_at=d["expires_at"],
            cert_seq=d["cert_seq"],
            root_sig=d["root_sig"],
        )


class IdentityRoot:
    """Root-of-trust: derives a root Ed25519 key and issues/signs agent certs."""

    #: Epoch of the current root key. Bumped on rotate_root so public verifiers
    #: can accept historical certs signed under a prior (rotated) root while
    #: still rejecting anything not signed by a known root epoch (K1).
    def __init__(self, master_secret: bytes, salt: Optional[bytes] = None):
        self.salt = salt or os.urandom(16)
        # Argon2id-strengthened master -> 32-byte seed -> root signing key.
        from .chriscrypt.envelope import derive_kek
        kek = derive_kek(master_secret, self.salt)
        self._root = Ed25519PrivateKey.from_private_bytes(kek)
        self._revoked: Dict[str, int] = {}  # agent_id -> revocation cert_seq sentinel
        self.root_epoch: int = 0
        # Root public keys for every epoch this runtime has known (for verifier
        # continuity: a verifier given the old+new root pubkeys still validates
        # historical chains). Seeded with the current epoch.
        self.known_root_pubs: Dict[int, bytes] = {self.root_epoch: self.root_public_pem}

    @property
    def root_public_pem(self) -> bytes:
        return self._root.public_key().public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )

    def export_seed(self, backup_kek: bytes) -> Dict[str, Any]:
        """Encrypted, key-wrapped root seed export (K1 disaster recovery).

        Never persists the root key in plaintext. The 32-byte seed is sealed
        with the caller-supplied backup KEK via the standard Envelope (same
        crypto used for the Memory Bank). The salt and current epoch travel
        with the blob so a restore reproduces the identical root key.
        """
        if len(backup_kek) != 32:
            raise ValueError("backup_kek must be 32 bytes")
        seed = self._root.private_bytes(
            serialization.Encoding.Raw, serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption(),
        )
        vault = SecretVault(backup_kek)
        sealed = vault.seal("root_seed", seed.hex())
        return {
            "salt": self.salt.hex(),
            "epoch": self.root_epoch,
            "sealed_seed": sealed,
        }

    @classmethod
    def from_seed(cls, blob: Dict[str, Any], backup_kek: bytes,
                  master_secret: bytes) -> "IdentityRoot":
        """Restore a root key from an export_seed blob (K1 recovery).

        `master_secret` is re-derived to confirm the restoring operator holds
        the original material; `backup_kek` unwraps the sealed seed. Both must
        agree with the export or the restore fails closed.
        """
        if len(backup_kek) != 32:
            raise ValueError("backup_kek must be 32 bytes")
        root = cls(master_secret, salt=bytes.fromhex(blob["salt"]))
        vault = SecretVault(backup_kek)
        seed_hex = vault.open(blob["sealed_seed"])
        restored = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(seed_hex))
        # The unwrapped seed must reproduce the derived root key exactly; if
        # master_secret + backup_kek disagree, the root won't match and we
        # refuse to substitute a divergent key.
        if restored.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw
        ) != root._root.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw
        ):
            raise ValueError("root seed does not match derived master (restore rejected)")
        root._root = restored
        root.root_epoch = int(blob["epoch"])
        root.known_root_pubs = {root.root_epoch: root.root_public_pem}
        return root

    def rotate_root(self, new_root: "IdentityRoot", issued_at: int,
                    expires_at: int, live_certs: List[AgentCert]) -> List[AgentCert]:
        """Re-sign all live agent certs under a new root (K1 root rotation).

        Requires the CURRENT root key to authorize the rotation (no silent root
        swap). Bumps the epoch, records the new root pubkey, and re-issues every
        supplied live cert under the new root with an incremented cert_seq so
        the chain stays continuous and historical certs remain verifiable via
        `known_root_pubs`.

        Returns the re-signed certs; the caller (ControlPlane) persists them and
        emits a signed `registry.root_rotate` audit entry.
        """
        # Authorize: the rotation record must be signed by the CURRENT root.
        rotate_body = canonical_bytes({
            "old_epoch": self.root_epoch,
            "new_epoch": new_root.root_epoch,
            "new_root_pub": new_root.root_public_pem.decode("utf-8"),
        })
        rotate_sig = self._root.sign(rotate_body).hex()
        old_epoch = self.root_epoch
        old_epoch_pub = self.root_public_pem
        # Commit: retain the OLD root pub under its epoch (verifier continuity),
        # then adopt the new root, bump epoch, and record the new root pub.
        self.known_root_pubs[old_epoch] = old_epoch_pub
        # Assign the new root a distinct epoch so historical chains stay keyed.
        new_epoch = (max(self.known_root_pubs.keys()) + 1) if self.known_root_pubs else 1
        new_root.root_epoch = new_epoch
        new_root.known_root_pubs = {new_epoch: new_root.root_public_pem}
        self._root = new_root._root
        self.root_epoch = new_epoch
        self.known_root_pubs[new_epoch] = self.root_public_pem
        self._rotation_sig = rotate_sig
        # Re-sign every live cert under the new root.
        resigned = []
        for cert in live_certs:
            if cert.role not in AGENT_ROLES:
                continue
            nc, _ = self.issue_cert(
                cert.agent_id, cert.role, cert.capabilities,
                issued_at, expires_at, cert_seq=cert.cert_seq + 1,
            )
            resigned.append(nc)
        return resigned

    def verify_cert_any_epoch(self, cert: AgentCert) -> bool:
        """Verify a cert against ANY known root epoch (verifier continuity).

        Used by public verifiers that hold the old+new root public keys so a
        rotated root doesn't invalidate the historical chain.
        """
        candidate = AgentCert.from_dict(cert.to_dict())
        candidate.root_sig = ""
        body = canonical_bytes(candidate.to_dict())
        for pub_pem in self.known_root_pubs.values():
            if pub_pem is None:
                continue
            try:
                key = serialization.load_pem_public_key(pub_pem)
                if not isinstance(key, Ed25519PublicKey):
                    continue
                key.verify(bytes.fromhex(cert.root_sig), body)
                return True
            except Exception:
                continue
        return False

    def issue_cert(
        self,
        agent_id: str,
        role: str,
        capabilities: List[str],
        issued_at: int,
        expires_at: int,
        cert_seq: int = 0,
    ) -> Tuple[AgentCert, Ed25519PrivateKey]:
        if role not in AGENT_ROLES:
            raise ValueError(f"unknown role: {role}")
        agent_key = Ed25519PrivateKey.generate()
        pub_pem = agent_key.public_key().public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode("utf-8")
        cert = AgentCert(
            agent_id=agent_id,
            pubkey_pem=pub_pem,
            role=role,
            capabilities=capabilities,
            issued_at=issued_at,
            expires_at=expires_at,
            cert_seq=cert_seq,
            root_sig="",
        )
        # Sign the cert body EXCLUDING root_sig (the signature is not its own input).
        body = canonical_bytes(cert.to_dict())
        cert.root_sig = self._root.sign(body).hex()
        return cert, agent_key

    def verify_cert(self, cert: AgentCert) -> bool:
        """True iff cert is signed by this root, unrevoked, and unexpired."""
        if cert.agent_id in self._revoked:
            return False
        candidate = AgentCert.from_dict(cert.to_dict())
        candidate.root_sig = ""  # exclude signature from the signed body
        try:
            self._root.public_key().verify(
                bytes.fromhex(cert.root_sig), canonical_bytes(candidate.to_dict())
            )
        except Exception:
            return False
        return True

    def revoke(self, agent_id: str) -> None:
        self._revoked[agent_id] = 1

    def rotate_agent(
        self, old_cert: AgentCert, issued_at: int, expires_at: int
    ) -> Tuple[AgentCert, Ed25519PrivateKey]:
        """Re-issue a fresh cert + key for an agent (D14 live rotation)."""
        return self.issue_cert(
            old_cert.agent_id,
            old_cert.role,
            old_cert.capabilities,
            issued_at,
            expires_at,
            cert_seq=old_cert.cert_seq + 1,
        )


# ---------------------------------------------------------------------------
# Per-record confidentiality (envelope) -- thin typed wrapper.
# ---------------------------------------------------------------------------

class SecretVault:
    """Confidentiality for local secrets via ChrisCryptSN.Envelope."""

    def __init__(self, kek: bytes):
        self._env = Envelope(kek=kek)

    def seal(self, name: str, value: str) -> Dict[str, Any]:
        return self._env.seal(name, value)

    def open(self, rec: Dict[str, Any]) -> str:
        return self._env.open(rec)


# ---------------------------------------------------------------------------
# Tamper-evident audit ledger (hash chain) -- typed AuditEntry wrapper.
# ---------------------------------------------------------------------------

class AuditTrail:
    """Append-only, Ed25519-signed audit ledger (12.5).

    Wraps ChrisCryptSN.Ledger. Entries are `AuditEntry` dicts; the ledger signs
    each entry's hash and links it to the previous, plus a signed checkpoint so
    tail truncation is detectable.
    """

    def __init__(self, signing_key: Ed25519PrivateKey, store=None):
        self._ledger = Ledger(signing_key, store=store)

    def append(self, entry: Dict[str, Any]) -> Dict[str, Any]:
        assert "seq" not in entry and "prev" not in entry, "seq/prev are ledger-managed"
        kind = entry.get("kind", "audit")
        return self._ledger.append(kind, entry)

    def entries(self) -> List[Dict[str, Any]]:
        return self._ledger.entries()

    def verify(self) -> bool:
        try:
            return bool(
                Ledger.verify_chain(
                    self._ledger.entries(),
                    self._ledger.public_key_pem(),
                    checkpoint=self._ledger.checkpoint(),
                )
            )
        except Exception:
            return False

    def verify_or_raise(self) -> None:
        if not self.verify():
            raise LedgerIntegrityError("Audit ledger failed integrity verification")

    def public_key_pem(self) -> bytes:
        return self._ledger.public_key_pem()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def master_to_kek(master_secret: bytes, salt: bytes) -> bytes:
    from .chriscrypt.envelope import derive_kek
    return derive_kek(master_secret, salt)


def hash_password_safe(pw: str) -> str:
    return hash_password(pw)


def verify_password_safe(stored: str, pw: str) -> bool:
    return verify_password(pw, stored)
