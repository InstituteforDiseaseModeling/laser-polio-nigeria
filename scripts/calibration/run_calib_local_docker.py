"""
Dockerized local calibration runner. Edit the config section below and run
with the VS Code play button or from the repo root:

    python scripts/calibration/run_calib_local_docker.py

Uses MySQL for AKS environment parity. Prerequisites:
  - Build image first: run build_calib_docker.py
Results are written to results/<STUDY_NAME>/.
"""

import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

# ── Configuration ─────────────────────────────────────────────────────────────

QUICK_TEST = True    # True = Zamfara (~30s/trial); False = full Nigeria

if QUICK_TEST:
    STUDY_NAME   = "zamfara_test"
    MODEL_CONFIG = "zamfara_calib_test.yaml"
    CALIB_CONFIG = "r0.yaml"
    N_TRIALS     = 3
else:
    STUDY_NAME   = "nigeria_calib"
    MODEL_CONFIG = "nigeria_7y_2017_regions_r0_radk_mmf_ssn_nozi_pim.yaml"
    CALIB_CONFIG = "r0_radk_pim.yaml"
    N_TRIALS     = 1

N_REPLICATES = 1

# ── Verify image exists ───────────────────────────────────────────────────────

result = subprocess.run(
    ["docker", "image", "inspect", "laser-polio-nigeria:local"],
    capture_output=True,
)
if result.returncode != 0:
    print("ERROR: Docker image 'laser-polio-nigeria:local' not found.")
    print("       Build it first: run build_calib_docker.py")
    sys.exit(1)

# ── Run ───────────────────────────────────────────────────────────────────────

print(f"Study:  {STUDY_NAME}")
print(f"Model:  {MODEL_CONFIG}")
print(f"Trials: {N_TRIALS}")
print()

env = {
    **os.environ,
    "STUDY_NAME":   STUDY_NAME,
    "MODEL_CONFIG": MODEL_CONFIG,
    "CALIB_CONFIG": CALIB_CONFIG,
    "N_TRIALS":     str(N_TRIALS),
    "N_REPLICATES": str(N_REPLICATES),
}

success = False
try:
    subprocess.run(
        [
            "docker", "compose", "up",
            "--abort-on-container-exit",
            "--exit-code-from", "calib_worker",
        ],
        env=env,
        cwd=REPO_ROOT,
        check=True,
    )
    success = True
except subprocess.CalledProcessError:
    print("\nERROR: Calibration worker exited with an error (see logs above).")
finally:
    subprocess.run(["docker", "compose", "down", "--volumes"], cwd=REPO_ROOT)

if success:
    print(f"\nResults: {REPO_ROOT / 'results' / STUDY_NAME}")
