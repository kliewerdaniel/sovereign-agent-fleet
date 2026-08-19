"""Cloud Run deployment entrypoint (13.3): serves the D17 approval console.

The runtime + gateway are deterministic local-first infrastructure (D9). Cloud
Run hosts the *human approval console* (D17) and the verifiable artifact mirror
(13.3) -- it never holds the root key or signs artifacts. The console posts a
human-signed ApprovalRecord back to the local runtime over the registered
callback (D3/D6: authority stays local).

Runtime configuration (env):
  FLEET_MODE            "gcp" | "local"   (default "local" -- set "gcp" in prod)
  FLEET_PROJECT         GCP project id    (default "project-3ba93cec-8ca6-43c0-ba4")
  FLEET_HUMAN_CERT_PEM  public AgentCert PEM (human approver) -- OPTIONAL.
                        The console only ever VERIFIES against this public key;
                        it never holds the human private key (fail-closed: with
                        no cert it rejects every approval). Signing happens in
                        the local runtime that calls the console.

Run with: `gunicorn fleet.gcp.deploy:app` (or any WSGI server). The WSGI app is
built from stdlib so it works without Flask; gunicorn is the only deploy dep.
"""
from __future__ import annotations

import json
import os

from fleet.crypto.foundation import AgentCert
from fleet.gcp.bridge import GcpBridge
from fleet.gcp.console import ApprovalConsole
from fleet.layers.approval import verify_approval

_DEFAULT_PROJECT = "project-3ba93cec-8ca6-43c0-ba4"

# A Cloud Run instance serves the approval console. The bridge mirrors signed
# artifacts to Firestore (mode="gcp") or keeps them via the local mirror
# (mode="local"); the 14.8 verifier reads the same schema either way.
_mode = os.environ.get("FLEET_MODE", "local")
_project = os.environ.get("FLEET_PROJECT", _DEFAULT_PROJECT)
_bridge = GcpBridge(mode=_mode, project=_project)

# The console binds verify_approval (public-key verify) and, if supplied, the
# human approver's PUBLIC cert. No private key crosses here -- a Cloud Run
# instance can verify a human signature but can never forge one (G2).
#
# The human cert is PUBLIC material. At deploy time the seeder (scripts/seed_gcp.py)
# writes a deterministic human cert's PUBLIC dict into FLEET_HUMAN_CERT_PEM so the
# console can verify approvals signed off-platform by the matching private key
# (scripts/judge_approve.py). The private key never leaves the operator's machine.
_human_cert = None
_pem = os.environ.get("FLEET_HUMAN_CERT_PEM")
if _pem:
    try:
        import base64

        _pem = base64.b64decode(_pem).decode("utf-8") if _pem.strip().startswith("ey") else _pem
        _human_cert = AgentCert.from_dict(json.loads(_pem))
    except Exception as exc:  # fail closed: no cert -> console rejects all approvals
        import sys

        print(f"[deploy] WARNING: could not parse FLEET_HUMAN_CERT_PEM: {exc}; "
              f"console will fail closed (reject all approvals)", file=sys.stderr)
        _human_cert = None

_console = ApprovalConsole(
    _bridge,
    verify_approval=verify_approval,
    human_cert=_human_cert,
)
app = _console.wsgi_app


def build_app(bridge: GcpBridge, console: ApprovalConsole):
    """Construct the WSGI app for a given bridge/console (testable offline)."""
    return console.wsgi_app

