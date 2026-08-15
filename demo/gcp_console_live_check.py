"""D5/D6 live Cloud Run console check: POST a human-signed approval envelope to
the deployed fleet-approval-console and confirm fail-closed behavior.

The running console has no queued action, so a well-formed but unbound (or
mis-bound) ApprovalRecord must return 403. A cryptographically valid signature
bound to a queued action would return 200 (demonstrated locally in
gcp_live_proof.py).
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.request

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from fleet.crypto.foundation import IdentityRoot, AgentCert
from fleet.layers import Approval

URL = os.environ.get("CONSOLE_URL",
                     "https://fleet-approval-console-85569899488.us-central1.run.app")
PROJECT = os.environ.get("FLEET_PROJECT", "project-3ba93cec-8ca6-43c0-ba4")


def _human():
    master = b"gcp-live-proof-master"
    root = IdentityRoot(master)
    now = int(time.time())
    cert, key = root.issue_cert("human-1", "human", ["approve_deny"],
                                issued_at=now, expires_at=now + 86400)
    return cert, key


def post(path, body):
    data = json.dumps(body).encode()
    req = urllib.request.Request(URL + path, data=data,
                                 headers={"Content-Type": "application/json"},
                                 method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode())


def main():
    cert, key = _human()
    # A valid-signature approval bound to an action the console has NOT queued.
    ap = Approval.sign(cert, key, "operator-1", "no-such-action", "outreach_send",
                       "deadbeef", "approve", "live test", int(time.time()))
    status, resp = post("/approve", ap.__dict__)
    print(f"POST /approve (unbound valid-sig) -> {status} {resp}")
    ok = status == 403
    print(f"fail-closed on live Cloud Run console: {'YES' if ok else 'NO (BUG)'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
