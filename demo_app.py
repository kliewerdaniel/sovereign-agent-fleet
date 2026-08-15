"""Streamlit window into the Sovereign Agent Fleet protocol (D26 use case).

This file lives OUTSIDE the trust boundary. It is a VIEWER: it drives the real
ControlPlane / Runtime / SimEnv stack and renders each protocol stage in its own
panel. It decides NOTHING — every gate (Evidence, Capability, Policy, Approval)
is enforced by the deterministic fleet code, exactly as in production.

8-panel hierarchy (D26 sec.9):
  1. Agent proposal     — what the model/brain proposed (model only proposes)
  2. Evidence           — SourcedEvidence (Researcher, schema-validated)
  3. Verification       — D16 verdict (VERIFIED / ASSERTED / HALLUCINATION)
  4. Capability         — Gateway capability decision
  5. Policy decision    — incident.required_authorization (AUTO/HUMAN/BLOCKED)
  6. Human approval     — cryptographically-bound ApprovalRecord if required
  7. SimEnv state       — before/after of the real deterministic transition
  8. Signed audit       — the chained, signed operator.final event

Run:  streamlit run demo_app.py
(dependency: requirements-ui.txt — NOT part of the runtime/audit surfaces)
"""
from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone

import streamlit as st
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from fleet.crypto.chriscrypt.store import JsonStore
from fleet.layers import (
    Analyst,
    Approval,
    ControlPlane,
    MemBank,
    Operator,
    Researcher,
    Runtime,
    ToolEnvelope,
)
from fleet.layers.incident import Authorization, bind_artifact, required_authorization
from fleet.simenv.env import ACTIONS, SimEnv, WorkloadState, asset_class


# ---------------------------------------------------------------------------
# Fleet bootstrap (local demo env; mirrors the beats/e2e fixtures)
# ---------------------------------------------------------------------------
@st.cache_resource
def build_fleet():
    tmp = tempfile.mkdtemp(prefix="saf_demo_")
    master = b"demo-app-master"
    audit = Ed25519PrivateKey.from_private_bytes(
        HKDF(algorithm=hashes.SHA256(), length=32, salt=None,
             info=b"fleet:audit").derive(b"audit-demo"))
    store = JsonStore(os.path.join(tmp, "audit.json"))
    cp = ControlPlane(master, audit, store=store, now_fn=lambda: int(datetime.now(timezone.utc).timestamp()),
                      run_id="demo-app")
    kek = HKDF(algorithm=hashes.SHA256(), length=32, salt=None,
               info=b"fleet:mem").derive(b"mem-demo")
    mem = MemBank(kek)
    rt = Runtime(cp, mem, now_fn=lambda: int(datetime.now(timezone.utc).timestamp()))
    r = cp.publish_agent("researcher-1", "researcher", ["emit_evidence"])
    a = cp.publish_agent("analyst-1", "analyst", ["qualify", "verify_gate"])
    o = cp.publish_agent("operator-1", "operator",
                         ["prepare_artifact", "crm_write", "incident_remediate"])
    human = cp.publish_agent("human-1", "human", ["approve_deny"])
    tool_cert, tool_key = cp.root.issue_cert("web_tool", "tool",
                                             ["retrieve"], 1_000, 9_999_999_999)
    cp.registry._certs["web_tool"] = tool_cert
    return {"cp": cp, "rt": rt, "r": r, "a": a, "o": o, "human": human,
            "tool_key": tool_key, "tool_cert": tool_cert, "sim": SimEnv()}


