"""Live fleet runtime for the API.

Owns ONE real ControlPlane + published agents (researcher/analyst/operator/
human-approver) and the audit ledger behind it. Every read endpoint projects
real fleet records; every write endpoint calls the EXISTING control-plane code
(fleet.layers.runtime.Approval.sign for D17, the Gateway for policy). No crypto
or policy logic is reimplemented here.

The adversarial beats run in a SEPARATE sandbox ControlPlane (see beats.py) so
they never mutate this live instance.
"""
from __future__ import annotations

import os
import secrets
import tempfile
import threading
import time
from typing import Any, Dict, List, Optional

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from fleet.crypto.chriscrypt.store import JsonStore
from fleet.crypto.foundation import AgentCert, AuditTrail
from fleet.layers import (
    Analyst,
    Approval,
    ControlPlane,
    MemBank,
    Operator,
    Researcher,
    Runtime,
    StubBrain,
    ToolEnvelope,
    evaluate_intel,
    stamp,
)
from fleet.layers.incident import Authorization, Severity, decision_summary, required_authorization
from fleet.layers.verification import ASSERTED, HALLUCINATION, VERIFIED
from fleet.simenv.env import SimEnv


def _audit_key(seed: bytes) -> Ed25519PrivateKey:
    return Ed25519PrivateKey.from_private_bytes(
        HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=b"fleet:audit").derive(seed)
    )


def _mem_kek(seed: bytes) -> bytes:
    return HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=b"fleet:mem").derive(seed)


