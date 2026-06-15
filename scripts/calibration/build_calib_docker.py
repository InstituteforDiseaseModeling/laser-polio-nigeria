"""
Build Docker image for local calibration.
Run with the VS Code play button or from the repo root:

    python scripts/calibration/build_calib_docker.py
"""

import shutil
import subprocess
import sys
import tomllib
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CALIB_REPO = REPO_ROOT / "../laser-polio-calibration"

# ── Versions ──────────────────────────────────────────────────────────────────

with open(REPO_ROOT / "pyproject.toml", "rb") as f:
    NIGERIA_VERSION = tomllib.load(f)["project"]["version"]

with open(CALIB_REPO / "pyproject.toml", "rb") as f:
    CALIB_VERSION = tomllib.load(f)["project"]["version"]

import re

# Read local laser-polio version
with open(REPO_ROOT / "../laser-polio/pyproject.toml", "rb") as f:
    LP_VERSION_LOCAL = tomllib.load(f)["project"]["version"]

# Query Artifactory for the latest available version
_IDM_INDEX = "https://packages.idmod.org/api/pypi/pypi-production/simple"
_result = subprocess.run(
    [sys.executable, "-m", "pip", "index", "versions", "laser-polio", "--pre",
     "--index-url", _IDM_INDEX],
    capture_output=True, text=True,
)
_match = re.search(r"laser.polio \(([^)]+)\)", _result.stdout)
LP_VERSION = _match.group(1) if _match else "unknown"

# ── Config ────────────────────────────────────────────────────────────────────

REGISTRY  = "idm-docker-staging.packages.idmod.org/laser/laser-polio"
LOCAL_TAG = "laser-polio-nigeria:local"
DATE_TAG  = date.today().strftime("%Y-%m-%d")

# ── Helpers ───────────────────────────────────────────────────────────────────

def run(cmd, cwd=REPO_ROOT, quiet=False):
    subprocess.run(
        cmd, cwd=cwd, check=True,
        stdout=subprocess.DEVNULL if quiet else None,
        stderr=subprocess.DEVNULL if quiet else None,
    )

# ── Build ─────────────────────────────────────────────────────────────────────

print(f"laser-polio             v{LP_VERSION}  (Artifactory) | local: v{LP_VERSION_LOCAL}")
if LP_VERSION != LP_VERSION_LOCAL:
    print(f"  WARNING: local v{LP_VERSION_LOCAL} differs from Artifactory v{LP_VERSION} — publish before building if needed")
print(f"laser-polio-calibration v{CALIB_VERSION}  (local wheel)")
print(f"laser-polio-nigeria     v{NIGERIA_VERSION}  (local wheel)")
print()

(REPO_ROOT / "dist").mkdir(exist_ok=True)

print("==> Step 1: Building laser-polio-calibration wheel...")
run([sys.executable, "-m", "build"], cwd=CALIB_REPO, quiet=True)
wheel = next((CALIB_REPO / "dist").glob(
    f"laser_polio_calibration-{CALIB_VERSION}-py3-none-any.whl"
))
shutil.copy(wheel, REPO_ROOT / "dist" / wheel.name)

print("==> Step 2: Building laser-polio-nigeria wheel...")
run([sys.executable, "-m", "build"], quiet=True)

print("\n==> Step 3: Building Docker image...")
run([
    "docker", "buildx", "build",
    "--platform", "linux/amd64",
    "--build-arg", f"LP_VERSION={LP_VERSION}",
    "--build-arg", f"NIGERIA_VERSION={NIGERIA_VERSION}",
    "--build-arg", f"CALIB_VERSION={CALIB_VERSION}",
    "--tag", f"{REGISTRY}:{DATE_TAG}",
    "--tag", f"{REGISTRY}:latest",
    "--tag", LOCAL_TAG,
    "--file", "docker/Dockerfile",
    "--load",
    ".",
])

print(f"\n✓ Build complete!")
print(f"  {LOCAL_TAG}")
print(f"  {REGISTRY}:{DATE_TAG}")
print(f"  {REGISTRY}:latest")
