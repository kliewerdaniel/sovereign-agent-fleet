"""Sovereign Runtime + fleet worker lifecycle (03.7 / 06 #11 #12 #13 / 13.2).

The Runtime executes a worker task through the deterministic lifecycle and is
the single place that:

  * enforces checkpointing so an interrupted run resumes instead of half-writing
    (failure #11 / #13: FINAL only after APPROVAL),
  * dedupes consequential writes via idempotency keys (failure #12),
  * holds the encrypted Memory Bank (local-first, D3/D6),
  * drives the three workers (Researcher / Analyst / Operator) which emit
    SourcedEvidence / QualifiedIntel / Artifact (12.2 / 12.3 / 12.4).

The probabilistic "brain" is a PLUGGABLE interface (D15/D18): it only proposes
structured content; the Runtime never lets it make authority, policy, or
verification decisions. The same test suite validates both the local Gemma
stub and (in Phase 4) Gemini, because the boundary is identical.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from fleet.crypto.foundation import SecretVault, canonical_bytes, sha256
from fleet.layers.armor import (
    InjectionError,
    redact_pii,
    sanitize_tool_result,
    verify_tool_envelope,
)
from fleet.layers.handoff import Handoff, HandoffError
from fleet.layers.verification import ASSERTED, HALLUCINATION, VERIFIED, stamp
from fleet.layers.approval import verify_approval
from fleet.layers.brain import (
    Brain,
    StubBrain,
    assert_no_policy_leak,
    analyst_instruction,
    operator_instruction,
)


class Lifecycle(str, Enum):
    REQUEST = "REQUEST"
    INTENT = "INTENT"
    PLAN = "PLAN"
    ACTION = "ACTION"
    TOOL = "TOOL"
    OBSERVATION = "OBSERVATION"
    EVIDENCE = "EVIDENCE"
    VERIFICATION = "VERIFICATION"
    ARTIFACT = "ARTIFACT"
    APPROVAL = "APPROVAL"
    FINAL = "FINAL"
    AUDIT = "AUDIT"


# Forward-only order; index enforces monotonic progress / resume.
_ORDER = list(Lifecycle)
_IDX = {s: i for i, s in enumerate(_ORDER)}


class RuntimeError_(Exception):
    pass


# ---------------------------------------------------------------------------
# Memory Bank (encrypted local state)
# ---------------------------------------------------------------------------

class MemBank:
    """Encrypted cross-session context (03.3 #3). Local-first; KEK never leaves."""

    def __init__(self, kek: bytes):
        self._vault = SecretVault(kek)
        self._records: Dict[str, Any] = {}

    def put(self, name: str, value: str) -> None:
        self._records[name] = self._vault.seal(name, value)

    def get(self, name: str) -> Optional[str]:
        rec = self._records.get(name)
        return self._vault.open(rec) if rec else None

    def sealed(self, name: str) -> Optional[dict]:
        return self._records.get(name)


# ---------------------------------------------------------------------------
# Runtime
# ---------------------------------------------------------------------------

@dataclass
class PublishedAgent:
    agent_id: str
    role: str
    cert: Any
    key: Any


class Runtime:
    def __init__(self, control_plane, membank: MemBank, brain: Optional[Brain] = None, store=None, now_fn=None):
        self.cp = control_plane
        self.mem = membank
        self.brain = brain or StubBrain()
        self.store = store
        self._now = now_fn or time.time
        self._idempotency: Dict[str, dict] = {}   # action_id -> recorded result
        self._checkpoints: Dict[str, dict] = {}    # task_id -> last state
        self._evidence: Dict[str, dict] = {}       # evidence_id -> metadata

    # -- idempotency (failure #12) ---------------------------------------------
    def idempotent(self, action_id: str, fn: Callable[[], dict]) -> dict:
        if action_id in self._idempotency:
            return {**self._idempotency[action_id], "idempotent_replay": True}
        result = fn()
        self._idempotency[action_id] = result
        return result

    # -- checkpointing (failure #11 / #13) -------------------------------------
    def checkpoint(self, task_id: str, state: str, payload: dict) -> None:
        self._checkpoints[task_id] = {"state": state, "payload": payload}
        if self.store is not None:
            self.store.put("checkpoint", {"id": f"task:{task_id}", "state": state,
                                          "payload": payload})

    def resume_from(self, task_id: str) -> Optional[dict]:
        return self._checkpoints.get(task_id)

    # -- evidence ledger (for D16 staleness) -----------------------------------
    def record_evidence_meta(self, evidence_id: str, collected_at: int) -> None:
        self._evidence[evidence_id] = {"collected_at": collected_at}

    def evidence_meta(self) -> Dict[str, dict]:
        return self._evidence

    def log_audit(self, kind: str, **fields) -> None:
        self.cp.audit.append({"kind": kind, "result": "ok", **fields})


# ---------------------------------------------------------------------------
# Worker: Researcher (gather) -- emits SourcedEvidence (12.2)
# ---------------------------------------------------------------------------

class Researcher:
    def __init__(self, agent: PublishedAgent, runtime: Runtime):
        self.agent = agent
        self.rt = runtime

    def gather(self, tool_envelope, retrieval_query: str, allowed_fields: List[str]) -> Handoff:
        """Turn a verified tool result into signed SourcedEvidence.

        Model Armor (D12): verify the signed tool envelope (poisoning defense)
        and sanitize the result to declared structured fields only (injection
        defense). Researcher is forbidden from emitting judgement fields (D8) —
        Handoff.consume enforces this when the Analyst consumes it.
        """
        # 1. tool poisoning defense: reject a forged/tampered tool result. A
        #    tool result is trusted only if signed by a registry-known tool
        #    identity (the signed envelope is the trust boundary, 12.6).
        tool_cert = self.rt.cp.registry.get_cert(tool_envelope.tool_id)
        if tool_cert is None:
            raise RuntimeError_("tool identity unknown to registry")
        if not verify_tool_envelope(tool_envelope, tool_cert.pubkey_pem):
            raise RuntimeError_("tool envelope failed signature verification")
        raw = json.loads(tool_envelope.output.decode("utf-8"))
        # 2. prompt injection defense: structured-only projection.
        try:
            structured = sanitize_tool_result(raw, allowed_fields)
        except InjectionError as e:
            self.rt.log_audit("runtime.injection", who=self.agent.agent_id, detail=str(e))
            raise
        now = int(self.rt._now())
        evidence_id = f"ev_{sha256(json.dumps(structured, sort_keys=True).encode())[:12]}"
        payload = {
            "evidence_id": evidence_id,
            "agent_id": self.agent.agent_id,
            "citation": structured.get("citation", ""),
            "extract": structured.get("extract", ""),
            "source_hash": sha256(tool_envelope.output),
            "retrieval_prov": {"tool": tool_envelope.tool_id, "ts": now, "query": retrieval_query},
            "collected_at": now,
        }
        self.rt.record_evidence_meta(evidence_id, now)
        self.rt.log_audit("researcher.emit", who=self.agent.agent_id, evidence_id=evidence_id)
        return Handoff.make(self.agent.cert, self.agent.key, "SourcedEvidence", payload)


# ---------------------------------------------------------------------------
# Worker: Analyst (judge) -- emits QualifiedIntel (12.3) via D16 gate
# ---------------------------------------------------------------------------

class Analyst:
    def __init__(self, agent: PublishedAgent, runtime: Runtime):
        self.agent = agent
        self.rt = runtime

    def qualify(self, evidence_handoff: Handoff, predicates: List[dict]) -> Handoff:
        """Consume Researcher evidence and emit verification-stamped intel."""
        live = self.rt.cp.registry.discover(self.agent.agent_id)
        if live is None:
            raise RuntimeError_("analyst identity not authenticated")
        # verify + schema-validate the inbound evidence (Model Armor boundary)
        ev_payload = evidence_handoff.consume(
            self.rt.cp.registry, known_evidence=set(self.rt.evidence_meta())
        )
        intel = {
            "intel_id": f"iq_{sha256(canonical_bytes(ev_payload))[:12]}",
            "agent_id": self.agent.agent_id,
            "target_id": ev_payload.get("agent_id", "target"),
            "predicates": predicates,
        }
        now = int(self.rt._now())
        stamped = stamp(intel, self.rt.evidence_meta(), now)
        self.rt.log_audit("analyst.qualify", who=self.agent.agent_id,
                          intel_id=stamped["intel_id"],
                          verification=stamped["verification"])
        return Handoff.make(self.agent.cert, self.agent.key, "QualifiedIntel", stamped)

    def classify_with_brain(self, evidence_handoff: Handoff, claim_type: str = "icp_fit") -> Handoff:
        """D15: let the probabilistic brain PROPOSE a classification, then
        enforce it through the same schema + D16 gate. The brain never decides
        verification -- it only proposes; the predicate still cites real,
        resolved evidence refs (no hallucination path)."""
        ev_payload = evidence_handoff.consume(
            self.rt.cp.registry, known_evidence=set(self.rt.evidence_meta())
        )
        instruction = analyst_instruction(ev_payload, claim_type)
        assert_no_policy_leak(instruction)  # D15: brain sees evidence only
        proposal = self.rt.brain.propose("analyst", instruction, "analyst_classification")
        # the predicate must cite the evidence the Analyst actually consumed
        proposal["evidence_refs"] = [ev_payload.get("evidence_id")]
        return self.qualify(evidence_handoff, [proposal])


# ---------------------------------------------------------------------------
# Worker: Operator (act) -- consumes intel, prepares artifact, executes
# ---------------------------------------------------------------------------

class Operator:
    def __init__(self, agent: PublishedAgent, runtime: Runtime):
        self.agent = agent
        self.rt = runtime

    def act(self, intel_handoff: Handoff, artifact_text: str,
            capability: str, idempotency_key: str,
            approval: Optional[dict] = None) -> dict:
        """Consume QualifiedIntel; enforce D16 boundary; execute consequential op.

        D16 boundary: HALLUCINATION intel is BLOCKED; ASSERTED intel requires a
        signed ApprovalRecord; VERIFIED intel auto-allows (low risk).
        FINAL only after authority + (for ASSERTED) approval (#13).
        """
        live = self.rt.cp.registry.discover(self.agent.agent_id)
        if live is None:
            raise RuntimeError_("operator identity not authenticated")
        intel = intel_handoff.consume(
            self.rt.cp.registry, known_evidence=set(self.rt.evidence_meta())
        )
        verification = intel.get("verification")
        if verification == HALLUCINATION:
            self.rt.log_audit("operator.blocked", who=self.agent.agent_id,
                              reason="hallucination-intel")
            return {"final": False, "blocked": True, "reason": "HALLUCINATION intel rejected"}

        # PII guard (D12): redact before the artifact becomes a record.
        redacted, n_pii = redact_pii(artifact_text)
        artifact_hash = sha256(redacted.encode("utf-8"))

        if verification == ASSERTED and approval is None:
            self.rt.log_audit("operator.needs_approval", who=self.agent.agent_id,
                              intel_id=intel.get("intel_id"))
            return {"final": False, "needs_approval": True,
                    "artifact_hash": artifact_hash, "pii_redacted": n_pii}

        # request authority (Gateway) — idempotency key dedupes replays (#12)
        resp = self.rt.cp.request_authority(live, capability, idempotency_key=idempotency_key)
        if not resp.granted:
            return {"final": False, "blocked": True,
                    "reason": resp.deny_reason or "authority denied"}
        if resp.require_approval:
            # D17 (A1/A2 — fail-closed): the human ApprovalRecord must be a
            # genuine Ed25519 signature that BINDS to this exact action. A
            # forged, rebound, or reused approval is rejected.
            human_cert = self.rt.cp.registry.human_cert()
            if human_cert is None or approval is None:
                return {"final": False, "needs_approval": True,
                        "artifact_hash": artifact_hash, "pii_redacted": n_pii}
            if not verify_approval(approval, human_cert, idempotency_key,
                                   capability, artifact_hash):
                self.rt.log_audit("operator.approval.rejected", who=self.agent.agent_id,
                                  reason="approval signature invalid or mis-bound")
                return {"final": False, "blocked": True,
                        "reason": "approval signature invalid or mis-bound",
                        "pii_redacted": n_pii}

        # FINAL: the consequential write is itself idempotent (#12) — a replay
        # of the same idempotency key returns the original recorded result
        # instead of double-executing.
        def _commit():
            self.rt.log_audit("operator.final", who=self.agent.agent_id,
                              capability=capability, artifact_hash=artifact_hash,
                              verification=verification, pii_redacted=n_pii)
            return {"final": True, "artifact_hash": artifact_hash,
                    "verification": verification, "pii_redacted": n_pii,
                    "require_approval": bool(resp.require_approval)}
        return self.rt.idempotent(idempotency_key, _commit)

    def draft_with_brain(self, intel_handoff: Handoff, target: str,
                         draft_spec: dict) -> str:
        """D15: brain DRAFTS outreach copy only. The draft is deterministic-
        validatable (schema) and still PII-redacted before becoming an artifact.
        The brain never sees intel verification state or policy context."""
        intel = intel_handoff.consume(
            self.rt.cp.registry, known_evidence=set(self.rt.evidence_meta())
        )
        instruction = operator_instruction(target, draft_spec)
        assert_no_policy_leak(instruction)  # D15: no policy/approval leakage
        proposal = self.rt.brain.propose("operator", instruction, "operator_outreach")
        redacted, _ = redact_pii(proposal.get("body", ""))
        return redacted


# ---------------------------------------------------------------------------
# Human approver (D17) -- signs ApprovalRecord
# ---------------------------------------------------------------------------

@dataclass
class Approval:
    approval_id: str
    agent_id: str
    action_id: str
    capability: str
    artifact_hash: str
    decision: str
    reason: str
    human_id: str
    human_sig: str
    ts: int

    @classmethod
    def sign(cls, human_cert, human_key, agent_id, action_id, capability,
             artifact_hash, decision, reason, ts) -> "Approval":
        import secrets
        body = canonical_bytes({
            "approval_id": "", "agent_id": agent_id, "action_id": action_id,
            "capability": capability, "artifact_hash": artifact_hash,
            "decision": decision, "reason": reason,
            "human_id": human_cert.agent_id, "ts": ts,
        })
        sig = human_key.sign(body).hex()
        return cls(approval_id=f"ap_{secrets.token_hex(6)}",
                   agent_id=agent_id, action_id=action_id, capability=capability,
                   artifact_hash=artifact_hash, decision=decision, reason=reason,
                   human_id=human_cert.agent_id, human_sig=sig, ts=ts)
