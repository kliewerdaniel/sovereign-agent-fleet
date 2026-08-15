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
    cert_seq: int                      # cert version bound into the verdict (A3)
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
        # idempotency_key -> (verdict, agent_id, cert_seq). The cert binding is
        # part of the key so that a revoked/rotated cert (cert_seq bump) forces a
        # re-authentication instead of replaying a stale GRANT (A3/D14).
        self._cache: Dict[str, tuple] = {}

    def request_authority(
        self,
        cert: AgentCert,
        capability: str,
        idempotency_key: Optional[str] = None,
    ) -> AuthorityResponse:
        # --- idempotency (13.7) ------------------------------------------------
        # A replay of a key returns the PRIOR authority outcome verbatim, but
        # ONLY while the requesting cert's identity + cert_seq are unchanged. A
        # revoke or root rotation bumps cert_seq, so a stale replay must NOT
        # reuse a prior GRANT — it re-enters authentication and is denied (A3).
        if idempotency_key is not None and idempotency_key in self._cache:
            cached_resp, cached_agent, cached_seq = self._cache[idempotency_key]
            if cached_agent == cert.agent_id and cached_seq == cert.cert_seq:
                # Re-verify the cert is STILL live before replaying a prior GRANT.
                # A revoke (or any registry state change) must not let a stale
                # positive verdict survive — the cache is re-validated, not just
                # memoized (A3/D14).
                live = self._registry.discover(cert.agent_id)
                if live is not None and live.cert_seq == cert.cert_seq \
                        and self._registry._root.verify_cert(cert):
                    return cached_resp
            # Cert state changed since the cached verdict -> invalidate + re-eval.
            del self._cache[idempotency_key]

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
                capability=capability, agent_id=cert.agent_id, cert_seq=cert.cert_seq,
                require_approval=require_approval, deny_reason=None,
                idempotency_key=idempotency_key, signed_deny_event=None,
            ),
            idempotency_key,
        )

    # --- internal -----------------------------------------------------------
    def _record(self, response, idempotency_key):
        """Cache a verdict under its idempotency key (13.7 replay = prior outcome).

        Bound to (agent_id, cert_seq) so a revoke/rotation invalidates it (A3).
        """
        if idempotency_key is not None:
            self._cache[idempotency_key] = (response, response.agent_id, response.cert_seq)
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
                capability=capability, agent_id=agent_id, cert_seq=0,
                require_approval=False, deny_reason=reason,
                idempotency_key=idempotency_key, signed_deny_event=signed,
            ),
            idempotency_key,
        )
