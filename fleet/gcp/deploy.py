"""Cloud Run deployment entrypoint (13.3): serves the D17 approval console.

The runtime + gateway are deterministic local-first infrastructure (D9). Cloud
Run hosts the *human approval console* (D17) and the verifiable artifact mirror
(13.3) — it never holds the root key or signs artifacts. The console posts a
human-signed ApprovalRecord back to the local runtime over the registered
callback (D3/D6: authority stays local).

Run with: `gunicorn fleet.gcp.deploy:app` (or any WSGI server). The WSGI app is
built from stdlib so it works without Flask; gunicorn is the only deploy dep.
"""
from __future__ import annotations

from fleet.gcp.bridge import GcpBridge
from fleet.gcp.console import ApprovalConsole

# A Cloud Run instance serves the approval console backed by a local-mode bridge
# (the live Firestore copy is read by the 14.8 verifier; the console only needs
# the pending-action queue + signature collection).
_bridge = GcpBridge(mode="local")
_console = _bridge.serve_console()
app = _console.wsgi_app


def build_app(bridge: GcpBridge, console: ApprovalConsole):
    """Construct the WSGI app for a given bridge/console (testable offline)."""
    return console.wsgi_app
