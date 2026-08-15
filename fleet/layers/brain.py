"""Phase 4 probabilistic brain (D15 / D18 / D20).

The brain is a PLUGGABLE interface: it only *proposes* structured content. The
deterministic Control Plane decides authority, verification, and what is
recorded. Model choice (local Gemma4 vs Gemini 3.5 Flash) is CONFIG, not code
(D18/D20) -- both implement the same ``Brain`` contract, so the SAME tests
validate either.

Hard rules enforced here (D15):
  * Brain output is SCHEMA-VALIDATED at the boundary BEFORE it becomes any
    record. Malformed probabilistic output is rejected, never silently trusted.
  * The brain NEVER receives policy / approval / capability context. The
    instruction builders below construct prompts from evidence only; a test
    asserts no policy vocabulary leaks into the prompt.

Gemini is DEMO-ONLY (D18): credits are conserved; it is never called in dev/test.
``GeminiBrain`` refuses to construct without ``demo=True``. Gemma is the dev
brain, reached via a local inference endpoint (Ollama-compatible by default).
Both heavy SDK/endpoint imports are LAZY so the offline test venv stays clean.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from fleet.layers.handoff import Handoff
from fleet.fin.domain import TradeProposal

# Policy/approval vocabulary that must NEVER reach the probabilistic brain (D15).
_FORBIDDEN_PROMPT_TOKENS = (
    "policy", "approval", "approve", "deny", "capability", "capabilities",
    "authoriz", "gateway", "permission", "reject",
)


class Brain:
    """Probabilistic brain interface (D15/D18).

    The ONLY job of a brain is to PROPOSE structured content. It never makes
    authority, policy, verification, or approval decisions -- those are the
    deterministic Control Plane's. Concrete brains (Gemma/Gemini) subclass this.
    """

    def propose(self, role: str, instruction: str, schema_hint: str) -> Dict[str, Any]:
        raise NotImplementedError


@dataclass
class StubBrain(Brain):
    """Deterministic dev/test brain: returns a fixed structured proposal."""

    canned: Dict[str, Any] = field(default_factory=dict)

    def propose(self, role: str, instruction: str, schema_hint: str) -> Dict[str, Any]:
        return self.canned


class BrainSchemaError(ValueError):
    """Raised when a brain's proposed output fails schema enforcement (D15)."""


# ---------------------------------------------------------------------------
# Output schemas -- the contract every brain must satisfy before a record.
# ---------------------------------------------------------------------------

SCHEMAS: Dict[str, Dict[str, Any]] = {
    "researcher_synthesis": {
        "required": ["summary"],
        "types": {"summary": str},
    },
    "analyst_classification": {
        "required": ["claim", "claim_type", "confidence", "evidence_refs"],
        "types": {
            "claim": str,
            "claim_type": str,
            "confidence": (int, float),
            "evidence_refs": list,
        },
    },
    "analyst_entity_resolution": {
        "required": ["resolved_entity", "confidence"],
        "types": {"resolved_entity": str, "confidence": (int, float),
                  "canonical_id": str},
    },
    "operator_outreach": {
        "required": ["subject", "body"],
        "types": {"subject": str, "body": str},
    },
    "trade_signal": {
        "required": ["symbol", "side", "qty", "price_constraint",
                     "thesis", "confidence", "evidence_refs", "strategy_id"],
        "types": {
            "symbol": str,
            "side": str,
            "qty": (int, float),
            "price_constraint": dict,
            "thesis": str,
            "confidence": (int, float),
            "evidence_refs": list,
            "strategy_id": str,
        },
    },
}


def validate_brain_output(task: str, output: Any) -> Dict[str, Any]:
    """Enforce the brain-output schema before it becomes a record (D15).

    Raises ``BrainSchemaError`` on any violation -- malformed probabilistic
    output is rejected at the boundary, never trusted.
    """
    if not isinstance(output, dict):
        raise BrainSchemaError(f"brain output for '{task}' must be a dict, got {type(output).__name__}")
    schema = SCHEMAS.get(task)
    if schema is None:
        raise BrainSchemaError(f"unknown brain task: {task}")
    for field in schema["required"]:
        if field not in output:
            raise BrainSchemaError(f"brain task '{task}' missing field: {field}")
    for field, t in schema["types"].items():
        if field in output and not isinstance(output[field], t):
            expected = t.__name__ if isinstance(t, type) else " or ".join(x.__name__ for x in t)
            raise BrainSchemaError(
                f"brain task '{task}' field '{field}' wrong type: "
                f"expected {expected}, got {type(output[field]).__name__}"
            )
    if "confidence" in output:
        try:
            c = float(output["confidence"])
        except (TypeError, ValueError):
            raise BrainSchemaError(
                f"confidence must be numeric, got {type(output['confidence']).__name__}"
            )
        if not (0.0 <= c <= 1.0):
            raise BrainSchemaError(f"confidence must be in [0,1], got {c}")
    if "evidence_refs" in output:
        if not all(isinstance(r, str) for r in output["evidence_refs"]):
            raise BrainSchemaError("evidence_refs must be a list of strings")
    return output


