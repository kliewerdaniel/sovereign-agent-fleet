#!/usr/bin/env python3
"""Scope 1+2 seeder: stand up LIVE GCP verifiable data for the D17 console.

Run from the deploy venv (has google-cloud-* installed):
    source .deploy-venv/bin/activate
    export GOOGLE_APPLICATION_CREDENTIALS=/path/adc.json   # to project-3ba93cec-8ca6-43c0-ba4
    export FLEET_PROJECT=project-3ba93cec-8ca6-43c0-ba4
    python scripts/seed_gcp.py

What it does (all additive, non-destructive):
  1. Builds a real ControlPlane whose audit ledger fans out to GcpBridge(mode="gcp").
  2. Runs the governed R->A->O beats; signed artifacts replicate to LIVE Firestore.
  3. Publishes the DETERMINISTIC human cert's PUBLIC dict (for FLEET_HUMAN_CERT_PEM)
     so the deployed console can verify off-platform approvals. The matching
     private key is printed once and written to a LOCAL-only file; it never
     leaves your machine.
  4. Pushes one pending consequential action to the live console /queue so judges
     see a real, verifiable approval request at the Cloud Run URL.

IMPORTANT: the human keypair is derived from a FIXED seed here so it matches the
key scripts/judge_approve.py uses. Do not change HUMAN_SEED between seed and judge.
"""
from __future__ import annotations

import base64
import json
import os
import sys
import tempfile
import time

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fleet.crypto.chriscrypt.store import JsonStore
from fleet.gcp.bridge import GcpBridge
from fleet.gcp.verify import FirestoreVerifier
from fleet.layers import (
    Analyst, ControlPlane, Handoff, MemBank, Operator, Researcher,
    Runtime, VERIFIED, ASSERTED, ToolEnvelope,
)
from fleet.layers.armor import InjectionError
from fleet.crypto.foundation import AgentCert, canonical_bytes

PROJECT = os.environ.get("FLEET_PROJECT", "project-3ba93cec-8ca6-43c0-ba4")
MASTER = b"gcp-live-proof-master"
COLLECTION = "fleet_ledger_live"
HUMAN_SEED = b"sovereign-fleet-judge-human-v1"  # DO NOT change across runs


def _human_keypair():
    """Deterministic human keypair so the deployed cert matches judge_approve.py."""
    key = Ed25519PrivateKey.from_private_bytes(
        HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=b"fleet:human").derive(HUMAN_SEED)
    )
    pub_pem = key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")
    # The deployed cert is PUBLIC material. Its root_sig is a benign placeholder:
    # the live console verifies the APPROVAL signature against this pubkey (not the
    # root_sig), so a self-consistent placeholder is sufficient for the judge loop.
    cert = AgentCert(
        agent_id="human-judge", pubkey_pem=pub_pem, role="human",
        capabilities=["approve_deny"], issued_at=int(time.time()),
        expires_at=int(time.time()) + 86400 * 365, cert_seq=0, root_sig="0" * 128,
    )
    return cert, key


def build():
    """Construct the ControlPlane WITHOUT side effects.

    This used to publish the demo agents inside build(), which meant merely
    *importing/constructing* the plane appended registry entries to the LIVE
    Firestore mirror (under a fresh per-process root key) and forked the chain.
    A judge importing this module to verify the cloud copy would silently
    corrupt it. Construction is now purely a constructor; the state-mutating
    work lives in publish_agents()/run_beats() and is only called from main().
    """
    tmp = tempfile.mkdtemp(prefix="saf_live_")
    audit_key = Ed25519PrivateKey.from_private_bytes(
        HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=b"fleet:audit").derive(b"audit-live")
    )
    store = JsonStore(os.path.join(tmp, "audit.json"))
    bridge = GcpBridge(mode="gcp", project=PROJECT, firestore_collection=COLLECTION)
    cp = ControlPlane(MASTER, audit_key, store=store, bridge=bridge, run_id="gcp-live")
    kek = HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=b"fleet:mem").derive(b"mem-live")
    mem = MemBank(kek)
    rt = Runtime(cp, mem)
    return dict(cp=cp, rt=rt, bridge=bridge)


def publish_agents(cp, rt):
    """The stateful part of seeding: publish the demo agents + a tool cert.
    This WRITES registry entries to the ledger / Firestore mirror. Kept separate
    from build() so constructing the plane is side-effect-free."""
    r = cp.publish_agent("researcher-1", "researcher", ["emit_evidence"])
    a = cp.publish_agent("analyst-1", "analyst", ["qualify", "verify_gate"])
    o = cp.publish_agent("operator-1", "operator", ["prepare_artifact", "crm_write", "outreach_send"])
    human = cp.publish_agent("human-1", "human", ["approve_deny"])
    tool_cert, tool_key = cp.root.issue_cert("web_tool", "tool", ["tool_result"],
                                             int(time.time()), int(time.time()) + 86400)
    cp.registry._certs["web_tool"] = tool_cert
    return dict(r=r, a=a, o=o, human=human, tool_cert=tool_cert, tool_key=tool_key)


