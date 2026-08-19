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
        # Seed the in-memory queue from the bridge (local mirror OR live
        # Firestore) so the queue survives Cloud Run instance restarts.
        self._pending: List[dict] = list(pending or []) or bridge.pending_actions()
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

    # -- REST queue (the runtime pushes pending consequential actions here) --
    def queue(self, action: dict) -> None:
        """Runtime pushes a pending consequential action for human review."""
        self._pending.append(action)
        # persist so it is visible on any Cloud Run instance (and survives restarts)
        try:
            self.bridge.enqueue_pending(action)
        except Exception as exc:  # pragma: no cover - defensive; never mask GCP errors in logs
            import sys
            print(f"[console] WARN: enqueue_pending failed: {exc}", file=sys.stderr)

    def pending(self) -> List[dict]:
        # Always sync from the bridge (the source of truth across instances).
        # Note: an empty list is a valid state (all actions approved), so we
        # assign unconditionally rather than guarding on truthiness.
        self._pending = self.bridge.pending_actions()
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
        action = next((a for a in self.pending() if a.get("action_id") == action_id), None)
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

        action = next((a for a in self.pending() if a.get("action_id") == action_id), None)
        if action is None:
            raise KeyError(f"unknown action_id: {action_id}")
        ap = Approval.sign(
            human_cert, human_key,
            action.get("agent_id", ""), action_id,
            action.get("capability", ""), action.get("artifact_hash", ""),
            decision, reason,
            int(action.get("ts", 0)),
        )
        self._pending = [a for a in self.pending() if a.get("action_id") != action_id]
        # remove from the bridge-backed source so it disappears on every instance
        try:
            self.bridge.consume_pending(action_id)
        except Exception as exc:  # pragma: no cover - defensive
            import sys
            print(f"[console] WARN: consume_pending failed: {exc}", file=sys.stderr)
        # persist the verifiable approval record (public-key-checkable later)
        try:
            self.bridge.record_approval(ap.__dict__)
        except Exception as exc:  # pragma: no cover - defensive
            import sys
            print(f"[console] WARN: record_approval failed: {exc}", file=sys.stderr)
        if self._on_approve:
            self._on_approve(ap.__dict__)
        return ap.__dict__

    # -- WSGI surface (Cloud Run) ------------------------------------------
    def wsgi_app(self, environ, start_response):
        method = environ.get("REQUEST_METHOD", "GET")
        path = environ.get("PATH_INFO", "/")
        try:
            if method == "GET" and path in ("/", "/pending"):
                if path == "/pending" or "text/html" not in (environ.get("HTTP_ACCEPT") or ""):
                    body = json.dumps({"pending": self.pending()}).encode()
                    start_response("200 OK", [("Content-Type", "application/json")])
                    return [body]
                # human-friendly live view at GET /
                return self._serve_html(environ, start_response)
            if method == "POST" and path == "/queue":
                size = int(environ.get("CONTENT_LENGTH") or 0)
                raw = environ["wsgi.input"].read(size) if size else b"{}"
                action = json.loads(raw or b"{}")
                if not action.get("action_id"):
                    body = json.dumps({"accepted": False, "reason": "action_id required"}).encode()
                    start_response("400 Bad Request", [("Content-Type", "application/json")])
                    return [body]
                self.queue(action)
                body = json.dumps({"accepted": True, "action_id": action.get("action_id")}).encode()
                start_response("202 Accepted", [("Content-Type", "application/json")])
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
                # The judge signed this record off-platform (human_sig present and
                # verified). Persist the VERIFIABLE record to the bridge so it is
                # reconstructable from public keys later (GCP holds data, not auth).
                # The console never re-signs (it holds no private key).
                try:
                    self.bridge.record_approval(req)
                    self.bridge.consume_pending(req.get("action_id"))
                except Exception as exc:  # pragma: no cover - defensive
                    import sys
                    print(f"[console] WARN: persist approval failed: {exc}", file=sys.stderr)
                body = json.dumps({"accepted": True}).encode()
                start_response("200 OK", [("Content-Type", "application/json")])
                return [body]
            start_response("404 Not Found", [("Content-Type", "text/plain")])
            return [b"not found"]
        except Exception as e:  # pragma: no cover - defensive
            start_response("500 Internal Server Error", [("Content-Type", "text/plain")])
            return [str(e).encode()]

    # -- minimal live HTML view (judge-facing, no framework) ----------------
    def _serve_html(self, environ, start_response):
        rows = []
        for a in self.pending():
            rows.append(
                "<tr><td>{aid}</td><td>{agent}</td><td>{cap}</td>"
                "<td><code>{h}</code></td></tr>".format(
                    aid=a.get("action_id", ""), agent=a.get("agent_id", ""),
                    cap=a.get("capability", ""), h=a.get("artifact_hash", "")[:16],
                )
            )
        # NOTE: build with .replace(), NOT str.format() — the template contains
        # literal CSS braces ({font-family:...}) which str.format() would try to
        # interpret as field references and raise KeyError (and surface a bare
        # "'font-family'" 500 body). .replace() leaves the CSS braces untouched.
        rows_html = "".join(rows) or "<tr><td colspan=4><em>no pending actions</em></td></tr>"
        html = (
            "<!doctype html><html><head><meta charset='utf-8'>"
            "<title>Sovereign Fleet — D17 Approval Console</title>"
            "<style>body{font-family:system-ui,sans-serif;background:#0c0f14;color:#e8eef6;"
            "padding:2rem}table{border-collapse:collapse;width:100%}td,th{border:1px solid #243;"
            "padding:.5rem;text-align:left}code{color:#7fd1ff}h1{font-weight:600}</style></head>"
            "<body><h1>Sovereign Agent Fleet — D17 Human Approval Console</h1>"
            "<p>Live Cloud Run instance. Pending consequential actions require a "
            "human-signed <code>ApprovalRecord</code> bound to the exact action "
            "(fail-closed). The queue is backed by Firestore — it is verifiable "
            "DATA, not authority.</p>"
            "<h2>Pending actions</h2>"
            "<table><tr><th>action_id</th><th>agent</th><th>capability</th>"
            "<th>artifact_hash</th></tr>{rows}</table>"
            "<p><small>Console holds only public keys; it cannot forge approvals. "
            "Sign off-platform via the published human cert.</small></p>"
            "</body></html>"
        ).replace("{rows}", rows_html)
        start_response("200 OK", [("Content-Type", "text/html; charset=utf-8")])
        return [html.encode("utf-8")]
