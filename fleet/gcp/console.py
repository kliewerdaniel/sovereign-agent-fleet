"""D17 Cloud Run approval console -- minimal stdlib WSGI (no Flask dependency).

Runs on Cloud Run as the human-in-the-loop approval surface. It never holds
authority: it only renders pending consequential actions and submits a
human-signed ``ApprovalRecord`` back to the local runtime over a callback. The
console is a display + signature-collection shell around the deterministic
Control Plane; the decision still lives locally (D3/D6).

Testable offline: ``wsgi_app(environ, start_response)`` is a plain WSGI app.
"""
from __future__ import annotations

import json
from typing import Any, Callable, Dict, List, Optional


class ApprovalConsole:
    def __init__(self, bridge, pending: Optional[List[dict]] = None,
                 on_approve: Optional[Callable[[dict], None]] = None):
        self.bridge = bridge
        self._pending: List[dict] = list(pending or [])
        self._on_approve = on_approve

    def queue(self, action: dict) -> None:
        """Runtime pushes a pending consequential action for human review."""
        self._pending.append(action)

    def pending(self) -> List[dict]:
        return list(self._pending)

    def approve(self, action_id: str, decision: str, reason: str,
                human_cert, human_key) -> Dict[str, Any]:
        """Collect a human Ed25519-signed ApprovalRecord (D17)."""
        from fleet.layers import Approval

        action = next((a for a in self._pending if a.get("action_id") == action_id), None)
        if action is None:
            raise KeyError(f"unknown action_id: {action_id}")
        ap = Approval.sign(
            human_cert, human_key,
            action.get("agent_id", ""), action_id,
            action.get("artifact_hash", ""), decision, reason,
            int(action.get("ts", 0)),
        )
        self._pending = [a for a in self._pending if a.get("action_id") != action_id]
        if self._on_approve:
            self._on_approve(ap.__dict__)
        return ap.__dict__

    # -- WSGI surface (Cloud Run) ------------------------------------------
    def wsgi_app(self, environ, start_response):
        method = environ.get("REQUEST_METHOD", "GET")
        path = environ.get("PATH_INFO", "/")
        try:
            if method == "GET" and path == "/pending":
                body = json.dumps({"pending": self.pending()}).encode()
                start_response("200 OK", [("Content-Type", "application/json")])
                return [body]
            if method == "POST" and path == "/approve":
                size = int(environ.get("CONTENT_LENGTH") or 0)
                raw = environ["wsgi.input"].read(size) if size else b"{}"
                req = json.loads(raw or b"{}")
                # In production, human_cert/human_key come from the device-bound
                # approver session (D17); for the deployed shell this is wired by
                # the runtime serving the console.
                body = json.dumps({"received": req}).encode()
                start_response("200 OK", [("Content-Type", "application/json")])
                return [body]
            start_response("404 Not Found", [("Content-Type", "text/plain")])
            return [b"not found"]
        except Exception as e:  # pragma: no cover - defensive
            start_response("500 Internal Server Error", [("Content-Type", "text/plain")])
            return [str(e).encode()]
