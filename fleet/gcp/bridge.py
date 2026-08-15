"""GCP replication bridge (13.3): only signed/verifiable artifacts leave local runtime.

Design principle (D3/D6): private keys and plaintext secrets NEVER cross to
GCP. The bridge replicates the *signed artifact* (cert / audit entry /
approval record) as a Firestore document whose verification requires only the
agent **public** keys. GCP holds verifiable *data*, sovereignty holds *authority*.

Two modes:
  * ``mode="local"`` (default, offline/test): an in-memory mirror that mimics the
    Firestore document schema EXACTLY. The 14.8 verifier therefore runs
    identically against the local mirror or a live Firestore copy -- it reads
    only document schema + public keys. This is the proof that the design holds
    whether or not GCP is actually deployed.
  * ``mode="gcp"``: lazily imports ``google.cloud.firestore`` /
    ``google.cloud.pubsub_v1`` and writes the same document schema. Requires the
    deploy dependencies in ``requirements-gcp.txt``. Not imported at module load,
    so the base (test) venv stays dependency-free.

Pub/Sub (R->A->O async handoffs, failure #3/#12): ``publish_task`` enqueues a
signed handoff envelope on a topic; local mode keeps an in-memory task list.

Cloud Run approval console (D17): ``serve_console`` returns a stdlib-WSGI app
(no Flask dependency) so it deploys on Cloud Run and is testable offline.
"""
from __future__ import annotations

import json
from typing import Any, Callable, Dict, List, Optional

from fleet.crypto.foundation import canonical_bytes, sha256


class ReplicationError(RuntimeError):
    pass


# 13.3 Firestore document schema: { id, payload, sig, prev_hash }.
def _doc_id(entry: Dict[str, Any]) -> str:
    return (
        entry.get("id")
        or entry.get("agent_id")
        or entry.get("evidence_id")
        or entry.get("intel_id")
        or entry.get("approval_id")
        or sha256(canonical_bytes(entry))
    )


class GcpBridge:
    def __init__(
        self,
        mode: str = "local",
        project: Optional[str] = None,
        firestore_collection: str = "fleet_ledger",
        pubsub_topic: str = "fleet_handoffs",
    ):
        if mode not in ("local", "gcp"):
            raise ValueError(f"unknown mode: {mode}")
        self.mode = mode
        self.project = project
        self.collection = firestore_collection
        self.topic = pubsub_topic
        self._mirror: Dict[str, dict] = {}
        self._tasks: List[dict] = []
        self._fs = None
        self._pub = None
        self._topic_path = None

    # -- client init (lazy; never at import) ---------------------------------
    def _init_clients(self) -> None:
        if self._fs is not None:
            return
        try:
            from google.cloud import firestore, pubsub_v1  # type: ignore
        except ImportError as e:  # pragma: no cover - only hit in gcp mode
            raise ReplicationError(
                "google-cloud-firestore / google-cloud-pubsub not installed; "
                f"install requirements-gcp.txt ({e})"
            )
        self._fs = firestore.Client(project=self.project)
        self._pub = pubsub_v1.PublisherClient()
        self._topic_path = self._pub.topic_path(self.project, self.topic)

    # -- 13.3 replicate ------------------------------------------------------
    def replicate(self, entry: Dict[str, Any]) -> Dict[str, Any]:
        """Mirror one signed artifact to Firestore (13.3).

        Returns the Firestore-shaped document {id, payload, sig, prev_hash}.
        The ``payload`` is the verbatim signed artifact -- so a verifier
        reconstructs it byte-for-byte and checks it with public keys only.
        """
        doc = {
            "id": str(_doc_id(entry)),
            "payload": entry,
            "sig": entry.get("sig"),
            "prev_hash": entry.get("prev"),
        }
        if self.mode == "gcp":
            self._init_clients()
            self._fs.collection(self.collection).document(doc["id"]).set(doc)
        else:
            self._mirror[doc["id"]] = doc
        return doc

    def mirror_docs(self) -> List[Dict[str, Any]]:
        """Return replicated docs (local mirror, or live Firestore)."""
        if self.mode == "gcp":
            self._init_clients()
            return [d.to_dict() for d in self._fs.collection(self.collection).stream()]
        return list(self._mirror.values())

    # -- Pub/Sub async handoffs (failure #3/#12) ----------------------------
    def publish_task(self, handoff: Dict[str, Any]) -> str:
        """Publish a signed handoff envelope to Pub/Sub (R->A->O async)."""
        if self.mode == "gcp" and self._pub is not None:
            self._init_clients()
            data = json.dumps(handoff, default=str).encode()
            future = self._pub.publish(self._topic_path, data)
            return future.result()  # pragma: no cover - gcp only
        self._tasks.append(handoff)
        return f"local-task-{len(self._tasks)}"

    def published_tasks(self) -> List[Dict[str, Any]]:
        return list(self._tasks)

    # -- Cloud Run approval console (D17) -----------------------------------
    def serve_console(self, cp=None):
        from fleet.gcp.console import ApprovalConsole
        from fleet.layers.approval import verify_approval

        # G2 hardening: wire server-side approval verification + the live human
        # approver cert so the deployed console can never be a pass-through. If
        # no ControlPlane (and thus no human cert) is supplied, human_cert stays
        # None and the console fails closed (rejects every approval).
        human = cp.registry.human_cert() if cp is not None else None
        return ApprovalConsole(
            self,
            verify_approval=verify_approval,
            human_cert=human,
        )


# ---------------------------------------------------------------------------
# Fanout store: lets the audit ledger ALSO replicate to GCP + emit telemetry,
# without the Ledger knowing about either. The JsonStore remains the source of
# truth; the mirror is the verifiable GCP copy.
# ---------------------------------------------------------------------------
class FanoutStore:
    def __init__(self, primary, on_put: Optional[Callable[[str, dict, Optional[str]], None]] = None):
        self.primary = primary
        self.on_put = on_put

    def put(self, coll: str, record: dict, event: Optional[str] = None) -> None:
        self.primary.put(coll, record, event)
        if self.on_put:
            self.on_put(coll, record, event)

    def get(self, coll: str, id: str):
        return self.primary.get(coll, id)

    def find(self, coll: str, **filters):
        return self.primary.find(coll, **filters)
