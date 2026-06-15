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

# ── Config ────────────────────────────────────────────────────────────────────

REGISTRY  = "idm-docker-staging.packages.idmod.org/laser/laser-polio"
LOCAL_TAG = "laser-polio-nigeria:local"
DATE_TAG  = date.today().strftime("%Y-%m-%d")

# ── Helpers ───────────────────────────────────────────────────────────────────

def run(cmd, cwd=REPO_ROOT):
    subprocess.run(cmd, cwd=cwd, check=True)

# ── Build ─────────────────────────────────────────────────────────────────────

print(f"laser-polio-nigeria     v{NIGERIA_VERSION}")
print(f"laser-polio-calibration v{CALIB_VERSION}")
print()

(REPO_ROOT / "dist").mkdir(exist_ok=True)

print("==> Step 1: Building laser-polio-calibration wheel...")
run([sys.executable, "-m", "build"], cwd=CALIB_REPO)
wheel = next((CALIB_REPO / "dist").glob(
    f"laser_polio_calibration-{CALIB_VERSION}-py3-none-any.whl"
))
shutil.copy(wheel, REPO_ROOT / "dist" / wheel.name)

print("\n==> Step 2: Building laser-polio-nigeria wheel...")
run([sys.executable, "-m", "build"])

print("\n==> Step 3: Building Docker image...")
run([
    "docker", "buildx", "build",
    "--platform", "linux/amd64",
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