# ---------------------------------------------------------------------------
# Run one incident scenario through the REAL pipeline, capturing each stage.
# ---------------------------------------------------------------------------
def run_scenario(env, workload_id, action_name, severity, human_approves):
    stages = {}
    sim = env["sim"]
    before = sim.state_of(workload_id)

    # 1) Agent proposal (model only proposes; here a deterministic draft text)
    proposal = f"Remediate {workload_id}: execute '{action_name}' (severity {severity})."
    stages["proposal"] = proposal

    # 2) Evidence — Researcher turns a verified tool result into SourcedEvidence
    extract = f"indicator of compromise on {workload_id}"
    ev_out = json.dumps({"citation": "https://soc.example/ioc", "extract": extract}).encode()
    env_env = ToolEnvelope.make(env["tool_key"], "web_tool", ev_out)
    ev_handoff = Researcher(env["r"], env["rt"]).gather(env_env, "ioc?", ["citation", "extract"])
    stages["evidence"] = ev_handoff.payload

    # 3) Verification — Analyst qualifies + D16 stamp
    intel_handoff = Analyst(env["a"], env["rt"]).qualify(ev_handoff, [{
        "claim": "compromise=true", "claim_type": "role",
        "evidence_refs": [ev_handoff.payload["evidence_id"]],
    }])
    intel = intel_handoff.payload
    intel["severity"] = severity  # analyst-assigned severity (not the model's)
    stages["intel"] = intel
    stages["verification"] = intel.get("verification")

    # 4) Capability — Gateway decision on the operator's cert
    cap_resp = env["cp"].request_authority(env["o"].cert, "incident_remediate")
    stages["capability"] = {
        "granted": cap_resp.granted,
        "decision": cap_resp.decision,
        "require_approval": cap_resp.require_approval,
    }

    # 5) Policy — pure (severity x blast x asset_class) decision
    auth = required_authorization(intel["verification"], severity, action_name, workload_id)
    stages["policy"] = {
        "authorization": auth.value,
        "asset_class": asset_class(workload_id),
        "blast_radius": ACTIONS[action_name][1],
    }

    # 6) Human approval (only meaningful when policy says HUMAN)
    approval = None
    if auth == Authorization.HUMAN:
        target_state = ACTIONS[action_name][0].value
        bound = bind_artifact(workload_id, action_name, target_state)
        if human_approves:
            ap = Approval.sign(env["human"].cert, env["human"].key,
                               "operator-1", "idem-demo", "incident_remediate",
                               bound, "approve", "incident authorized",
                               int(datetime.now(timezone.utc).timestamp())).__dict__
            approval = ap
    stages["approval"] = approval

    # 7) SimEnv transition + 8) signed audit — via Operator.act (enforces all gates)
    result = Operator(env["o"], env["rt"]).act(
        intel_handoff, proposal, "incident_remediate", "idem-demo",
        approval=approval, target_workload=workload_id,
        action_name=action_name, simenv=sim,
    )
    after = sim.state_of(workload_id)
    stages["sim_before"] = before
    stages["sim_after"] = after
    stages["result"] = result
    # the signed operator.final audit entry (if it happened)
    final_entries = [e for e in env["cp"].audit.entries() if e.get("kind") == "operator.final"]
    stages["audit"] = final_entries[-1] if final_entries else None
    return stages


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------
st.set_page_config(page_title="Sovereign Agent Fleet — Incident Protocol", layout="wide")
st.title("Sovereign Agent Fleet")
st.caption("Incident Triage → Authorized Remediation — a window INTO the protocol "
           "(the UI decides nothing; every gate is enforced by the fleet code).")

env = build_fleet()

col_l, col_r = st.columns(2)
with col_l:
    workload_id = st.selectbox("Target workload", list(env["sim"].state.keys()), index=0)
with col_r:
    action_name = st.selectbox("Remediation action", list(ACTIONS.keys()), index=0)
severity = st.selectbox("Severity (analyst-assigned)", ["LOW", "MEDIUM", "HIGH"], index=0)
human_approves = st.checkbox("Human grants approval (if required)", value=True)

if st.button("Run remediation scenario", type="primary"):
    stages = run_scenario(env, workload_id, action_name, severity, human_approves)
    panels = st.container()

    def panel(n, title, body, tone="info"):
        with panels:
            box = panels.expander(f"{n}. {title}", expanded=True)
            with box:
                if tone == "good":
                    st.success(body)
                elif tone == "bad":
                    st.error(body)
                elif tone == "warn":
                    st.warning(body)
                else:
                    st.write(body)

    # 1. Proposal
    panel(1, "Agent proposal (model only proposes)", stages["proposal"])
    # 2. Evidence
    panel(2, "Evidence — SourcedEvidence", stages["evidence"])
    # 3. Verification
    v = stages["verification"]
    vtone = "good" if v == "VERIFIED" else ("warn" if v == "ASSERTED" else "bad")
    panel(3, f"Verification (D16) — {v}", f"Evidence gate verdict: {v}", vtone)
    # 4. Capability
    cap = stages["capability"]
    panel(4, "Capability (Gateway)", cap,
          "good" if cap["granted"] else "bad")
    # 5. Policy
    pol = stages["policy"]
    ptone = {"AUTO": "good", "HUMAN": "warn", "BLOCKED": "bad"}[pol["authorization"]]
    panel(5, f"Policy decision — {pol['authorization']}", pol, ptone)
    # 6. Approval
    if stages["approval"] is not None:
        panel(6, "Human approval — signed ApprovalRecord", stages["approval"], "good")
    else:
        note = ("AUTO: human approval not required" if pol["authorization"] == "AUTO"
                else "BLOCKED: no approval path (policy prohibits this action)")
        panel(6, "Human approval", note, "warn" if pol["authorization"] != "AUTO" else "good")
    # 7. SimEnv
    sb, sa = stages["sim_before"], stages["sim_after"]
    changed = sb != sa
    panel(7, f"SimEnv state — before→after",
          f"before: **{sb.value}**  →  after: **{sa.value}**"
          + ("" if changed else "  (no state change — execution did not occur)"),
          "good" if changed else "bad")
    # 8. Audit
    if stages["audit"] is not None:
        panel(8, "Signed audit event — operator.final", stages["audit"], "good")
    else:
        panel(8, "Signed audit event", "No operator.final was emitted — the action did not execute.", "bad")

    # Outcome banner
    res = stages["result"]
    if res.get("final"):
        st.banner("Remediation executed and recorded.", icon="✅")
    elif res.get("blocked"):
        st.banner(f"BLOCKED at gate '{res.get('gate')}': {res.get('reason')}", icon="🛑")
    else:
        st.banner("Awaiting valid human approval (needs_approval).", icon="⏳")
else:
    st.info("Choose a workload, action, and severity, then run the scenario to watch "
            "all eight protocol stages resolve against the real fleet stack.")
