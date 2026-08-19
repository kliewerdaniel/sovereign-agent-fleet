#!/usr/bin/env python3
"""Scope 2 judge loop: sign a human ApprovalRecord off-platform, POST to Cloud Run.

This is the human-in-the-loop action a judge performs against the LIVE console.
The private key is derived from the SAME HUMAN_SEED used by scripts/seed_gcp.py,
so the signature verifies under the cert deployed in FLEET_HUMAN_CERT_PEM.

Run:
    source .deploy-venv/bin/activate
    export CONSOLE_URL=https://<your-cloud-run-url>   # printed by deploy_gcp.sh
    export FLEET_PROJECT=project-3ba93cec-8ca6-43c0-ba4
    python scripts/judge_approve.py --action-id live-e2e-1 --approve

It fetches the pending action from GET {CONSOLE_URL}/pending, signs an approval
bound to the EXACT action_id/capability/artifact_hash, and POSTs to /approve.
The console verifies it with only the human public cert (fail-closed).
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import time

import requests
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fleet.crypto.foundation import canonical_bytes

HUMAN_SEED = b"sovereign-fleet-judge-human-v1"  # MUST match seed_gcp.py


def _human_key():
    return Ed25519PrivateKey.from_private_bytes(
        HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=b"fleet:human").derive(HUMAN_SEED)
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--console-url", default=os.environ.get("CONSOLE_URL", ""))
    ap.add_argument("--action-id", default="live-e2e-1")
    ap.add_argument("--decision", default="approve", choices=["approve", "deny"])
    ap.add_argument("--reason", default="judge-reviewed")
    args = ap.parse_args()
    if not args.console_url:
        sys.exit("set --console-url or CONSOLE_URL env")

    base = args.console_url.rstrip("/")
    resp = requests.get(f"{base}/pending", timeout=15)
    resp.raise_for_status()
    pending = {p["action_id"]: p for p in resp.json().get("pending", [])}
    if args.action_id not in pending:
        sys.exit(f"action {args.action_id} not in pending queue: {list(pending)}")
    action = pending[args.action_id]
    ts = int(time.time())

    # Build the approval body exactly as fleet.layers.runtime.Approval.sign does,
    # then sign with the deterministic human key. The console re-verifies the
    # same canonical body against the deployed public cert (fail-closed).
    body = canonical_bytes({
        "approval_id": "",
        "agent_id": action.get("agent_id", ""),
        "action_id": action["action_id"],
        "capability": action.get("capability", ""),
        "artifact_hash": action.get("artifact_hash", ""),
        "decision": args.decision,
        "reason": args.reason,
        "human_id": "human-judge",
        "ts": ts,
    })
    key = _human_key()
    human_sig = key.sign(body).hex()

    rec = {
        "approval_id": "",
        "agent_id": action.get("agent_id", ""),
        "action_id": action["action_id"],
        "capability": action.get("capability", ""),
        "artifact_hash": action.get("artifact_hash", ""),
        "decision": args.decision,
        "reason": args.reason,
        "human_id": "human-judge",
        "human_sig": human_sig,
        "ts": ts,
    }
    r = requests.post(f"{base}/approve", json=rec, timeout=15)
    print(f"POST /approve -> {r.status_code} {r.text}")
    if r.status_code == 200 and r.json().get("accepted"):
        print("\nAPPROVAL ACCEPTED by the live console (fail-closed verify passed).")
    else:
        sys.exit("approval was REJECTED by the console (fail-closed) — see reason above.")


if __name__ == "__main__":
    main()
