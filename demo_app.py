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
from fleet.fin.domain import Account, Mandate, TradeProposal, assess, required_trade_authorization
from fleet.fin.market_adapter import ReplayFixture
from fleet.fin.exchange_sim import ExchangeSim
from fleet.fin.verify import verify_control_plane


# ---------------------------------------------------------------------------
# Financial workload bootstrap (mirrors the financial e2e fixtures)
# ---------------------------------------------------------------------------
def build_fleet_fin():
    """Build a FRESH financial fleet (isolated ControlPlane + agents + account).

    This is intentionally NOT cached: each demo click gets a clean fleet so
    adversarial injections (e.g. `revoked_operator`) never leak across runs.
    The Runtime reuses operator-1's identity only if already present in its
    identity_root; a fresh Runtime starts empty, so this is safe.
    """
    tmp = tempfile.mkdtemp(prefix="saf_fin_")
    master = b"fin-demo-master"
    audit = Ed25519PrivateKey.from_private_bytes(
        HKDF(algorithm=hashes.SHA256(), length=32, salt=None,
             info=b"fleet:audit").derive(b"audit-fin-demo"))
    store = JsonStore(os.path.join(tmp, "fin_audit.json"))
    now_fn = lambda: 2000  # deterministic demo clock
    cp = ControlPlane(master, audit, store=store, now_fn=now_fn, run_id="demo-fin")
    kek = HKDF(algorithm=hashes.SHA256(), length=32, salt=None,
               info=b"fleet:mem").derive(b"mem-fin-demo")
    mem = MemBank(kek)
    rt = Runtime(cp, mem, now_fn=now_fn,
                 brain=__import__("fleet.layers.brain", fromlist=["StubBrain"]).StubBrain())
    r = cp.publish_agent("researcher-1", "researcher", ["emit_evidence"])
    a = cp.publish_agent("analyst-1", "analyst", ["qualify", "verify_gate"])
    o = cp.publish_agent("operator-1", "operator", ["trade_execute"])
    human = cp.publish_agent("human-1", "human", ["approve_deny"])
    tool_cert, tool_key = cp.root.issue_cert("mkt", "tool", ["retrieve"], 2000, 9_999_999_999)
    cp.registry._certs["mkt"] = tool_cert
    account = Account("acct-1", cash=100_000.0, positions={},
                      mandate=Mandate(allowed_assets=["AAPL"]))
    market = ReplayFixture("AAPL", 2000, 150.0, 150.2, 150.1, 1.0e6, "replay").to_market_data()
    return {"cp": cp, "rt": rt, "r": r, "a": a, "o": o, "human": human,
            "tool_key": tool_key, "tool_cert": tool_cert,
            "account": account, "market": market}


