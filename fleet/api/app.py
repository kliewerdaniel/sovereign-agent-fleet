"""FastAPI control-plane API for the Sovereign Agent Fleet front end.

Phase 1 of the build prompt. Thin read wrappers over the real fleet control
plane (fleet.layers / fleet.crypto) plus write endpoints that call the
EXISTING signing/approval flow (D17 Approval.sign) — no reimplemented crypto.

Nothing here computes policy or signs anything itself: it asks the control
plane and serializes the result (see schema.py).
"""
from __future__ import annotations

import asyncio
import json
import secrets
import time
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from . import beats
from .runtime import get_fleet
from .schema import (
    AgentsSnapshot,
    ApprovalResult,
    AuditEntry,
    BeatListEntry,
    BeatResult,
    ChainIntegrity,
    DecideRequest,
    Health,
    LedgerPage,
    PendingApproval,
    PolicyLog,
    RunRequest,
    RunResult,
    VerificationLog,
)

app = FastAPI(title="Sovereign Agent Fleet API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # demo front end; tighten in production
    allow_methods=["*"],
    allow_headers=["*"],
)


def _proj_entries(raw: List[Dict[str, Any]]) -> List[AuditEntry]:
    return [AuditEntry(**{k: v for k, v in e.items() if k in AuditEntry.model_fields})
            for e in raw]


@app.get("/health", response_model=Health)
def health():
    return Health()


@app.get("/agents", response_model=AgentsSnapshot)
def agents():
    snap = get_fleet().agents_snapshot()
    return AgentsSnapshot(**snap)


@app.get("/ledger", response_model=LedgerPage)
def ledger(
    since: Optional[str] = Query(None, description="cursor (entry id) to fetch after"),
    limit: int = Query(50, ge=1, le=500),
):
    page = get_fleet().ledger_page(since=since, limit=limit)
    return LedgerPage(
        entries=_proj_entries(page["entries"]),
        next_cursor=page["next_cursor"],
        head=page["head"],
        entry_count=page["entry_count"],
        chain_valid=page["chain_valid"],
    )


@app.get("/chain/integrity", response_model=ChainIntegrity)
def chain_integrity():
    return ChainIntegrity(**get_fleet().chain_integrity())


def ledger_stream_gen(fleet=None):
    """Async generator that tails the hash chain and yields SSE chunks.

    Exposed separately from the endpoint so tests can drive it directly
    (bounded) without blocking on a live StreamingResponse.
    """
    if fleet is None:
        fleet = get_fleet()

    async def gen():
        last_seq = -1
        entries = fleet._raw_entries()
        if entries:
            last_seq = entries[-1]["seq"]
        yield ": ok\n\n"
        while True:
            await asyncio.sleep(1.0)
            cur = fleet._raw_entries()
            fresh = [e for e in cur if e["seq"] > last_seq]
            for e in fresh:
                last_seq = e["seq"]
                payload = {k: v for k, v in e.items() if k in AuditEntry.model_fields}
                data = json.dumps({"event": "audit.append", "entry": payload})
                yield f"data: {data}\n\n"
    return gen()


@app.get("/ledger/stream")
def ledger_stream():
    """Server-Sent Events: tails the hash chain and pushes new records as the
    fleet appends them. Polls the ledger tail (JsonStore has no push channel);
    only emits entries with a seq greater than the last seen cursor."""
    return StreamingResponse(ledger_stream_gen(), media_type="text/event-stream")


@app.get("/policy-log", response_model=PolicyLog)
def policy_log():
    return PolicyLog(decisions=get_fleet().policy_log())


@app.get("/verification", response_model=VerificationLog)
def verification():
    return VerificationLog(artifacts=get_fleet().verification_log())


@app.get("/approvals/pending", response_model=List[PendingApproval])
def approvals_pending():
    return [PendingApproval(**p) for p in get_fleet().pending_approvals()]


@app.post("/approvals/{request_id}/decide", response_model=ApprovalResult)
def decide(request_id: str, body: DecideRequest):
    fleet = get_fleet()
    try:
        result = fleet.decide(request_id, body.approve, body.signer)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return ApprovalResult(**result)


@app.post("/run/incident", response_model=RunResult)
def run_incident(body: RunRequest):
    """Additive: triggers a real R->A->O incident pipeline so the live ledger
    and approval console have genuine data to show. Calls the real fleet."""
    res = get_fleet().run_incident(
        verification=body.verification, severity=body.severity,
        workload_id=body.workload_id, action=body.action,
    )
    res["audit_tail"] = _proj_entries(res["audit_tail"])
    return RunResult(**res)


@app.post("/agents/{agent_id}/revoke-rotate")
def revoke_rotate(agent_id: str):
    try:
        return get_fleet().revoke_rotate(agent_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/demo/beats", response_model=List[BeatListEntry])
def demo_beats():
    return [BeatListEntry(**b) for b in beats.list_beats()]


@app.post("/demo/beat/{n}", response_model=BeatResult)
def demo_beat(n: int):
    if n < 1 or n > 8:
        raise HTTPException(status_code=400, detail="beat must be 1..8")
    try:
        passed, detail, new_entries = beats.run_beat(n)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"beat {n} failed: {e}")
    name = dict((b["beat"], b["name"]) for b in beats.list_beats()).get(n, f"beat {n}")
    return BeatResult(
        beat=n, name=name, passed=passed, detail=detail,
        ledger_entries=_proj_entries(new_entries),
    )


# ---- package init wiring --------------------------------------------------
def create_app() -> FastAPI:
    return app
