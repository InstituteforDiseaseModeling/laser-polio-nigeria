"""
Local calibration runner. Edit the config section below and run from the repo root:

    python scripts/calibration/run_calib_local.py

Uses SQLite — no database setup required. Switch QUICK_TEST to False for a full Nigeria run.
Results and the SQLite DB are written to results/<STUDY_NAME>/.
"""

import os
from pathlib import Path

# Import laser_polio_nigeria first — its __init__ loads .env so LASER_POLIO_DATA
# is set before laser_polio_calibration imports trigger load_manifest().
import laser_polio_nigeria as _  # loads .env so LASER_POLIO_DATA is set before calibration imports
from laser_polio_calibration.core.calibrate import main
from laser_polio_nigeria.calibration.build_inputs import build_calibrate_nigeria_inputs

# ── Configuration ────────────────────────────────────────────────────────────

QUICK_TEST = False  # True = Zamfara (~30s/trial); False = full Nigeria

if QUICK_TEST:
    STUDY_NAME   = "zamfara_test"
    MODEL_CONFIG = "zamfara_calib_test.yaml"
    CALIB_CONFIG = "r0.yaml"
    N_TRIALS     = 3
else:
    STUDY_NAME   = "calib_nga_9y_2017_r0_radk_pim_annual_local_20260622"
    MODEL_CONFIG = "nigeria_9y_2017_regions_r0_radk_mmf_ssn_nozi_pim.yaml"
    CALIB_CONFIG = "r0_radk_pim.yaml"
    N_TRIALS     = 1

CONFIG_ROOT  = "config"
N_REPLICATES = 1
RESULTS_PATH = Path("results") / STUDY_NAME

# ── Storage (SQLite, auto-created) ───────────────────────────────────────────

RESULTS_PATH.mkdir(parents=True, exist_ok=True)
os.environ["STORAGE_URL"] = f"sqlite:///{RESULTS_PATH}/calib.db"

# ── Run ──────────────────────────────────────────────────────────────────────

main(
    study_name=STUDY_NAME,
    model_config=MODEL_CONFIG,
    calib_config=CALIB_CONFIG,
    config_root=CONFIG_ROOT,
    fit_function="log_likelihood",
    n_replicates=N_REPLICATES,
    n_trials=N_TRIALS,
    results_path=str(RESULTS_PATH),
    actual_data_file=None,
    dry_run=False,
    build_inputs=build_calibrate_nigeria_inputs,
)