def run_fin_scenario(env, symbol, side, qty, consensus, human_approves, adversarial,
                     brain_source="deterministic"):
    """Run one financial trade through the REAL four-gate pipeline.

    brain_source:
      - "deterministic" (default): a rule-based proposal (no model).
      - "cooperative":  a well-behaved probabilistic brain PROPOSES; same gates.
      - "hostile":      an adversarial brain proposes worst-case; same gates (M0).

    The UI decides NOTHING: every gate (Evidence, Capability, Risk-policy,
    Approval) is enforced by fleet.fin code exactly as in production/e2e.
    """
    stages = {}
    cp = env["cp"]
    account = env["account"]
    market = env["market"]

    # 1) Model proposal (the model only PROPOSES; the gates decide).
    stages["proposal"] = {
        "symbol": symbol, "side": side, "qty": qty,
        "thesis": "deterministic baseline strategy signal",
    }

    # 2) Evidence — Researcher -> SourcedEvidence
    extract = f"{symbol} strong momentum on verified feed"
    ev_out = json.dumps({"citation": "https://mkt.example/snap", "extract": extract}).encode()
    ev_handoff = Researcher(env["r"], env["rt"]).gather(
        ToolEnvelope.make(env["tool_key"], "mkt", ev_out), "signal?", ["citation", "extract"])
    stages["evidence"] = ev_handoff.payload

    # 3) Verification — Analyst qualifies (+ D16 stamp)
    intel_handoff = Analyst(env["a"], env["rt"]).qualify(ev_handoff, [{
        "claim": "momentum=bullish", "claim_type": "icp_fit", "confidence": 0.9,
        "evidence_refs": [ev_handoff.payload["evidence_id"]],
    }])
    intel = intel_handoff.payload
    stages["intel"] = intel
    stages["verification"] = intel.get("verification")

    # 4) Proposal object (deterministic source). For the model-coupled path this
    #    is built but unused — act_trade_from_brain produces its own proposal from
    #    the brain and runs it through the SAME gates. Building it unconditionally
    #    keeps the value always bound for the deterministic branches below.
    proposal = TradeProposal(symbol, side, float(qty), {"type": "MARKET"},
                             "thesis", 0.9, [ev_handoff.payload["evidence_id"]], "s1")
    use_brain = brain_source in ("cooperative", "hostile")

    # Resolve which BRAIN drives the model-coupled path (per-call override).
    brain = None
    if use_brain:
        from fleet.layers.brain import CooperativeBrain, HostileBrain
        brain = HostileBrain() if brain_source == "hostile" else CooperativeBrain()

    # Adversarial injection: forge the approval with the OPERATOR key (not human).
    # Only meaningful on the deterministic path (a concrete proposal to forge).
    approval = None
    if adversarial == "forged_approval" and not use_brain:
        # Build the artifact hash the operator WOULD bind, then sign with wrong key.
        from fleet.fin.domain import bind_trade, account_state_hash
        pre = account_state_hash(account)
        risk = assess(proposal, account, market, account.mandate, 2000)
        artifact = bind_trade(account.account_id, proposal, pre,
                              market.snapshot_hash, risk.risk_assessment_hash)
        forged = Approval.sign(env["human"].cert, env["o"].key,  # WRONG key
                               "operator-1", "idem-fin", "trade_execute",
                               artifact, "approve", "forged", 2000)
        approval = forged.__dict__
    elif adversarial == "revoked_operator":
        cp.registry.revoke("operator-1")

    from fleet.layers.runtime import RuntimeError_ as _RuntimeError
    stages["result"] = None  # set by the execution below; kept for verifier section
    try:
        if use_brain:
            # Model-coupled execution: same four gates, brain only proposes.
            if adversarial == "replay":
                consensus_used = "weak" if consensus == "weak" else None
                first = Operator(env["o"], env["rt"]).act_trade_from_brain(
                    intel_handoff, account, market, account.mandate,
                    ExchangeSim(account, market, now=2000), idempotency_key="idem-fin",
                    consensus=consensus_used, brain=brain)
                res = Operator(env["o"], env["rt"]).act_trade_from_brain(
                    intel_handoff, account, market, account.mandate,
                    ExchangeSim(account, market, now=2000), idempotency_key="idem-fin",
                    consensus=consensus_used, brain=brain)
                stages["result"] = res
                stages["replayed"] = True
            else:
                consent = "weak" if consensus == "weak" else None
                res = Operator(env["o"], env["rt"]).act_trade_from_brain(
                    intel_handoff, account, market, account.mandate,
                    ExchangeSim(account, market, now=2000), idempotency_key="idem-fin",
                    consensus=consent, brain=brain)
                stages["result"] = res
            # fall through to the independent verifier (runs for every path)
        elif adversarial == "replay":
            # Executes twice with the same idempotency key (second is a replay).
            consensus_used = "weak" if consensus == "weak" else None
            first = Operator(env["o"], env["rt"]).act_trade(
                intel_handoff, proposal, account, market, account.mandate,
                ExchangeSim(account, market, now=2000), idempotency_key="idem-fin",
                approval=approval, consensus=consensus_used)
            res = Operator(env["o"], env["rt"]).act_trade(
                intel_handoff, proposal, account, market, account.mandate,
                ExchangeSim(account, market, now=2000), idempotency_key="idem-fin",
                approval=approval, consensus=consensus_used)
            stages["result"] = res
            stages["replayed"] = True
        else:
            # 5) Capability + 6) Risk-policy via the real Operator.act_trade (all gates).
            sim = ExchangeSim(account, market, now=2000)
            # A forged approval is only meaningful if the trade reaches the HUMAN tier
            # (where the approval is actually verified). Force the advisory escalation.
            consent = "weak" if (consensus == "weak" or adversarial == "forged_approval") else None
            res = Operator(env["o"], env["rt"]).act_trade(
                intel_handoff, proposal, account, market, account.mandate, sim,
                idempotency_key="idem-fin", approval=approval, consensus=consent)
            stages["result"] = res
    except _RuntimeError as exc:
        # Fail-closed: a revoked/unknown operator identity (or other hard auth
        # failure) raises inside act_trade. Surface it as a clean BLOCKED result
        # instead of crashing the UI.
        stages["result"] = {"final": False, "blocked": True,
                             "gate": "capability", "reason": str(exc)}

    # 7) Independent verifier (read-only, public certs only).
    final_entries = [e for e in cp.audit.entries() if e.get("kind") == "operator.final"]
    if final_entries:
        agg = verify_control_plane(cp, env["o"].cert, env["human"].cert, 2000)
        stages["verifier"] = agg
    else:
        stages["verifier"] = {"overall": "N/A", "note": "no execution recorded"}
    return stages


# ---------------------------------------------------------------------------
# Run one incident scenario through the REAL pipeline, capturing each stage.
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

# Mode selector: incident remediation (existing) or financial workload (D27).
MODE = st.radio("Workload", ["Incident remediation", "Financial trade (D27)"], horizontal=True)

