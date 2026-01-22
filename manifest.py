# src/laser_polio_nigeria/manifest.py

from pathlib import Path
import os

# Base data directory (external, not in repo)
DATA_ROOT = Path(os.environ.get("LASER_POLIO_DATA", "/mnt/data/laser-polio")).resolve()
OUTPUT_ROOT = Path(os.environ.get("LASER_POLIO_OUTPUT", "output")).resolve()

# Input files
AGE_PYRAMID = DATA_ROOT / "demographics" / "Nigeria_age_pyramid_2024.csv"
SYNTH_POP = DATA_ROOT / "synthetic" / "synth_data_nigeria_r014.h5"
MOBILITY_MATRIX = DATA_ROOT / "mobility" / "distance_matrix_africa_adm2.h5"
OBSERVED_CASES = DATA_ROOT / "epi" / "nigeria_observed_cases.csv"
SIA_SCHEDULE = DATA_ROOT / "vaccination" / "sia_schedule.csv"

# Output directories
CALIB_OUTPUT = OUTPUT_ROOT / "calibration"
PLOTS_DIR = OUTPUT_ROOT / "figures"

# Utility
def ensure_all_inputs_exist():
    for f in [AGE_PYRAMID, SYNTH_POP, MOBILITY_MATRIX, OBSERVED_CASES, SIA_SCHEDULE]:
        if not f.exists():
            raise FileNotFoundError(f"Missing input file: {f}")