class LiveFleet:
    """Singleton live control plane + projection helpers."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        master = os.urandom(32)
        audit_seed = os.urandom(32)
        self.audit_key = _audit_key(audit_seed)
        fd, store_path = tempfile.mkstemp(suffix=".json", prefix="fleet-api-")
        with os.fdopen(fd, "w") as fh:
            fh.write("{}")
        self.store = JsonStore(store_path)
        self.cp = ControlPlane(master, self.audit_key, store=self.store)
        self.researcher = self.cp.publish_agent("researcher", "researcher", ["gather"])
        self.analyst = self.cp.publish_agent("analyst", "analyst", ["qualify"])
        self.operator = self.cp.publish_agent("operator", "operator", ["incident_remediate"])
        self.human = self.cp.publish_agent("human-approver", "human", ["approve"])
        # Synced view of live agent certs/keys: agent_id -> (cert, key).
        # revoke_rotate() refreshes an entry here so incident runs always sign
        # with the registry-current cert (Handoff.verify rejects stale seqs).
        self._agents = {
            self.researcher.agent_id: (self.researcher.cert, self.researcher.key),
            self.analyst.agent_id: (self.analyst.cert, self.analyst.key),
            self.operator.agent_id: (self.operator.cert, self.operator.key),
            self.human.agent_id: (self.human.cert, self.human.key),
        }

    # -- ledger -------------------------------------------------------------
    def _raw_entries(self) -> List[Dict[str, Any]]:
        return [e for e in self.cp.audit.entries() if e.get("id") != "checkpoint"]

    def ledger_page(self, since: Optional[str] = None, limit: int = 50) -> Dict[str, Any]:
        entries = self._raw_entries()
        if since is not None:
            # entries are zero-padded seq ids; fetch those with id > since
            entries = [e for e in entries if e["id"] > since]
        window = entries[-limit:]
        nxt = window[-1]["id"] if len(window) == limit and window else None
        head = entries[-1]["sig"] if entries else None
        return {
            "entries": window,
            "next_cursor": nxt,
            "head": head,
            "entry_count": len(self._raw_entries()),
            "chain_valid": bool(self.cp.verify_audit()),
        }

    def chain_integrity(self) -> Dict[str, Any]:
        entries = self._raw_entries()
        return {
            "valid": bool(self.cp.verify_audit()),
            "entry_count": len(entries),
            "head": entries[-1]["sig"] if entries else None,
            "audit_pubkey_pem": self.cp.audit.public_key_pem().decode(),
            "checked_at": int(time.time()),
        }

    # -- agents -------------------------------------------------------------
    def agents_snapshot(self) -> Dict[str, Any]:
        agents: List[Dict[str, Any]] = []
        for agent_id in self.cp.registry._certs:
            cert = self.cp.registry.get_cert(agent_id)
            if cert is None:
                continue
            revoked = agent_id in self.cp.registry._revoked
            agents.append({
                "agent_id": cert.agent_id,
                "role": cert.role,
                "capabilities": list(cert.capabilities),
                "cert_seq": cert.cert_seq,
                "status": "revoked" if revoked else "active",
                "issued_at": cert.issued_at,
                "expires_at": cert.expires_at,
            })
        return {
            "root_epoch": self.cp.root.root_epoch,
            "root_public_pem": self.cp.root.root_public_pem.decode(),
            "agents": agents,
        }

    # -- policy + verification projections ---------------------------------
    def policy_log(self) -> List["PolicyDecisionRow"]:
        from .schema import PolicyDecisionRow
        rows = []
        for e in self._raw_entries():
            if e.get("kind") in ("gateway.grant", "gateway.deny"):
                p = e.get("payload", {})
                rows.append(PolicyDecisionRow(**{
                    "seq": e["seq"],
                    "ts": e["ts"],
                    "agent_id": e.get("who") or p.get("agent_id", ""),
                    "capability": p.get("capability", ""),
                    "decision": "deny" if e["kind"] == "gateway.deny" else "grant",
                    "require_approval": bool(p.get("require_approval", False)),
                    "policy_id": p.get("policy_id"),
                    "reason": p.get("why") or p.get("policy_id"),
                    "idempotency_key": p.get("idempotency_key"),
                }))
        return rows

    def verification_log(self) -> List["VerificationRow"]:
        from .schema import VerificationRow
        rows = []
        for e in self._raw_entries():
            if e.get("kind") == "analyst.qualify":
                p = e.get("payload", {})
                rows.append(VerificationRow(**{
                    "seq": e["seq"],
                    "ts": e["ts"],
                    "agent_id": e.get("who", ""),
                    "intel_id": p.get("intel_id", ""),
                    "verification": p.get("verification", "UNKNOWN"),
                    "confidence": float(p.get("confidence", 0.0)),
                    "target_id": p.get("target_id", ""),
                    "artifact_hash": p.get("artifact_hash"),
                }))
        return rows

    # -- approval queue (D17) ----------------------------------------------
    def pending_approvals(self) -> List[Dict[str, Any]]:
        """Consequential actions awaiting a human-signed ApprovalRecord.

        Sourced from entries the Operator produced with needs_approval=True but
        no attached signed approval. Derived from genuine ledger state.
        """
        entries = self._raw_entries()
        # action_ids that already have a signed approval
        signed = {e["payload"].get("action_id")
                  for e in entries if e.get("kind") == "operator.approval.signed"}
        pending = []
        for e in entries:
            if e.get("kind") != "operator.needs_approval":
                continue
            p = e.get("payload", {})
            action_id = p.get("action_id") or p.get("idempotency_key")
            if not action_id or action_id in signed:
                continue
            pending.append({
                "request_id": action_id,
                "action_id": action_id,
                "capability": p.get("capability", ""),
                "agent_id": e.get("who") or p.get("who", ""),
                "artifact_hash": p.get("artifact_hash", ""),
                "reason": p.get("reason"),
                "raised_at": e["ts"],
            })
        return pending

    def decide(self, request_id: str, approve: bool, signer: str) -> Dict[str, Any]:
        """Call the EXISTING D17 flow. Never reimplements signing.

        Looks up the pending consequential action, then (on approve) produces a
        genuine Ed25519 ApprovalRecord via Approval.sign bound to the human's
        real cert/key, and appends a signed `operator.approval.signed` entry.
        On deny, appends a signed `operator.approval.rejected` entry.
        """
        with self._lock:
            pending = [p for p in self.pending_approvals() if p["request_id"] == request_id]
            if not pending:
                raise KeyError(f"no pending approval for request {request_id}")
            p = pending[0]
            capability = p["capability"]
            artifact_hash = p["artifact_hash"]
            agent_id = p["agent_id"]
            ts = int(time.time())
            decision = "approve" if approve else "reject"
            reason = "human approved via fleet API" if approve else "human rejected via fleet API"

            if approve:
                approval = Approval.sign(
                    self.human.cert, self.human.key, agent_id, request_id,
                    capability, artifact_hash, decision, reason, ts,
                )
                self.cp.audit.append({
                    "kind": "operator.approval.signed",
                    "who": "human-approver",
                    "request_id": request_id,
                    "action_id": request_id,
                    "capability": capability,
                    "artifact_hash": artifact_hash,
                    "decision": decision,
                    "reason": reason,
                })
                return approval.__dict__
            else:
                self.cp.audit.append({
                    "kind": "operator.approval.rejected",
                    "who": "human-approver",
                    "request_id": request_id,
                    "action_id": request_id,
                    "capability": capability,
                    "artifact_hash": artifact_hash,
                    "decision": decision,
                    "reason": reason,
                })
                return {
                    "approval_id": f"ap_denied_{secrets.token_hex(4)}",
                    "agent_id": agent_id,
                    "action_id": request_id,
                    "capability": capability,
                    "artifact_hash": artifact_hash,
                    "decision": decision,
                    "reason": reason,
                    "human_id": self.human.cert.agent_id,
                    "human_sig": "",
                    "ts": ts,
                }

    # -- run trigger (additive; calls real fleet pipeline) -----------------
    def run_incident(
        self, *, verification: str = VERIFIED, severity: str = "LOW",
        workload_id: str = "web-edge", action: str = "block_egress",
        query: str = "why is the web-edge host beaconing?",
    ) -> Dict[str, Any]:
        """Run a real R->A->O incident-remediation pipeline against the fleet.

        Mirrors bridge/fleet_adapter.run_incident: drives the genuine
        Researcher/Analyst/Operator + SimEnv + audit ledger. Returns the policy
        outcome + pending-approval request id so the console can sign it.
        """
        with self._lock:
            run_id = f"run_{secrets.token_hex(4)}"
            simenv = SimEnv()
            rt = Runtime(self.cp, MemBank(_mem_kek(os.urandom(32))),
                         brain=StubBrain(), store=self.store)
            res = Researcher(self.researcher, rt)
            ana = Analyst(self.analyst, rt)
            op = Operator(self.operator, rt)

            # Resolve sender identity from the SYNCED live agents. revoke-rotate
            # advances a cert's seq and reissues a fresh key; revoke_rotate()
            # refreshes the entry in self._agents, so reading from it always
            # yields a cert whose seq matches the registry (otherwise
            # Handoff.verify rejects with "sender identity not authenticated").
            from fleet.layers.registry import PublishedAgent as RegistryAgent

            def live_agent(agent_id: str) -> RegistryAgent:
                pair = self._agents.get(agent_id)
                if pair is None:
                    raise KeyError(f"no live agent {agent_id}")
                cert, key = pair
                return RegistryAgent(cert=cert, key=key)

            pre_count = len(self._raw_entries())
            # Researcher gathers schema-valid evidence (real handoff, real sig).
            researcher = live_agent(self.researcher.agent_id)
            evidence_payload = {
                "evidence_id": f"ev_{secrets.token_hex(6)}",
                "agent_id": self.researcher.agent_id,
                "citation": "sim:web-edge:siem",
                "extract": f"{workload_id} exhibiting anomalous egress volume (severity {severity}).",
                "source_hash": secrets.token_hex(16),
                "retrieval_prov": {"tool": "siem", "ts": int(time.time()), "query": query},
                "collected_at": int(time.time()),
            }
            from fleet.layers.handoff import Handoff as RealHandoff
            ev_handoff = RealHandoff.make(
                researcher.cert, researcher.key, "SourcedEvidence", evidence_payload
            )
            rt.record_evidence_meta(evidence_payload["evidence_id"], int(time.time()))

            claim_type = "icp_fit" if verification == ASSERTED else "remediation"
            predicates = [{
                "claim": f"{workload_id} requires remediation via {action}",
                "claim_type": claim_type,
                "evidence_refs": [evidence_payload["evidence_id"]],
                "severity": severity,
            }]
            if verification == HALLUCINATION:
                analyst = live_agent(self.analyst.agent_id)
                base_intel = {
                    "intel_id": f"iq_{secrets.token_hex(6)}",
                    "agent_id": self.analyst.agent_id,
                    "target_id": workload_id,
                    "predicates": [{
                        "claim": predicates[0]["claim"],
                        "claim_type": "remediation",
                        "evidence_refs": ["ev_nonexistent"],
                        "severity": severity,
                    }],
                }
                intel = stamp(base_intel, {}, int(time.time()))
                intel_handoff = RealHandoff.make(
                    analyst.cert, analyst.key, "QualifiedIntel", intel
                )
            else:
                intel_handoff = ana.qualify(ev_handoff, predicates)
                intel = intel_handoff.payload

            auth = required_authorization(
                intel["verification"], Severity(severity), action, workload_id)
            idempotency_key = f"act_{secrets.token_hex(6)}"
            before = {"workload_id": workload_id, "state": simenv.state_of(workload_id).value}

            if intel["verification"] == HALLUCINATION:
                self.cp.audit.append({
                    "kind": "operator.blocked", "who": self.operator.agent_id,
                    "reason": "hallucination-intel", "gate": "evidence",
                    "target": workload_id, "action": action,
                })
                result: Dict[str, Any] = {"final": False, "blocked": True,
                                          "reason": "HALLUCINATION intel rejected"}
            else:
                result = op.act(
                    intel_handoff, artifact_text=f"Remediate {workload_id} via {action}",
                    capability="incident_remediate", idempotency_key=idempotency_key,
                    target_workload=workload_id, action_name=action, simenv=simenv,
                )
                # Genuine-fleet gap: the remediation fork (Operator._act_remediation)
                # returns needs_approval=True for HUMAN authorization WITHOUT appending
                # any durable ledger entry (unlike the generic act() which logs
                # operator.needs_approval). That leaves the consequential action
                # invisible to the pending queue + D17 decide. Append the same-shaped
                # durable entry the operator itself logs in the generic path so the
                # live approval console + real Approval.sign flow can observe it.
                if result.get("needs_approval") and not result.get("final"):
                    self.cp.audit.append({
                        "kind": "operator.needs_approval",
                        "who": self.operator.agent_id,
                        "intel_id": intel.get("intel_id"),
                        "capability": "incident_remediate",
                        "target": workload_id,
                        "action": action,
                        "artifact_hash": result.get("artifact_hash"),
                        "idempotency_key": idempotency_key,
                        "authorization": result.get("authorization", "HUMAN"),
                    })
            after = {"workload_id": workload_id, "state": simenv.state_of(workload_id).value}

            run_entries = [
                e for e in self._raw_entries()[pre_count:]
                if e.get("kind") != "registry.publish"
            ]
            return {
                "run_id": run_id,
                "verification": intel["verification"],
                "authorization": auth.value,
                "needs_approval": bool(result.get("needs_approval", False)),
                "blocked": bool(result.get("blocked", False)),
                "reason": result.get("reason"),
                "action_id": idempotency_key,
                "capability": "incident_remediate",
                "artifact_hash": result.get("artifact_hash"),
                "target": workload_id,
                "action": action,
                "environment_before": before,
                "environment_after": after,
                "audit_tail": run_entries,
            }

    # -- registry controls (beat 8 live, D14) -----------------------------
    def revoke_rotate(self, agent_id: str) -> Dict[str, Any]:
        """Exercise D14 revoke -> rotate against the live fleet, returning the
        post-rotation cert so the UI can show continuity."""
        with self._lock:
            self.cp.registry.revoke(agent_id)
            pa = self.cp.registry.rotate(agent_id)
            # Keep the synced live-agent view current so incident runs sign with
            # the rotated cert (Handoff.verify rejects stale seqs).
            self._agents[agent_id] = (pa.cert, pa.key)
            cert: AgentCert = pa.cert
            return {
                "agent_id": agent_id,
                "cert_seq": cert.cert_seq,
                "revoked": agent_id in self.cp.registry._revoked,
                "discoverable": self.cp.registry.discover(agent_id) is not None,
                "root_epoch": self.cp.root.root_epoch,
                "chain_valid": bool(self.cp.verify_audit()),
                "new_cert": {
                    "agent_id": cert.agent_id, "role": cert.role,
                    "capabilities": list(cert.capabilities),
                    "cert_seq": cert.cert_seq, "issued_at": cert.issued_at,
                    "expires_at": cert.expires_at,
                },
            }


# Module-level singleton (one live control plane per API process).
_fleet = LiveFleet()


def get_fleet() -> LiveFleet:
    return _fleet
