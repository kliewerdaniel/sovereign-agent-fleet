# -*- coding: utf-8 -*-
"""HONEST GCP verifier proof (D3/D6/14.8).

Builds a real ControlPlane, exercises governed actions (researcher -> analyst ->
operator with human approval), replicates the signed artifacts to the local
Firestore mirror, then verifies the GCP copy using ONLY the public keys -- the
exact code path the Cloud Run verifier runs. No private key is used by the
verifier. GCP min-instances are 0 in the demo, so this is the LOCAL replica of
that identical public-key path, labeled as such.
"""
import sys, os, json, tempfile
import os as _os  # repo-root-relative so the proof is portable (no hardcoded laptop path)
sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))))

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from fleet.crypto.chriscrypt.store import JsonStore
from fleet.gcp.bridge import GcpBridge
from fleet.gcp.otel import OtelExporter
from fleet.gcp.verify import FirestoreVerifier
from fleet.layers import (ControlPlane, MemBank, Runtime, Researcher, Analyst,
                          Operator, Approval, ToolEnvelope)
from fleet.layers.armor import redact_pii
from fleet.crypto.foundation import sha256

tmp = tempfile.mkdtemp(prefix="saf_proof_")
master = b"phase5-master"
audit = Ed25519PrivateKey.from_private_bytes(
    HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=b"fleet:audit").derive(b"audit-p5"))
store = JsonStore(os.path.join(tmp, "audit.json"))
bridge = GcpBridge(mode="local", project="project-3ba93cec-8ca6-43c0-ba4")
otel = OtelExporter(use_sdk=False)
cp = ControlPlane(master, audit, store=store, now_fn=lambda: 1000,
                  bridge=bridge, otel=otel, run_id="run-p5")
kek = HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=b"fleet:mem").derive(b"mem-p5")
mem = MemBank(kek)
rt = Runtime(cp, mem, now_fn=lambda: 1000)
r = cp.publish_agent("researcher-1", "researcher", ["emit_evidence"])
a = cp.publish_agent("analyst-1", "analyst", ["qualify", "verify_gate"])
o = cp.publish_agent("operator-1", "operator", ["prepare_artifact", "crm_write"])
human = cp.publish_agent("human-1", "human", ["approve_deny"])
tool_cert, tool_key = cp.root.issue_cert("web_tool", "tool", ["retrieve"], 1000, 9_999_999_999)
cp.registry._certs["web_tool"] = tool_cert

# grant capabilities (gateway authority) before the operator acts
cp.request_authority(r.cert, "emit_evidence")
cp.request_authority(a.cert, "qualify")
cp.request_authority(o.cert, "crm_write")

def _gather(extract):
    out = json.dumps({"citation": "https://src.example/x", "extract": extract}).encode()
    env_t = ToolEnvelope.make(tool_key, "web_tool", out)
    return Researcher(r, rt).gather(env_t, "cloud ERP?", ["citation", "extract"])

def _verified_intel():
    ev1 = _gather("prospect uses cloud ERP")
    ev2 = _gather("VP engineering title")
    return Analyst(a, rt).qualify(ev1, [{
        "claim": "icp_fit=true", "claim_type": "icp_fit",
        "evidence_refs": [ev1.payload["evidence_id"], ev2.payload["evidence_id"]],
    }])

def _artifact_hash(text):
    redacted, _ = redact_pii(text)
    return sha256(redacted.encode("utf-8"))

# --- Beat: human approves a SPECIFIC action, operator executes it (replicated) ---
AID = "act-gcp-proof"
artifact_text = "Write CRM: prospect is ICP fit."
ah = _artifact_hash(artifact_text)
ap_dict = Approval.sign(human.cert, human.key, "operator-1", AID,
                        "crm_write", ah, "approve", "intel verified", 1_001).__dict__
intel = _verified_intel()
res = Operator(o, rt).act(intel, artifact_text, "crm_write", AID, approval=ap_dict)

# --- Replicate to local Firestore mirror ---
mirror = bridge.mirror_docs()

# --- Public-key-only verification (the GCP verifier path) ---
verifier = FirestoreVerifier(mirror, cp.audit.public_key_pem(), cp.root.root_public_pem)
ok = verifier.verify()

# --- Tamper: mutate one replicated entry's body, re-verify (must fail) ---
docs = sorted(mirror, key=lambda d: d.get("payload", {}).get("seq", 0))
target = next((d for d in docs if d.get("payload", {}).get("seq") not in (0, None)), None)
if target is None:
    target = docs[1] if len(docs) > 1 else docs[0]
tampered = dict(target)
tp = dict(tampered["payload"]); tp["payload"] = dict(tp["payload"]); tp["payload"]["result"] = "tampered"
tampered["payload"] = tp
tampered_docs = [d if d is not target else tampered for d in docs]
v2 = FirestoreVerifier(tampered_docs, cp.audit.public_key_pem(), cp.root.root_public_pem)
ok_tampered = v2.verify()

_PROOF = {
    ("GCP_PROJECT" if bridge.mode == "gcp" else "LOCAL_MIRROR_PROJECT"): bridge.project,
    "MODE": bridge.mode,
    "VERIFIER_PATH": "FirestoreVerifier.verify (public-key-only, identical to Cloud Run verifier)",
    "OPERATOR_FINAL": res.get("final"),
    "LOCAL_CHAIN_OK": ok,
    "REPLICATED_DOCS": len([d for d in mirror if d.get("payload", {}).get("kind") is not None]),
    "TAMPER_DETECTED": (not ok_tampered),
    "PRIVATE_KEY_USED_BY_VERIFIER": False,
    "FINAL_COMMITTED": bool(ok and res.get("final") and not ok_tampered),
}
print(json.dumps(_PROOF, indent=2))
_out_path = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "gcp_proof.json")
with open(_out_path, "w") as fh:
    json.dump(_PROOF, fh, indent=2)
