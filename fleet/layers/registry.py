"""Agent Registry (Control Plane component #1 — 03.3 / D10 / D13 / D14).

Publishes, versions, discovers, revokes, and rotates fleet agent identities.
Every operation is recorded in the tamper-evident audit ledger. Built on the
Phase 0 IdentityRoot (Ed25519 root-of-trust certs) + AuditTrail.

Identity authentication (is this cert signed by root, unrevoked, unexpired) is
the Registry's job. Authorization (is this agent allowed this action?) is the
Gateway's job (policy.py). The two are deliberately separate (04.4).
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from fleet.crypto.foundation import AGENT_ROLES, AgentCert, AuditTrail, IdentityRoot


class RegistryError(Exception):
    pass


@dataclass
class PublishedAgent:
    cert: AgentCert
    key: Ed25519PrivateKey


class AgentRegistry:
    def __init__(self, root: IdentityRoot, audit: AuditTrail, now_fn=None):
        self._root = root
        self._audit = audit
        self._certs: Dict[str, AgentCert] = {}   # agent_id -> latest active cert
        self._revoked: Set[str] = set()
        self._now = now_fn or time.time

    # --- publish / discover ------------------------------------------------
    def publish(
        self,
        agent_id: str,
        role: str,
        capabilities: List[str],
        ttl_seconds: int = 86400,
    ) -> PublishedAgent:
        if role not in AGENT_ROLES:
            raise ValueError(f"unknown role: {role}")
        issued_at = int(self._now())
        expires_at = issued_at + ttl_seconds
        cert, key = self._root.issue_cert(
            agent_id, role, capabilities, issued_at, expires_at, cert_seq=0
        )
        self._certs[agent_id] = cert
        self._audit.append(
            {
                "kind": "registry.publish",
                "who": "control_plane",
                "agent_id": agent_id,
                "role": role,
                "capabilities": capabilities,
                "cert_seq": 0,
                "result": "ok",
            }
        )
        return PublishedAgent(cert=cert, key=key)

    def discover(self, agent_id: str) -> Optional[AgentCert]:
        """Authorization view: returns the cert only if it is the latest,
        root-signed, unrevoked, and unexpired. None otherwise."""
        cert = self._certs.get(agent_id)
        if cert is None:
            return None
        if agent_id in self._revoked:
            return None
        if not self._root.verify_cert(cert):
            return None
        if int(self._now()) >= cert.expires_at:
            return None
        return cert

    def list_agents(self) -> List[str]:
        return [a for a in self._certs if a not in self._revoked]

    def get_cert(self, agent_id: str) -> Optional[AgentCert]:
        """Latest cert regardless of revocation/expiry (inspection only)."""
        return self._certs.get(agent_id)

    def human_cert(self) -> Optional[AgentCert]:
        """Return the live (root-signed, unrevoked, unexpired) human approver cert.

        Used by the Operator to verify ApprovalRecords (D17). Looks up by ROLE,
        not a hard-coded id, so the human agent can be named anything.
        """
        for agent_id in self._certs:
            cert = self.discover(agent_id)
            if cert is not None and cert.role == "human":
                return cert
        return None

    def is_known(self, agent_id: str) -> bool:
        return agent_id in self._certs

    # --- revoke / rotate (D14) ---------------------------------------------
    def revoke(self, agent_id: str) -> None:
        if agent_id not in self._certs:
            raise RegistryError(f"unknown agent: {agent_id}")
        self._revoked.add(agent_id)
        self._root.revoke(agent_id)
        self._audit.append(
            {
                "kind": "registry.revoke",
                "who": "control_plane",
                "agent_id": agent_id,
                "result": "ok",
            }
        )

    def rotate(self, agent_id: str, ttl_seconds: int = 86400) -> PublishedAgent:
        old = self._certs.get(agent_id)
        if old is None:
            raise RegistryError(f"unknown agent: {agent_id}")
        issued_at = int(self._now())
        expires_at = issued_at + ttl_seconds
        cert, key = self._root.rotate_agent(old, issued_at, expires_at)
        # rotation re-issues a fresh key -> clears any prior revocation (D14 resume)
        self._revoked.discard(agent_id)
        self._root._revoked.pop(agent_id, None)
        self._certs[agent_id] = cert
        self._audit.append(
            {
                "kind": "registry.rotate",
                "who": "control_plane",
                "agent_id": agent_id,
                "cert_seq": cert.cert_seq,
                "result": "ok",
            }
        )
        return PublishedAgent(cert=cert, key=key)