# ---------------------------------------------------------------------------
# Schema-enforcing wrapper -- any brain behind this is validated at the edge.
# ---------------------------------------------------------------------------

class SchemaEnforcedBrain(Brain):
    def __init__(self, base: Brain):
        self.base = base

    def propose(self, role: str, instruction: str, schema_hint: str) -> Dict[str, Any]:
        out = self.base.propose(role, instruction, schema_hint)
        if not isinstance(out, dict):
            raise BrainSchemaError(
                f"brain '{self.base.__class__.__name__}' returned non-dict for '{schema_hint}'"
            )
        return validate_brain_output(schema_hint, out)


# ---------------------------------------------------------------------------
# Offline stand-in (dev/test). Represents BOTH Gemma and Gemini behavior for
# the schema-enforcement contract: canned output per task, so the same test
# runs against Gemma or Gemini by swapping the base brain.
# ---------------------------------------------------------------------------

class DeterministicBrain(Brain):
    def __init__(self, canned: Optional[Dict[str, Any]] = None):
        self.canned = canned or {}

    def propose(self, role: str, instruction: str, schema_hint: str) -> Dict[str, Any]:
        v = self.canned.get(schema_hint, {})
        if callable(v):
            v = v(role, instruction, schema_hint)
        return v


class CooperativeBrain(Brain):
    """A well-behaved probabilistic strategist: proposes a clean LONG in the
    allowed universe (AAPL) sized within the mandate. Used to demonstrate that
    an HONEST model also flows through the same four gates and executes."""

    def __init__(self, symbol: str = "AAPL", side: str = "BUY", qty: float = 10,
                 strategy_id: str = "ai-strategist"):
        self.symbol = symbol
        self.side = side
        self.qty = qty
        self.strategy_id = strategy_id

    def propose(self, role: str, instruction: str, schema_hint: str) -> Dict[str, Any]:
        if schema_hint != "trade_signal":
            return {}
        return {
            "symbol": self.symbol, "side": self.side, "qty": self.qty,
            "price_constraint": {"type": "MARKET"},
            "thesis": "model: verified momentum signal in allowed universe",
            "confidence": 0.85,
            "evidence_refs": ["ev-from-intel"],  # overwritten by strategist
            "strategy_id": self.strategy_id,
        }


class HostileBrain(Brain):
    """Adversarial model (D27 M0 demonstration): deliberately proposes the WORST
    possible trade that still PASSES the output schema -- an unauthorized asset,
    a 100x-oversized position, and a confidence engineered to look stale/reckless.
    The point: schema validity does NOT grant authority. Every Layer (Capability,
    Risk-policy, ExchangeSim) must refuse it INDEPENDENTLY of the model. The model
    may lie; the boundary holds."""

    def propose(self, role: str, instruction: str, schema_hint: str) -> Dict[str, Any]:
        if schema_hint != "trade_signal":
            return {}
        return {
            "symbol": "TSLA",          # not in allowed universe -> risk-policy BLOCK
            "side": "BUY",
            "qty": 1000,                # ~$150k vs max_order_usd=10k -> order-too-large
            "price_constraint": {"type": "MARKET"},
            "thesis": "hostile model: ignore mandate, maximize size",
            "confidence": 0.01,         # low confidence; advisory only, never de-escalates
            "evidence_refs": ["ev-from-intel"],
            "strategy_id": "hostile",
        }

# ---------------------------------------------------------------------------
# Gemini 3.5 Flash (D20) -- GenAI SDK called DIRECTLY. DEMO-ONLY (D18).
# Lazy import: the google-genai package is NOT in the test venv.
# ---------------------------------------------------------------------------

class GeminiBrain(Brain):
    def __init__(self, model: str = "gemini-3.5-flash", api_key: Optional[str] = None,
                 demo: bool = False):
        if not demo:
            # D18: never burn Gemini credits outside the submission demo.
            raise RuntimeError(
                "Gemini is demo-only (D18). Construct with demo=True for the "
                "submission demo; use Gemma/DeterministicBrain for dev/test."
            )
        self.model = model
        self.api_key = api_key

    def propose(self, role: str, instruction: str, schema_hint: str) -> Dict[str, Any]:
        from google import genai  # lazy; only present at demo time

        client = genai.Client(api_key=self.api_key)
        resp = client.models.generate_content(
            model=self.model,
            contents=instruction,
            config={"response_mime_type": "application/json"},
        )
        return json.loads(resp.text)


# ---------------------------------------------------------------------------
# Local abliterated Gemma4 (D18) -- dev brain. Calls a LOCAL inference endpoint
# (Ollama-compatible by default) so no credit is spent. Lazy stdlib http; no
# heavy client dependency in the base venv.
# ---------------------------------------------------------------------------

