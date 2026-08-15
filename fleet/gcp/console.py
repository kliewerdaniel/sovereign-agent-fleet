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
                 on_approve: Optional[Callable[[dict], None]] = None,
                 verify_approval=None, human_cert=None):
        self.bridge = bridge
        self._pending: List[dict] = list(pending or [])
        self._on_approve = on_approve
        # verify_approval(appr_record, human_cert, action_id, capability, artifact_hash)
        # -> bool. Provided by the Control Plane (fleet.layers.approval). If None,
        # the console cannot perform server-side verification and must reject
        # (fail-closed) — it never echoes an unverifiable approval (G2).
        self._verify = verify_approval
        # Device-bound approver identity (D17). In production this is the live
        # human cert served by the runtime; the console binds verification to it.
        self._human_cert = human_cert
        self._audit: List[dict] = []

    def queue(self, action: dict) -> None:
        """Runtime pushes a pending consequential action for human review."""
        self._pending.append(action)

    def pending(self) -> List[dict]:
        return list(self._pending)

    def _assess_posted_approval(self, req: dict) -> tuple:
        """Server-side gate for a posted approval (G2). Returns (ok, reason).

        Fail-closed: if the console has no verifier or human cert bound, or the
        posted ApprovalRecord fails cryptographic verification bound to the exact
        pending action, the approval is rejected — never silently forwarded.
        """
        if self._verify is None or self._human_cert is None:
            return False, "console has no verification binding (fail-closed)"
        action_id = req.get("action_id")
        action = next((a for a in self._pending if a.get("action_id") == action_id), None)
        if action is None:
            return False, "no matching pending action"
        ok = self._verify(
            req, self._human_cert,
            action_id,
            action.get("capability", ""),
            action.get("artifact_hash", ""),
        )
        if not ok:
            return False, "human signature invalid or mis-bound to action"
        return True, "verified"

    def audit_log(self) -> List[dict]:
        return list(self._audit)

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
            action.get("capability", ""), action.get("artifact_hash", ""),
            decision, reason,
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
                # G2: the console is NOT a pass-through. A posted approval must
                # carry a cryptographically-verifiable human_sig bound to the
                # pending action; otherwise it is rejected (fail-closed) and a
                # loud audit event is recorded. It never merely echoes the body.
                verdict, why = self._assess_posted_approval(req)
                if not verdict:
                    self._audit.append({
                        "kind": "console.unverified_approval_rejected",
                        "why": why,
                        "action_id": req.get("action_id"),
                    })
                    body = json.dumps({
                        "accepted": False,
                        "reason": why,
                    }).encode()
                    start_response("403 Forbidden",
                                   [("Content-Type", "application/json")])
                    return [body]
                self._audit.append({
                    "kind": "console.approval_verified",
                    "action_id": req.get("action_id"),
                })
                body = json.dumps({"accepted": True}).encode()
                start_response("200 OK", [("Content-Type", "application/json")])
                return [body]
            start_response("404 Not Found", [("Content-Type", "text/plain")])
            return [b"not found"]
        except Exception as e:  # pragma: no cover - defensive
            start_response("500 Internal Server Error", [("Content-Type", "text/plain")])
            return [str(e).encode()]