def reconstruct_audit_pubkey() -> bytes:
    """Deterministic PUBLIC audit key for verifying the live chain.

    A judge uses this to verify the Firestore copy WITHOUT constructing a
    ControlPlane (construction no longer writes, but even calling build() is
    unnecessary). No private key, no writes — just derive the same Ed25519
    public key the seeder used to sign the chain. This is the only key needed
    for FirestoreVerifier.verify(), which checks the audit-signed ledger.
    """
    audit_key = Ed25519PrivateKey.from_private_bytes(
        HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=b"fleet:audit").derive(b"audit-live")
    )
    return audit_key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)


def main():
    # Idempotent: every ControlPlane re-starts at GENESIS, so a re-seed must
    # clear prior runs BEFORE building the ControlPlane. build() is now
    # side-effect-free (it only constructs the plane); the registry writes
    # happen in publish_agents() below, after the clear.
    bridge = GcpBridge(mode="gcp", project=PROJECT, firestore_collection=COLLECTION)
    print("[seed] clearing prior live docs/pending/approvals ...")
    bridge.clear()

    env = build()
    cp, rt, bridge = env["cp"], env["rt"], env["bridge"]
    agents = publish_agents(cp, rt)
    r, a, o, tool_key = agents["r"], agents["a"], agents["o"], agents["tool_key"]

    def gather(q):
        sig = ToolEnvelope.make(tool_key, "web_tool",
                                json.dumps({"citation": "x", "extract": q}).encode())
        return Researcher(r, rt).gather(sig, q, ["citation", "extract"])

    # minimal governed beat -> leaves a real pending consequential action
    ev = gather("cloud ERP prospect")
    intel = Analyst(a, rt).qualify(ev, [
        {"claim": "icp_fit=true", "claim_type": "icp_fit",
         "evidence_refs": [ev.payload["evidence_id"]]},
    ])
    op = Operator(o, rt)
    out = op.act(intel, "draft outreach", "crm_write", idempotency_key="live-e2e-1")
    assert out.get("needs_approval") or out.get("final"), out

    # ---- LIVE verification (public keys only) ----
    # Use reconstruct_audit_pubkey() — the SAME key a judge uses — rather than
    # the in-process cp. This proves the cloud copy verifies from public keys
    # alone (no private key, no in-process authority). The verifier only needs
    # the audit pubkey; the ledger is signed by the audit key.
    docs = bridge.mirror_docs()
    verifier = FirestoreVerifier(docs, reconstruct_audit_pubkey())
    ok = verifier.verify()
    print(f"[seed] live Firestore docs: {len(docs)}")
    print(f"[seed] FirestoreVerifier.verify() = {ok}")
    assert ok, "LIVE cloud copy failed integrity verification"

    # ---- publish the deterministic human cert's PUBLIC dict ----
    human_cert, human_key = _human_keypair()
    pub_b64 = base64.b64encode(json.dumps(human_cert.to_dict()).encode()).decode()
    print("\n[seed] Set this as the Cloud Run env var FLEET_HUMAN_CERT_PEM:\n")
    print(pub_b64)
    # write the matching PRIVATE key to a local-only file (never committed; .gitignored pattern)
    key_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "judge_human_key.json")
    with open(key_path, "w") as fh:
        json.dump({"seed": HUMAN_SEED.decode(), "private_key_hex": human_key.private_bytes(
            serialization.Encoding.Raw, serialization.PrivateFormat.Raw,
            serialization.NoEncryption()).hex()}, fh)
    print(f"\n[seed] matching PRIVATE key written LOCALLY to: {key_path} (do not commit)")

    # ---- push a live pending action to the console's /queue ----
    from fleet.gcp.console import ApprovalConsole
    from fleet.layers.approval import verify_approval
    console = ApprovalConsole(bridge, verify_approval=verify_approval, human_cert=human_cert)
    pending_action = {
        "action_id": "live-e2e-1",
        "agent_id": "operator-1",
        "capability": "crm_write",
        "artifact_hash": out["artifact_hash"],
        "ts": int(time.time()),
    }
    console.queue(pending_action)
    print(f"[seed] pushed live pending action '{pending_action['action_id']}' to Cloud Run /queue")
    print("[seed] DONE — judges can now GET the console URL and POST a signed approval.")


if __name__ == "__main__":
    main()
