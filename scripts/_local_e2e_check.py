"""Local (no GCP) end-to-end check of the new D17 console + bridge queue logic."""
import os, sys, json, time
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from fleet.gcp.bridge import GcpBridge
from fleet.gcp.console import ApprovalConsole
from fleet.layers.approval import verify_approval
from fleet.crypto.foundation import AgentCert, canonical_bytes
from io import BytesIO
from wsgiref.util import setup_testing_defaults

bridge = GcpBridge(mode="local", project="project-3ba93cec-8ca6-43c0-ba4")
key = Ed25519PrivateKey.from_private_bytes(
    HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=b"fleet:human").derive(b"sovereign-fleet-judge-human-v1"))
pub_pem = key.public_key().public_bytes(
    serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode()
human_cert = AgentCert(agent_id="human-judge", pubkey_pem=pub_pem, role="human",
    capabilities=["approve_deny"], issued_at=int(time.time()), expires_at=int(time.time()) + 99999,
    cert_seq=0, root_sig="0" * 128)

console = ApprovalConsole(bridge, verify_approval=verify_approval, human_cert=human_cert)
action = {"action_id": "act-1", "agent_id": "operator-1", "capability": "crm_write",
          "artifact_hash": "deadbeef", "ts": int(time.time())}
console.queue(action)
assert [p["action_id"] for p in console.pending()] == ["act-1"], "queue failed"

def post(console, req):
    env = {}; setup_testing_defaults(env); env["REQUEST_METHOD"] = "POST"; env["PATH_INFO"] = "/approve"
    b = json.dumps(req).encode(); env["CONTENT_LENGTH"] = str(len(b)); env["wsgi.input"] = BytesIO(b)
    out = {}
    def sr(s, h): out["s"] = s
    console.wsgi_app(env, sr); return out["s"]

ts = action["ts"]
body = canonical_bytes({"approval_id": "", "agent_id": "operator-1", "action_id": "act-1",
    "capability": "crm_write", "artifact_hash": "deadbeef", "decision": "approve",
    "reason": "ok", "human_id": "human-judge", "ts": ts})
sig = key.sign(body).hex()
rec = {"approval_id": "", "agent_id": "operator-1", "action_id": "act-1", "capability": "crm_write",
       "artifact_hash": "deadbeef", "decision": "approve", "reason": "ok",
       "human_id": "human-judge", "human_sig": sig, "ts": ts}
st = post(console, rec)
assert "200" in st, f"valid approval rejected: {st}"
assert [a["action_id"] for a in bridge.recorded_approvals()] == ["act-1"], "approval not persisted"
assert [p["action_id"] for p in console.pending()] == [], "pending not consumed"

bad = dict(rec); bad["action_id"] = "act-2"
st2 = post(console, bad)
assert "403" in st2, f"tampered approval accepted: {st2}"
print("ALL LOCAL E2E OK (queue->pend->verify->persist->consume, tamper rejected)")
