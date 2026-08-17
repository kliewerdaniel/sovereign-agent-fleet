"""Signed QuantEvidence envelope (Layer-1 enrichment, D28-style).

The quant layer's outputs are carried as a SEPARATE signed carrier bound to the
proposal's ``proposal_hash`` — exactly the D28 §6.3 enrichment split. The
governance surface (the ``TradeProposal`` / ``NormalizedOrder``) is unchanged;
this envelope is **logged, integrity-verifiable, and ignored by the gates.**

Why a separate envelope instead of fields on ``TradeProposal``:
    * It keeps ``fleet/fin/`` byte-untouched (D27 Tier-C honor: no alpha
      research added *to* the locked financial workload).
    * It lets the verifier prove *binding + integrity* (authentic, signed by the
      claimed producer, bound to the exact proposal, unmodified) without ever
      needing to trust the content — D28 D-D.
    * M0 is preserved for free: removing the envelope and recomputing the
      disposition yields an IDENTICAL authorization outcome (the gates never
      read it). ``fleet/fin/verify.py``'s existing enrichment-strip check already
      covers this with zero change.

Signing: the producer (a quant-model cert) signs the canonical body with its
Ed25519 key, reusing ``fleet.crypto.foundation.canonical_bytes`` / ``sha256`` —
the SAME primitive every other artifact in the repo uses. No new signing scheme.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from fleet.crypto.foundation import AgentCert, canonical_bytes, sha256


def qe_sign_body(d: Dict[str, Any]) -> bytes:
    """Reconstruct the exact canonical body signed by the producer (excl. sig)."""
    return canonical_bytes({k: v for k, v in d.items() if k not in ("signature",)})


@dataclass
class QuantEvidence:
    """Signed bundle of quant estimates for one proposal.

    Carries ONLY hashes of the constituent estimates (not the full records) so
    the envelope is compact and the verifier can bind to them. The full records
    are logged alongside (or reconstructed) by the holder's audit path.
    """

    proposal_hash: str          # binds to the TradeProposal / order this informs
    exchange_id: int
    producer_cert_id: str
    probability_hash: str        # ProbabilityEstimate.p_hash
    market_prob_hash: str        # MarketProbability.mp_hash
    edge_hash: str               # EdgeEstimate.edge_hash
    ev_hash: str                 # ExpectedValue.ev_hash
    model_id: str = "unknown"
    method: str = "unspecified"
    ts: int = 0
    calibration_hash: Optional[str] = None   # CalibrationRecord.cal_hash, if settlement known
    signature: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "proposal_hash": self.proposal_hash,
            "exchange_id": self.exchange_id,
            "producer_cert_id": self.producer_cert_id,
            "probability_hash": self.probability_hash,
            "market_prob_hash": self.market_prob_hash,
            "edge_hash": self.edge_hash,
            "ev_hash": self.ev_hash,
            "model_id": self.model_id,
            "method": self.method,
            "ts": self.ts,
            "calibration_hash": self.calibration_hash,
            "signature": self.signature,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "QuantEvidence":
        return cls(
            proposal_hash=str(d.get("proposal_hash", "")),
            exchange_id=int(d.get("exchange_id", 0)),
            producer_cert_id=str(d.get("producer_cert_id", "")),
            probability_hash=str(d.get("probability_hash", "")),
            market_prob_hash=str(d.get("market_prob_hash", "")),
            edge_hash=str(d.get("edge_hash", "")),
            ev_hash=str(d.get("ev_hash", "")),
            model_id=str(d.get("model_id", "unknown")),
            method=str(d.get("method", "unspecified")),
            ts=int(d.get("ts", 0)),
            calibration_hash=(str(d["calibration_hash"]) if d.get("calibration_hash") is not None else None),
            signature=str(d.get("signature", "")),
        )


def build_quant_evidence(
    producer_cert: AgentCert,
    producer_key: Ed25519PrivateKey,
    *,
    proposal_hash: str,
    exchange_id: int,
    probability_hash: str,
    market_prob_hash: str,
    edge_hash: str,
    ev_hash: str,
    model_id: str = "unknown",
    method: str = "unspecified",
    ts: int = 0,
    calibration_hash: Optional[str] = None,
) -> QuantEvidence:
    """Construct + sign a QuantEvidence envelope.

    ``proposal_hash`` MUST be the sha256(canonical(TradeProposal)) (or the
    normalized-order hash) this evidence informs — binding is the whole point.
    """
    qe = QuantEvidence(
        proposal_hash=proposal_hash,
        exchange_id=exchange_id,
        producer_cert_id=producer_cert.agent_id,
        probability_hash=probability_hash,
        market_prob_hash=market_prob_hash,
        edge_hash=edge_hash,
        ev_hash=ev_hash,
        model_id=model_id,
        method=method,
        ts=ts,
        calibration_hash=calibration_hash,
    )
    qe.signature = producer_key.sign(qe_sign_body(qe.to_dict())).hex()
    return qe


def verify_quant_evidence(qe: QuantEvidence, producer_cert: AgentCert) -> bool:
    """Fail-closed verification: signature under the claimed producer cert.

    Proves the envelope was signed by the claimed producer and is unmodified.
    Does NOT prove the contained estimates are correct — only authentic + bound.
    """
    if not qe.signature:
        return False
    try:
        pub = serialization.load_pem_public_key(producer_cert.pubkey_pem.encode())
        if not isinstance(pub, Ed25519PublicKey):
            return False
        pub.verify(bytes.fromhex(qe.signature), qe_sign_body(qe.to_dict()))
    except (InvalidSignature, ValueError, Exception):
        return False
    return True


def bind_quant_log(qe: QuantEvidence, *, p_hash: str, mp_hash: str, edge_hash: str, ev_hash: str) -> str:
    """Content-address the exact (envelope + constituent hashes) for audit binding.

    Lets the verifier assert the envelope it holds references the SAME estimate
    hashes that were logged — closing the "envelope swapped for different
    estimates" gap without trusting the envelope's content.
    """
    return sha256(canonical_bytes({
        "proposal_hash": qe.proposal_hash,
        "probability_hash": p_hash,
        "market_prob_hash": mp_hash,
        "edge_hash": edge_hash,
        "ev_hash": ev_hash,
        "envelope_sig": qe.signature,
    }))


__all__ = [
    "QuantEvidence",
    "build_quant_evidence",
    "verify_quant_evidence",
    "bind_quant_log",
    "qe_sign_body",
]
