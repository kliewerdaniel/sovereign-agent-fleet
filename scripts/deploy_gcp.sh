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
gcloud run deploy "$SERVICE" \
  --image="$IMAGE" \
  --region="$REGION" \
  --project="$PROJECT" \
  --no-allow-unauthenticated \
  --set-env-vars="FLEET_MODE=gcp,FLEET_PROJECT=${PROJECT}" \
  --min-instances=1

echo "==> Live URL:"
gcloud run services describe "$SERVICE" --region="$REGION" --project "$PROJECT" \
  --format='value(status.url)'

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