if MODE == "Financial trade (D27)":
    fen = build_fleet_fin()
    st.divider()
    st.subheader("Financial Trade — golden path + adversarial controls")
    st.caption("A window INTO the financial protocol. The UI proposes; the four gates "
               "(Evidence, Capability, Risk-policy, Approval) and the independent "
               "verifier enforce everything, exactly as in the fleet code.")

    col1, col2, col3 = st.columns(3)
    with col1:
        symbol = st.selectbox("Symbol", ["AAPL", "TSLA"], index=0)
    with col2:
        side = st.selectbox("Side", ["BUY", "SELL"], index=0)
    with col3:
        qty = st.number_input("Quantity", min_value=1, max_value=2000, value=10, step=1)

    col4, col5, col6 = st.columns(3)
    with col4:
        consensus = st.selectbox("Advisory consensus", ["none", "weak", "severe"], index=0)
    with col5:
        adversarial = st.selectbox(
            "Adversarial injection",
            ["none", "forged_approval", "revoked_operator", "replay"], index=0)
    with col6:
        brain_source = st.selectbox(
            "Proposal source",
            ["deterministic", "cooperative (AI)", "hostile (AI)"], index=0)
    brain_key = {"deterministic": "deterministic",
                 "cooperative (AI)": "cooperative",
                 "hostile (AI)": "hostile"}[brain_source]

    if st.button("Run financial scenario", type="primary"):
        stages = run_fin_scenario(
            fen, symbol, side, qty,
            consensus if consensus != "none" else None,
            human_approves=True, adversarial=adversarial, brain_source=brain_key)
        panels = st.container()

        def fpanel(n, title, body, tone="info"):
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

        # Panel 1 reflects the proposal source (deterministic rule vs model).
        if brain_key == "deterministic":
            fpanel(1, "Model proposal (model only proposes)", stages["proposal"])
        else:
            src = "Hostile brain" if brain_key == "hostile" else "Cooperative brain"
            note = ("adversarial: proposes unauth asset + 100x size; the SAME four "
                    "gates must refuse it (M0)" if brain_key == "hostile"
                    else "well-behaved: proposes in-universe LONG; same gates execute")
            fpanel(1, f"Proposal source: {src} (AI strategy demonstrates the protocol)",
                   note, tone="warn" if brain_key == "hostile" else "info")
        fpanel(2, "Evidence — SourcedEvidence", stages["evidence"])
        v = stages["verification"]
        vtone = "good" if v == "VERIFIED" else ("warn" if v == "ASSERTED" else "bad")
        fpanel(3, f"Verification (D16) — {v}", f"Evidence gate verdict: {v}", vtone)

        res = stages.get("result", {})
        cap = res.get("gate") == "capability"
        blocked = res.get("blocked")
        authorized = res.get("authorization")
        gate_tone = "bad" if blocked else ("good" if authorized == "AUTO" else "warn")
        fpanel(4, "Capability + Risk-policy (Operator.act_trade)",
               {k: res.get(k) for k in ("final", "blocked", "gate", "authorization",
                                        "disposition", "require_approval", "reason")},
               gate_tone)

        if adversarial == "forged_approval":
            fpanel(5, "Adversarial — forged approval",
                   "Forged approval (signed by operator key, not human) was "
                   "presented. Expect: blocked at the approval gate.", "warn")
        elif adversarial == "revoked_operator":
            fpanel(5, "Adversarial — revoked operator",
                   "Operator cert was revoked before the run. Expect: capability "
                   "denied at the gateway.", "warn")
        elif adversarial == "replay":
            fpanel(5, "Adversarial — replay (same idempotency key x2)",
                   "The same request was submitted twice. Expect: the second is an "
                   "idempotent replay (cached result, no new ledger entry).", "warn")

        # Independent verifier (read-only, public certs only).
        ver = stages.get("verifier", {})
        overall = ver.get("overall")
        vt = {"PASS": "good", "FAIL": "bad", "CRITICAL": "bad", "N/A": "info"}.get(overall, "info")
        fpanel(6, f"Independent verifier — {overall}",
               ver if overall != "N/A" else ver.get("note", "no execution"), vt)

        # Outcome banner
        if stages.get("replayed"):
            st.banner("Replay handled: cached fill returned, no duplicate ledger entry.",
                      icon="🔁")
        elif res.get("final"):
            st.banner("Trade executed and verified.", icon="✅")
        elif res.get("blocked"):
            st.banner(f"BLOCKED at gate '{res.get('gate')}': {res.get('reason')}", icon="🛑")
        elif res.get("needs_approval"):
            st.banner("Awaiting valid human approval (HUMAN tier).", icon="⏳")
        else:
            st.banner("No execution occurred.", icon="ℹ️")
    st.stop()  # financial mode renders its own panels; do not fall through

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
