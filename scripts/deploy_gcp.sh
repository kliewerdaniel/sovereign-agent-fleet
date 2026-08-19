#!/usr/bin/env bash
# Sovereign Agent Fleet — GCP deploy (D17 approval console + live Firestore mirror)
#
# READ BEFORE RUNNING. This script is ADDITIVE and NON-DESTRUCTIVE to the repo.
# It does NOT run `git push` and does NOT auto-execute end-to-end — review, then run.
#
# Prereqs:
#   - gcloud CLI authenticated to an account with Editor/Owner on $PROJECT
#   - $PROJECT has billing enabled (you confirmed you control billing)
#   - .deploy-venv has google-cloud-* installed (it does) for the seeding step
#
# What this does:
#   1. set active project
#   2. enable required APIs (Run, Cloud Build, Artifact Registry, Firestore, Pub/Sub)
#   3. create the Artifact Registry docker repo (idempotent)
#   4. build + push image via Cloud Build (deployment/Dockerfile)
#   5. create Firestore database (if missing)
#   6. deploy the D17 console to Cloud Run with FLEET_MODE=gcp
#   7. print the live service URL
#   8. (optional, commented) seed a live signed chain into Firestore
#
# CAVEAT — read this before you call it "done":
#   The deployed D17 console is a display/signing shell whose _pending queue is
#   in-memory. With no runtime feeding it over HTTP, it shows an EMPTY queue.
#   The genuine "verifiable on GCP" deliverable here is the Firestore mirror:
#   signed artifacts land in a live collection and a verifier recomputes the
#   hash-chain from public keys only (step 8 seeds that chain). To make the
#   console judge-interactive you must also host the runtime that feeds it
#   (Scope 2 — adds a /queue route + bridges a live ControlPlane to Firestore).

set -euo pipefail

PROJECT="${FLEET_PROJECT:-project-3ba93cec-8ca6-43c0-ba4}"
REGION="${FLEET_REGION:-us-central1}"
SERVICE="fleet-approval-console"
REPO="cloud-run-source-deploy"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT}/${REPO}/${SERVICE}"

echo "==> Target project: $PROJECT   region: $REGION"
gcloud config set project "$PROJECT"

echo "==> Enabling APIs"
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  firestore.googleapis.com \
  pubsub.googleapis.com \
  --project "$PROJECT"

echo "==> Creating Artifact Registry repo (idempotent)"
gcloud artifacts repositories create "$REPO" \
  --repository-format=docker --location="$REGION" \
  --project "$PROJECT" 2>/dev/null \
  || echo "  (repo already exists)"

echo "==> Building + pushing image via Cloud Build"
gcloud builds submit . \
  --config cloudbuild.yaml \
  --substitutions="_IMAGE=${IMAGE}" \
  --project "$PROJECT"

echo "==> Firestore database (create if missing)"
gcloud firestore databases create --region="$REGION" --project "$PROJECT" 2>/dev/null \
  || echo "  (firestore already exists)"

echo "==> Deploying Cloud Run service: $SERVICE"

# Bring the DETERMINISTIC human PUBLIC cert so the console can verify judge
# signatures in the cloud (fail-closed binding). The cert is a pure function of
# HUMAN_SEED (see fleet/crypto/foundation.py + scripts/seed_gcp.py), so we
# re-derive it here — no private key leaves the operator, and the cert survives
# every redeploy (otherwise the console loses its verify binding and rejects
# even valid approvals). Prefer a freshly seeded file if present.
CERT_FILE="scripts/judge_human_cert.b64"
if [[ -r "$CERT_FILE" ]]; then
  FLEET_HUMAN_CERT_PEM="$(cat "$CERT_FILE")"
  echo "  using cert from $CERT_FILE"
else
  # derive deterministically (needs the deploy venv w/ fleet + cryptography)
  FLEET_HUMAN_CERT_PEM="$(.deploy-venv/bin/python - "$PROJECT" <<'PY' 2>/dev/null
import sys, base64, json, time
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from fleet.crypto.foundation import AgentCert
HUMAN_SEED=b"sovereign-fleet-judge-human-v1"
key=Ed25519PrivateKey.from_private_bytes(HKDF(algorithm=hashes.SHA256(),length=32,salt=None,info=b"fleet:human").derive(HUMAN_SEED))
pub=key.public_key().public_bytes(serialization.Encoding.PEM,serialization.PublicFormat.SubjectPublicKeyInfo).decode()
cert=AgentCert(agent_id="human-judge",pubkey_pem=pub,role="human",capabilities=["approve_deny"],issued_at=int(time.time()),expires_at=int(time.time())+86400*365,cert_seq=0,root_sig="0"*128)
print(base64.b64encode(json.dumps(cert.to_dict()).encode()).decode())
PY
)"
  echo "  derived cert inline"
fi

gcloud run deploy "$SERVICE" \
  --image="$IMAGE" \
  --region="$REGION" \
  --project="$PROJECT" \
  --no-allow-unauthenticated \
  --set-env-vars="FLEET_MODE=gcp,FLEET_PROJECT=${PROJECT},FLEET_HUMAN_CERT_PEM=${FLEET_HUMAN_CERT_PEM}" \
  --min-instances=1

echo "==> Live URL:"
gcloud run services describe "$SERVICE" --region="$REGION" --project "$PROJECT" \
  --format='value(status.url)'

# The console is a PUBLICLY READABLE verification shell (shows only verifiable
# data — no private keys), while POST /approve stays fail-closed. A clean
# `--no-allow-unauthenticated` deploy strips any prior public-read binding, so
# re-grant allUsers read here. (If you want reads private too, remove this.)
echo "==> Granting public read (allUsers invoker) — writes stay fail-closed"
gcloud run services add-iam-policy-binding "$SERVICE" \
  --region="$REGION" --project="$PROJECT" \
  --member="allUsers" --role="roles/run.invoker" >/dev/null 2>&1 \
  && echo "  public read enabled" || echo "  (binding unchanged)"

cat <<'NOTE'

---------------------------------------------------------------------------
NEXT STEPS (manual)
---------------------------------------------------------------------------
1. Seed a LIVE signed chain into Firestore so "verifiable on GCP" is true:
     source .deploy-venv/bin/activate
     export GOOGLE_APPLICATION_CREDENTIALS=</path/to/adc.json>   # to $PROJECT
     python demo/gcp_live_proof.py        # runs GcpBridge(mode="gcp")

2. Verify the cloud copy from public keys only (what a judge checks):
     python - <<'PY'
     from fleet.gcp.bridge import GcpBridge
     from fleet.gcp.verify import FirestoreVerifier
     b = GcpBridge(mode="gcp", project="$PROJECT")
     docs = b.mirror_docs()
     # public_key_pem()/root_public_pem come from your seeded ControlPlane
     print("docs in Firestore:", len(docs))
     PY

3. (Scope 2) Make the console judge-interactive: host the runtime that calls
   console.queue(...) over a new /queue route, with a live ControlPlane wired
   to GcpBridge(mode="gcp"). Not covered by this script.
---------------------------------------------------------------------------
NOTE