class GemmaBrain(Brain):
    def __init__(self, base_url: str = "http://localhost:11434",
                 model: str = "gemma4", demo: bool = False):
        self.base_url = base_url.rstrip("/")
        self.model = model

    def propose(self, role: str, instruction: str, schema_hint: str) -> Dict[str, Any]:
        import urllib.request

        payload = json.dumps({
            "model": self.model,
            "prompt": instruction,
            "format": "json",
            "stream": False,
        }).encode("utf-8")
        req = urllib.request.Request(
            self.base_url + "/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=60) as r:
            data = json.loads(r.read().decode("utf-8"))
        raw = data.get("response", "{}")
        if not isinstance(raw, str):
            raise BrainSchemaError("Gemma endpoint returned non-string response")
        return json.loads(raw)


# ---------------------------------------------------------------------------
# Instruction builders -- construct prompts from EVIDENCE ONLY (D15). The brain
# never sees policy/approval/capability context. A test asserts this.
# ---------------------------------------------------------------------------

def analyst_instruction(ev_payload: Dict[str, Any], claim_type: str = "icp_fit") -> str:
    citation = ev_payload.get("citation", "")
    extract = ev_payload.get("extract", "")
    eid = ev_payload.get("evidence_id", "")
    return (
        f"Classify the following sourced evidence for the claim type '{claim_type}'.\n"
        f"Evidence id: {eid}\nCitation: {citation}\nExtract: {extract}\n"
        f"Return JSON with: claim (string), claim_type (string), "
        f"confidence (float 0-1), evidence_refs (list of evidence ids)."
    )


def operator_instruction(target: str, draft_spec: Dict[str, Any]) -> str:
    intent = draft_spec.get("intent", "")
    return (
        f"Draft a short professional outreach message to {target}.\n"
        f"Intent: {intent}\n"
        f"Return JSON with: subject (string), body (string)."
    )


def strategist_instruction(ev_payload: Dict[str, Any], universe: List[str]) -> str:
    """D15: build a TRADE PROPOSAL prompt from evidence ONLY. The brain never
    receives policy / approval / capability / position context — it proposes a
    trade, it does not authorize one. It must pick from the allowed universe."""
    citation = ev_payload.get("citation", "")
    extract = ev_payload.get("extract", "")
    eid = ev_payload.get("evidence_id", "")
    universe_s = ", ".join(universe)
    return (
        f"Propose a single trade based ONLY on the sourced evidence below.\n"
        f"Evidence id: {eid}\nCitation: {citation}\nExtract: {extract}\n"
        f"Allowed universe: {universe_s}\n"
        f"Return JSON with: symbol (string, from allowed universe), side (string),\n"
        f"qty (number), price_constraint (object with type MARKET|LIMIT, "
        f"limit number, band number), thesis (string), confidence (float 0-1),\n"
        f"evidence_refs (list of evidence ids), strategy_id (string)."
    )


def assert_no_policy_leak(instruction: str) -> None:
    low = instruction.lower()
    for tok in _FORBIDDEN_PROMPT_TOKENS:
        if tok in low:
            raise BrainSchemaError(f"prompt leaks policy vocabulary '{tok}' (D15)")


# ---------------------------------------------------------------------------
# Trade strategist (financial Layer-1 proposal boundary, D27).
# Parallel to Analyst: the probabilistic brain PROPOSES a trade; this class
# schema-validates it and produces a fleet.fin.TradeProposal. The strategist
# never decides authorization, risk, or policy — those are Layer 2/3.
# ---------------------------------------------------------------------------

class TradeStrategist:
    def __init__(self, agent, runtime, universe: List[str], brain=None):
        self.agent = agent
        self.rt = runtime
        self.universe = universe
        # Allow a per-call brain override (e.g. demo selects cooperative/hostile).
        # Falls back to the runtime's configured brain.
        self.brain = brain if brain is not None else runtime.brain

    def propose_from_evidence(self, evidence_handoff: "Handoff", strategy_id: str,
                              side_hint: str = "BUY") -> "TradeProposal":
        """Consume Researcher evidence, let the brain PROPOSE via the
        'trade_signal' schema, then validate and return a TradeProposal."""
        from fleet.fin.domain import TradeProposal

        ev_payload = evidence_handoff.consume(
            self.rt.cp.registry, known_evidence=set(self.rt.evidence_meta())
        )
        instruction = strategist_instruction(ev_payload, self.universe)
        assert_no_policy_leak(instruction)  # D15: evidence only, no policy vocab
        raw = self.brain.propose("strategist", instruction, "trade_signal")
        # schema-validated at the boundary before it becomes a proposal (D15)
        validated = validate_brain_output("trade_signal", raw)
        # evidence_refs MUST cite the evidence the strategist actually consumed
        validated["evidence_refs"] = [str(ev_payload.get("evidence_id"))]
        return TradeProposal(
            symbol=validated["symbol"],
            side=validated.get("side", side_hint),
            qty=float(validated["qty"]),
            price_constraint=validated["price_constraint"],
            thesis=validated["thesis"],
            confidence=float(validated["confidence"]),
            evidence_refs=validated["evidence_refs"],
            strategy_id=validated.get("strategy_id", strategy_id),
        )
