"""
Active Configuration for DDNS vs Culture Response SIA Experiment.

Compares expected 5-year polio case burden when using DDNS vs culture
surveillance to trigger response SIAs, by sweeping over detection
sensitivity and response time parameters and grouping results by method.

Workflow:
1. extract_best_calib_params.py  — pull best trial → update snapshot config
2. submit_snapshot_jobs.py       — run 9y simulation → snapshot.h5
3. submit_response_jobs.py       — sweep (sensitivity × response_time × reps)
4. plot_ddns_vs_culture.py       — compare methods using LAB_METHODS ranges
"""

# Docker image settings
DOCKER_IMAGE_TAG = "ddns-vs-culture-v20260626.1"
LASER_POLIO_VERSION = "latest"
DOCKER_IMAGE = f"idm-docker-staging.packages.idmod.org/laser/laser-polio:{DOCKER_IMAGE_TAG}"

# Config for creating snapshots (uses fixed seed from config file)
SNAPSHOT_CONFIG = "scripts/ddns_vs_culture_response_sias/configs/snapshot_nigeria.yaml"

# Config for response SIA runs (seed set per rep)
RESPONSE_CONFIG = "scripts/ddns_vs_culture_response_sias/configs/response_nigeria.yaml"

# Snapshot output directory on PVC
SNAPSHOT_DIR = "/shared/snapshots/ddns_vs_culture"

# Response SIA output directory on PVC
OUTPUT_DIR = "/shared/results/ddns_vs_culture"

# ── Parameter sweep (same grid for all analyses) ──────────────────────────────

DETECTION_SENSITIVITIES = [0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90, 0.95, 1.00]
RESPONSE_TIMES = [40, 50, 60, 70, 80, 90, 100, 110, 120]  # days from detection to 1st SIA round

N_RESPONSE_REPS = 100

# ── Lab method parameter ranges (used in analysis/plotting, not simulation) ───
#
# These define which (sensitivity, response_time) values are "plausible" for
# each lab method. Update these from literature or expert elicitation.
# All values must be present in DETECTION_SENSITIVITIES and RESPONSE_TIMES above.

LAB_METHODS = {
    "ddns": {
        "label": "DDNS",
        "color": "#1f77b4",  # blue
        "detection_sensitivities": [0.80, 0.85, 0.90, 0.95, 1.00],  # TODO: update from elicitation
        "response_times": [40, 50, 60, 70],  # TODO: update from elicitation
    },
    "culture": {
        "label": "Culture",
        "color": "#d62728",  # red
        "detection_sensitivities": [0.50, 0.55, 0.60, 0.65, 0.70],  # TODO: update from elicitation
        "response_times": [80, 90, 100, 110, 120],  # TODO: update from elicitation
    },
}

# ── Cluster configuration ──────────────────────────────────────────────────────

PVC_NAME = "laser-stg-pvc"
