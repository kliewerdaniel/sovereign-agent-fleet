# Sovereign Agent Fleet -- Cloud Run approval console image.
# Cloud Run hosts ONLY the D17 human-approval console + the verifiable GCP
# artifact mirror. It never holds the root key or signs artifacts (D3/D6).
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    FLEET_MODE=gcp

WORKDIR /app

# Base runtime deps (cryptography/pynacl/argon2-cffi) + the cloud layer
# (firestore/pubsub/otel/gunicorn). Installed together so the image is complete.
COPY requirements.txt requirements-gcp.txt ./
RUN pip install -r requirements.txt -r requirements-gcp.txt

COPY fleet ./fleet

EXPOSE 8080
# Cloud Run injects FLEET_MODE/FLEET_PROJECT/FLEET_HUMAN_CERT_PEM at deploy time.
CMD ["gunicorn", "fleet.gcp.deploy:app", "--bind", "0.0.0.0:8080", "--workers", "1"]
