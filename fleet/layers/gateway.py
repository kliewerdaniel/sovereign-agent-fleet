"""Capability Gateway (Control Plane component #5 — 03.3 / 13.1 / D9 / D15).

The ONLY issuer of authority. An agent presents its root-signed AgentCert and
requests a capability. The Gateway:

  * authenticates the cert (root-signed, unrevoked, unexpired) via the Registry;
  * evaluates capability policy (pure, deterministic, never Gemini);
  * returns GRANT / REQUIRE_APPROVAL / DENY;
  * on DENY, emits a *signed* deny event into the audit ledger (13.1);
  * dedupes replayed authority requests via idempotency keys (13.7, failure #12).

Forged / expired / revoked certs are treated as DENY with a signed event, so
the refusal itself is a verifiable ledger fact (adversarial beats 2 and 7).
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Dict, Optional, Set

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from fleet.crypto.foundation import AgentCert, AuditTrail, canonical_bytes, sha256
from fleet.layers.policy import Decision, PolicyResult, decide


class GatewayDeny(Exception):
    """Raised when authority is denied; carries the structured response."""
    def __init__(self, resp: "AuthorityResponse"):
        self.resp = resp
        super().__init__(resp.deny_reason or resp.decision.value)


@dataclass
class AuthorityResponse:
    granted: bool
    policy_id: str
    decision: str                       # "grant" | "require_approval" | "deny"
    capability: str
    agent_id: str
    require_approval: bool
    deny_reason: Optional[str]
    idempotency_key: Optional[str]
    signed_deny_event: Optional[dict]   # AuditEntry if denied


class Gateway:
    def __init__(
        self,
        registry,  # AgentRegistry
        audit: AuditTrail,
        signing_key: Ed25519PrivateKey,
        signing_agent_id: str = "gateway",
        now_fn=None,
    ):
        self._registry = registry
        self._audit = audit
        self._key = signing_key
        self._signer = signing_agent_id
        self._now = now_fn or time.time
        self._cache: Dict[str, AuthorityResponse] = {}  # idempotency_key -> prior verdict

    def request_authority(
        self,
        cert: AgentCert,
        capability: str,
        idempotency_key: Optional[str] = None,
    ) -> AuthorityResponse:
        # --- idempotency (13.7) ------------------------------------------------
        # A replay of a key returns the PRIOR authority outcome verbatim; it is
        # not a fresh denial. This prevents the Gateway from double-charging the
        # same consequential action and lets a legit retry of a granted request
        # succeed. True "no double-execution" enforcement lives at the Runtime
        # write layer (failure #12); here we only memoize the verdict.
        if idempotency_key is not None:
            if idempotency_key in self._cache:
                return self._cache[idempotency_key]
            response = None  # set below, then cached

        # --- authentication (root-signed, unrevoked, unexpired) ---------------
        live = self._registry.discover(cert.agent_id)
        auth_ok = (
            live is not None
            and live.cert_seq == cert.cert_seq
            and self._registry._root.verify_cert(cert)
        )
        if not auth_ok:
            return self._deny(
                cert.agent_id, capability,
                "identity not authenticated (forged/expired/revoked cert)",
                idempotency_key,
            )

        # --- authorization (pure policy, never Gemini) -----------------------
        pol: PolicyResult = decide(cert.role, capability)
        if pol.decision is Decision.DENY:
            return self._deny(cert.agent_id, capability, pol.reason, idempotency_key)

        require_approval = pol.decision is Decision.REQUIRE_APPROVAL
        self._audit.append(
            {
                "kind": "gateway.grant",
                "who": cert.agent_id,
                "capability": capability,
                "policy_id": pol.policy_id,
                "require_approval": require_approval,
                "result": "ok",
            }
        )
        return self._record(
            AuthorityResponse(
                granted=True, policy_id=pol.policy_id, decision=pol.decision,
                capability=capability, agent_id=cert.agent_id,
                require_approval=require_approval, deny_reason=None,
                idempotency_key=idempotency_key, signed_deny_event=None,
            ),
            idempotency_key,
        )

    # --- internal -----------------------------------------------------------
    def _record(self, response, idempotency_key):
        """Cache a verdict under its idempotency key (13.7 replay = prior outcome)."""
        if idempotency_key is not None:
            self._cache[idempotency_key] = response
        return response

    def _deny(self, agent_id, capability, reason, idempotency_key) -> AuthorityResponse:
        entry = {
            "kind": "gateway.deny",
            "who": agent_id,
            "capability": capability,
            "policy_id": "deny",
            "result": "denied",
            "why": reason,
        }
        signed = self._audit.append(entry)
        # attach the gateway's signature over the deny event for non-repudiation
        signed = dict(signed)
        signed["gateway_sig"] = self._key.sign(canonical_bytes(signed)).hex()
        return self._record(
            AuthorityResponse(
                granted=False, policy_id="deny", decision="deny",
                capability=capability, agent_id=agent_id,
                require_approval=False, deny_reason=reason,
                idempotency_key=idempotency_key, signed_deny_event=signed,
            ),
            idempotency_key,
        )
