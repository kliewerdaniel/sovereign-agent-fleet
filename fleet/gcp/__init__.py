"""fleet.gcp — GCP replication, observability, and approval console (13.3 / 03.2 #7 / D17).

Every artifact that leaves the local runtime to GCP is *signed and verifiable*
using only public keys (D3/D6). GCP holds data; sovereignty holds authority.
"""
from fleet.gcp.bridge import FanoutStore, GcpBridge, ReplicationError
from fleet.gcp.console import ApprovalConsole
from fleet.gcp.otel import InMemorySpanExporter, OtelExporter, OtelSpan
from fleet.gcp.verify import FirestoreVerifier

__all__ = [
    "GcpBridge",
    "ReplicationError",
    "FanoutStore",
    "ApprovalConsole",
    "FirestoreVerifier",
    "OtelExporter",
    "OtelSpan",
    "InMemorySpanExporter",
]
