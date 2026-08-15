"""D21 S1 / R3 — supply-chain lockfile invariants (adversarial).

Locks in the repo must stay pinned (no unbounded `>=` ranges) so CI's pip-audit
is meaningful and installs are reproducible. R3 specifically requires the GCP
deploy layer (`requirements-gcp.lock.txt`) to be a first-class, pinned surface
covered by CI — not an un-audited afterthought. These tests assert the file-level
invariants the CI matrix leg enforces.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# Packages the GCP deploy/console/otel path pulls at runtime (Cloud Run image).
GCP_DEPLOY_PACKAGES = {
    "google-cloud-firestore",
    "google-cloud-pubsub",
    "opentelemetry-api",
    "opentelemetry-sdk",
    "gunicorn",
}


def _parse_pins(path: Path) -> dict:
    pins = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # Expect "name==version"; reject any unbounded range.
        m = re.match(r"^([A-Za-z0-9_.\-]+)\s*==\s*([^\s;]+)", line)
        if not m:
            raise AssertionError(f"non-pinned / unparseable line in {path.name}: {line!r}")
        pins[m.group(1).lower()] = m.group(2)
    return pins


def test_base_lockfile_is_pinned():
    pins = _parse_pins(ROOT / "requirements.lock.txt")
    assert pins, "requirements.lock.txt must pin at least one package"
    # cryptography is the security-critical one — must be pinned exactly.
    assert "cryptography" in pins
    assert pins["cryptography"] == "50.0.0"


def test_gcp_lockfile_is_pinned_and_covers_deploy_surface():
    path = ROOT / "requirements-gcp.lock.txt"
    assert path.exists(), "GCP lockfile must exist (R3: it is a CI-audited surface)"
    pins = _parse_pins(path)
    assert pins, "requirements-gcp.lock.txt must pin packages"
    # Every deploy-time GCP package must be pinned (no `>=`).
    for pkg in GCP_DEPLOY_PACKAGES:
        assert pkg in pins, f"GCP deploy package missing from lockfile: {pkg}"
        assert "==" in f"{pkg}=={pins[pkg]}"  # trivially true post-parse; guards parse contract


def test_no_unbounded_ranges_in_any_lockfile():
    for name in ("requirements.lock.txt", "requirements-gcp.lock.txt"):
        text = (ROOT / name).read_text()
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            # Every dependency line must be an exact pin; reject `>=`, `~=`, `>`, `<`, `*`.
            assert re.match(r"^[A-Za-z0-9_.\-]+\s*==\s*[^\s;]+$", line), \
                f"{name} has a non-pinned line: {line!r}"
