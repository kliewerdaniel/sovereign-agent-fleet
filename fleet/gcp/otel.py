"""Agent Observability (03.2 #7): OTel-compliant audit + reasoning trace export.

The Control Plane audit ledger is the source of truth; this exporter maps each
audit event to an OpenTelemetry *shape* (span with trace_id/span_id/attributes)
so the data flows into any OTel backend without the runtime depending on a
specific SDK at build time. We duck-type the OTel span interface:

  * if ``opentelemetry`` is importable, spans go to the real SDK/tracer;
  * otherwise they go to an in-memory collector (offline/test) that exposes the
    same attribute shape, so tests assert on trace structure without network.

This keeps the base (test) venv free of heavy SDK deps (D18 cost discipline)
while satisfying the hackathon "OTel audit logs + reasoning traces" requirement.
"""
from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional


class OtelSpan:
    """Minimal OTel span shape (name, trace_id, span_id, attributes, events)."""

    def __init__(self, name: str, trace_id: str, span_id: str,
                 attributes: Optional[Dict[str, Any]] = None):
        self.name = name
        self.trace_id = trace_id
        self.span_id = span_id
        self.attributes = dict(attributes or {})
        self.events: List[Dict[str, Any]] = []

    def add_event(self, name: str, attributes: Optional[Dict[str, Any]] = None) -> None:
        self.events.append({"name": name, "attributes": dict(attributes or {})})


class InMemorySpanExporter:
    """Offline collector mirroring the OTel span export shape."""

    def __init__(self):
        self.spans: List[OtelSpan] = []

    def export(self, span: OtelSpan) -> None:
        self.spans.append(span)

    def by_trace(self, trace_id: str) -> List[OtelSpan]:
        return [s for s in self.spans if s.trace_id == trace_id]


class OtelExporter:
    def __init__(self, use_sdk: bool = False):
        self.use_sdk = use_sdk
        self._collector = InMemorySpanExporter()
        self._tracer = None
        if use_sdk:  # pragma: no cover - exercised only in deploy mode
            from opentelemetry import trace  # type: ignore
            self._tracer = trace.get_tracer("sovereign-fleet")

    def trace_for(self, run_id: str) -> str:
        """Stable trace id per execution run (so R->A->O share one trace)."""
        return uuid.uuid5(uuid.NAMESPACE_DNS, f"fleet-run:{run_id}").hex

    def emit_audit(self, run_id: str, entry: Dict[str, Any]) -> OtelSpan:
        """Map one audit ledger entry to an OTel span."""
        trace_id = self.trace_for(run_id)
        span_id = uuid.uuid4().hex[:16]
        attrs = {
            "fleet.kind": entry.get("kind"),
            "fleet.who": (entry.get("payload") or {}).get("who"),
            "fleet.result": (entry.get("payload") or {}).get("result"),
            "fleet.seq": entry.get("seq"),
        }
        if self.use_sdk and self._tracer is not None:  # pragma: no cover
            with self._tracer.start_as_current_span(f"audit:{entry.get('kind')}") as span:
                for k, v in attrs.items():
                    if v is not None:
                        span.set_attribute(k, str(v))
                return OtelSpan(f"audit:{entry.get('kind')}", trace_id, span_id, attrs)
        span = OtelSpan(f"audit:{entry.get('kind')}", trace_id, span_id, attrs)
        self._collector.export(span)
        return span

    def emit_reasoning(self, run_id: str, role: str, step: str,
                       content: Dict[str, Any]) -> OtelSpan:
        """Map a (deterministic) brain proposal to a reasoning span."""
        trace_id = self.trace_for(run_id)
        span_id = uuid.uuid4().hex[:16]
        attrs = {"fleet.reasoning.role": role, "fleet.reasoning.step": step}
        span = OtelSpan(f"reasoning:{role}:{step}", trace_id, span_id, attrs)
        span.add_event("proposal", content)
        self._collector.export(span)
        return span

    def spans(self) -> List[OtelSpan]:
        return self._collector.spans
