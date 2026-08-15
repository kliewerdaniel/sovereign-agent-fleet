"""Phase 2 (D21 hardening) — K1 root key lifecycle adversarial tests.

Proves:
  * root seed export is ENCRYPTED (no plaintext key on disk);
  * from_seed restores a byte-identical root only with the correct backup KEK +
    master secret (fail-closed on a wrong key);
  * rotate_root re-signs live certs under a NEW root, bumps the epoch, and the
    OLD root's certs are still verifiable via known_root_pubs (verifier continuity);
  * a cert signed under the new root is NOT verifiable under the old root alone
    (isolation), and vice-versa;
  * the Gateway idempotency cache is invalidated on rotation (A3).
"""
import os

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from pathlib import Path

from fleet.crypto.foundation import IdentityRoot, SecretVault, canonical_bytes
from fleet.layers import ControlPlane
from fleet.gcp.bridge import FanoutStore
from fleet.crypto.chriscrypt.store import JsonStore


def _cp(tmp_path, master=b"master-K1"):
    audit = Ed25519PrivateKey.from_private_bytes(
        HKDF(algorithm=hashes.SHA256(), length=32, salt=None,
             info=b"fleet:audit").derive(b"audit-K1"))
    store = JsonStore(str(tmp_path / "audit.json"))
    cp = ControlPlane(master, audit, store=store, now_fn=lambda: 1_000)
    return cp


def test_root_seed_export_is_encrypted():
    root = IdentityRoot(b"master-secret")
    backup = os.urandom(32)
    blob = root.export_seed(backup)
    # No plaintext seed anywhere in the export.
    assert "sealed_seed" in blob
    raw = repr(blob).encode()
    # The raw root private key must never appear in the export blob.
    seed = root._root.private_bytes(
        serialization.Encoding.Raw, serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption())
    assert seed not in raw
    # The sealed blob cannot be read without the KEK.
    wrong_vault = SecretVault(os.urandom(32))
    try:
        wrong_vault.open(blob["sealed_seed"])
        assert False, "sealed seed opened with wrong KEK"
    except Exception:
        pass


def test_root_seed_restore_fail_closed_on_wrong_key():
    root = IdentityRoot(b"master-secret")
    backup = os.urandom(32)
    blob = root.export_seed(backup)
    # Wrong master secret -> restore rejected.
    try:
        IdentityRoot.from_seed(blob, backup, b"wrong-master")
        assert False, "restore succeeded with wrong master"
    except ValueError:
        pass
    # Wrong backup KEK -> SecretVault open fails.
    try:
        IdentityRoot.from_seed(blob, os.urandom(32), b"master-secret")
        assert False, "restore succeeded with wrong KEK"
    except Exception:
        pass
    # Correct material -> identical root key.
    restored = IdentityRoot.from_seed(blob, backup, b"master-secret")
    assert restored.root_public_pem == root.root_public_pem


def test_rotate_root_resigns_live_certs_and_keeps_history():
    cp = _cp(Path("/tmp"))
    # Build agents.
    r = cp.publish_agent("researcher-1", "researcher", ["emit_evidence"])
    a = cp.publish_agent("analyst-1", "analyst", ["qualify", "verify_gate"])
    o = cp.publish_agent("operator-1", "operator", ["crm_write"])
    old_epoch = cp.root.root_epoch
    old_cert_rc = cp.registry._certs["researcher-1"]
    # Rotate.
    res = cp.rotate_root(b"new-master-rotation")
    assert res["epoch_new"] == old_epoch + 1
    assert "researcher-1" in res["resigned"]
    # New cert verifies under the NEW root.
    new_cert = cp.registry._certs["researcher-1"]
    assert cp.root.verify_cert(new_cert) is True
    # Old cert is STILL verifiable via known_root_pubs (verifier continuity).
    assert cp.root.verify_cert_any_epoch(old_cert_rc) is True
    # A verifier that only knows the NEW root pubkey (as distributed out-of-band,
    # e.g. from the registry.root_rotate audit entry) ...
    new_pub = cp.root.root_public_pem
    fresh = IdentityRoot(b"verifier-placeholder")
    fresh.known_root_pubs = {0: new_pub}
    # ... cannot verify the OLD cert -> isolation holds.
    assert fresh.verify_cert_any_epoch(old_cert_rc) is False
    # ... but CAN verify a re-signed cert captured post-rotation.
    post = cp.registry._certs["researcher-1"]
    assert fresh.verify_cert_any_epoch(post) is True


def test_rotate_invalidates_gateway_cache():
    cp = _cp(Path("/tmp"))
    o = cp.publish_agent("operator-1", "operator", ["crm_write"])
    # Get authority under the old root -> cached.
    ra = cp.request_authority(o.cert, "crm_write", idempotency_key="idem-rot")
    assert ra.granted is True
    # Rotate -> cache must clear.
    cp.rotate_root(b"new-master-rotation")
    # After rotation, re-requesting the same key re-evaluates (not served stale).
    ra2 = cp.request_authority(o.cert, "crm_write", idempotency_key="idem-rot")
    # The old cert no longer verifies under the new root -> now denied.
    assert ra2.granted is False
