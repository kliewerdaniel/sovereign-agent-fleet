"""Sovereign Agent Fleet — frontend bridge.

FastAPI surface over the REAL fleet package:

  REST
    GET  /api/health
    GET  /api/runs                      # run index (last snapshot per run_id)
    GET  /api/runs/{run_id}/state       # full run snapshot (resync/backfill)
    GET  /api/chain/integrity           # server-computed trust state
    GET  /api/audit?limit=50            # signed chain tail + integrity verdict
    GET  /api/run/{domain}              # run a fresh incident pipeline (sync)
    POST /api/approve/{request_id}/sign # produce a genuine Ed25519 ApprovalRecord

  WebSocket
    /ws                                  # streams typed PipelineEvents as the
                                         # fleet audit ledger grows

The Next.js client calls REST for reads/signing and subscribes to /ws for
live stage progression. No fleet record fields are invented here.
"""
from __future__ import annotations

import asyncio
import json
import os
import secrets
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .fleet_adapter import FleetAdapter
from .schema import AuditEntry, PipelineEvent

# One adapter per process (in-memory ledger; would be per-session in prod).
MASTER = os.environ.get("FLEET_MASTER", "fleet-bridge-master").encode()
AUDIT_SEED = os.environ.get("FLEET_AUDIT_SEED", "fleet-bridge-audit").encode()
adapter = FleetAdapter(MASTER, AUDIT_SEED)

app = FastAPI(title="Sovereign Agent Fleet Bridge", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("FLEET_CORS_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- live subscribers -------------------------------------------------------
_subscribers: List[WebSocket] = []
_runs: Dict[str, Dict[str, Any]] = {}  # run_id -> last result snapshot


async def _broadcast(event: PipelineEvent) -> None:
    dead = []
    payload = json.dumps(event.model_dump(mode="json"), default=str)
    for ws in _subscribers:
        try:
            await ws.send_text(payload)
        except Exception:
            dead.append(ws)
    for ws in dead:
        _subscribers.remove(ws)


# --- REST -------------------------------------------------------------------
@app.get("/api/health")
async def health():
    return {"status": "ok", "audit_entries": len(adapter.audit_entries())}


@app.get("/api/chain/integrity")
async def chain_integrity():
    """Server-computed trust state (fail-closed). The banner renders this
    verbatim — the client never verifies crypto itself."""
    return adapter.chain_integrity()


# Sync wrapper so the (sync) fleet adapter can enqueue live WS broadcasts
# on the running event loop without awaiting.
def _emit(event: PipelineEvent) -> None:
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_broadcast(event))
    except RuntimeError:
        pass  # no loop (e.g. imported outside server) — events still land in _runs


@app.get("/api/audit")
async def audit(limit: int = 50):
    entries = adapter.audit_tail(limit=limit)
    return {
        "entries": [e.model_dump(mode="json") for e in entries],
        "count": len(entries),
        "ledger_pubkey_pem": adapter.cp.audit.public_key_pem().decode("utf-8"),
    }


@app.get("/api/runs")
async def list_runs():
    """Run index (bridge process memory). Each entry is the last snapshot from
    a /api/run/incident call — real fleet output, no fabrication."""
    return {
        "run_ids": list(_runs.keys()),
        "runs": {
            rid: {
                "run_id": r["run_id"],
                "verification": r["verification"],
                "authorization": r["authorization"],
                "needs_approval": r["needs_approval"],
                "blocked": r["blocked"],
                "target": r["target"],
                "action": r["action"],
                "audit_count": len(r.get("audit_tail", [])),
            }
            for rid, r in _runs.items()
        },
    }


@app.get("/api/runs/{run_id}/state")
async def run_state(run_id: str):
    """Full run snapshot (real fleet output stored from the last /api/run/incident
    call). Used by the Next.js detail page and WS reconnect/backfill."""
    result = _runs.get(run_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"unknown run {run_id}")
    return result


@app.get("/api/runs/by-action/{action_id}")
async def run_by_action(action_id: str):
    """Resolve a run by its operator action idempotency key (the same value the
    detail page uses as the approval request id). Returns the run snapshot plus
    the operator/human cert identities needed to render the D17 sign page."""
    for r in _runs.values():
        if r.get("action_id") == action_id:
            return {
                "run": r,
                "operator": {"agent_id": adapter.operator.agent_id},
                "human": {"agent_id": adapter.human.agent_id},
            }
    raise HTTPException(status_code=404, detail=f"no run for action_id {action_id}")


@app.get("/api/run/{domain}")
async def run_pipeline(domain: str, verification: str = "VERIFIED", severity: str = "LOW",
                       workload_id: str = "web-edge", action: str = "block_egress"):
    if domain != "incident":
        raise HTTPException(status_code=400, detail="only 'incident' domain wired in Phase 0")
    result = adapter.run_incident(
        _emit, verification=verification, severity=severity,
        workload_id=workload_id, action=action,
    )
    _runs[result["run_id"]] = result
    return result


class SignRequest(BaseModel):
    agent_id: str
    action_id: str
    capability: str
    artifact_hash: str
    decision: str = "approve"
    reason: str = "human approved via bridge"


@app.post("/api/approve/{request_id}/sign")
async def sign_approval(request_id: str, body: SignRequest):
    approval = adapter.sign_approval(
        request_id, body.agent_id, body.action_id, body.capability,
        body.artifact_hash, body.decision, body.reason,
    )
    # Broadcast the ApprovalSigned event so the client advances the stage.
    from .schema import ApprovalSigned
    await _broadcast(ApprovalSigned(
        run_id="", request_id=request_id, approval=approval  # type: ignore[call-arg]
    ))
    return approval.model_dump(mode="json")


# --- WebSocket --------------------------------------------------------------
@app.websocket("/ws")
async def ws(ws: WebSocket):
    await ws.accept()
    _subscribers.append(ws)
    try:
        while True:
            # Client may send a resync ping; we reply with current audit tail.
            msg = await ws.receive_text()
            try:
                data = json.loads(msg)
            except Exception:
                data = {}
            if data.get("type") == "resync":
                for e in adapter.audit_tail(limit=20):
                    await ws.send_text(json.dumps(
                        {"type": "AuditEntryAppended", "run_id": "", "entry": e.model_dump(mode="json")},
                        default=str,
                    ))
    except WebSocketDisconnect:
        pass
    finally:
        if ws in _subscribers:
            _subscribers.remove(ws)
