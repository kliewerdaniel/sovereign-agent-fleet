"""Model Armor — structural + deterministic guardrails (D12 / 04.3 / 14.3).

No probabilistic classifier. Three sub-threats, three structural controls:

1. Prompt injection  -- agents receive ONLY schema-validated structured results.
   We strip free-text instruction surfaces from tool output before it can
   reach a model, and expose only declared structured fields. An injected
   "ignore previous instructions" string has no execution surface because the
   protocol never executes free-text as instruction.

2. Tool poisoning    -- every tool result is wrapped in a signed envelope
   (tool_id, output_hash, tool_sig). A tampered/forged output fails signature
   verification BEFORE the model ever sees it; the Runtime logs the failure.

3. PII leaks         -- deterministic regex/format scanner over outbound
   artifacts. Matching spans are redacted (replaced with a token) and the
   plaintext is never written to the ledger or logs.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from fleet.crypto.foundation import canonical_bytes

# --- 1. prompt injection ---------------------------------------------------

# Instruction-style fragments that have no business surviving from a tool
# result into a model prompt. Matching lines/fields are dropped.
_INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?previous\s+instructions", re.I),
    re.compile(r"disregard\s+(the\s+)?(above|prior|system)", re.I),
    re.compile(r"you\s+are\s+now", re.I),
    re.compile(r"exfil", re.I),
    re.compile(r"system\s*:\s*", re.I),
    re.compile(r"<\s*(system|instruction|prompt)\b", re.I),
    re.compile(r"reveal\s+(your|the)\s+(system\s+)?(prompt|instruction)", re.I),
]


class InjectionError(Exception):
    pass


def scan_injection(text: str) -> List[str]:
    """Return any instruction-like fragments found in free text."""
    hits = []
    for pat in _INJECTION_PATTERNS:
        for m in pat.finditer(text):
            hits.append(m.group(0))
    return hits


def sanitize_tool_result(raw: Dict[str, Any], allowed_fields: List[str]) -> Dict[str, Any]:
    """Model Armor step 1: project tool output to declared structured fields.

    Anything outside `allowed_fields` is dropped (no free-text instruction
    surface reaches the model). If a value contains an injection fragment,
    raise InjectionError so the Runtime records an injection attempt instead
    of forwarding it.
    """
    structured: Dict[str, Any] = {}
    for field in allowed_fields:
        if field in raw:
            value = raw[field]
            if isinstance(value, str):
                hits = scan_injection(value)
                if hits:
                    raise InjectionError(f"injection fragment in field '{field}': {hits}")
            structured[field] = value
    return structured


# --- 2. tool poisoning -----------------------------------------------------

@dataclass
class ToolEnvelope:
    tool_id: str
    output_hash: str
    output: bytes
    tool_sig: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tool_id": self.tool_id,
            "output_hash": self.output_hash,
            "output": self.output.decode("utf-8", "replace"),
            "tool_sig": self.tool_sig,
        }

    @classmethod
    def make(cls, tool_key: Ed25519PrivateKey, tool_id: str, output: bytes) -> "ToolEnvelope":
        from fleet.crypto.foundation import sha256
        oh = sha256(output)
        body = canonical_bytes({"tool_id": tool_id, "output_hash": oh})
        sig = tool_key.sign(body).hex()
        return cls(tool_id=tool_id, output_hash=oh, output=output, tool_sig=sig)


def verify_tool_envelope(env: ToolEnvelope, tool_cert_pem: str) -> bool:
    """Model Armor step 2: reject a tampered/forged tool result before the model.

    Verification is over (tool_id, output_hash) so a forged OR altered output
    fails. The signed envelope is the trust boundary for tool results (12.6).
    """
    try:
        key = serialization.load_pem_public_key(tool_cert_pem.encode())
        if not isinstance(key, Ed25519PublicKey):
            return False
        body = canonical_bytes({"tool_id": env.tool_id, "output_hash": env.output_hash})
        key.verify(bytes.fromhex(env.tool_sig), body)
        # recompute the output hash; a bit-flip in `output` breaks the chain too.
        from fleet.crypto.foundation import sha256
        return sha256(env.output) == env.output_hash
    except (InvalidSignature, ValueError):
        return False


# --- 3. PII ----------------------------------------------------------------

# Deterministic format scanner. These are demo-grade patterns for CRM/outreach
# artifacts; a production deployment would add more. Matching spans are
# redacted, never logged in plaintext.
_PII_PATTERNS = [
    ("email", re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")),
    ("phone", re.compile(r"(?<!\d)(?:\+?\d[\s.-]?){9,15}(?!\d)")),
    ("ssn", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    ("card", re.compile(r"\b(?:\d[ -]*?){13,19}\b")),
]


def scan_pii(text: str) -> List[Tuple[str, str]]:
    findings = []
    for kind, pat in _PII_PATTERNS:
        for m in pat.finditer(text):
            findings.append((kind, m.group(0)))
    return findings


def redact_pii(text: str) -> Tuple[str, int]:
    """Replace every detected PII span with a token. Returns (redacted, n_finds)."""
    n = 0
    out = text
    for kind, pat in _PII_PATTERNS:
        def _sub(m, k=kind):
            nonlocal n
            n += 1
            return f"<REDACTED:{k}>"
        out = pat.sub(_sub, out)
    return out, n
