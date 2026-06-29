"""
Local runner for response SIA from snapshot - just hit play!

Edit the CONFIG, RESPONSE_TIME, DETECTION_SENSITIVITY, and REP variables below.

First run run_local_snapshot.py to create a snapshot. This script will auto-detect
the latest snapshot, or you can set SNAPSHOT_PATH manually.
"""

import time
from datetime import UTC
from datetime import datetime
from pathlib import Path

import pandas as pd
from core.run_from_snapshot import extract_metrics
from core.run_from_snapshot import extract_timeseries
from core.run_from_snapshot import hash_seed
from core.run_from_snapshot import load_model_config

import laser_polio as lp

# ============================================================================
# CONFIGURE YOUR RUN HERE
# ============================================================================

# Path to snapshot file (output from run_local_snapshot.py)
# Set to None to auto-detect the latest snapshot, or specify a path manually
SNAPSHOT_PATH = None  # Auto-detect latest snapshot

# Which config to use for response runs (relative to scripts/ddns_vs_culture_response_sias/configs/)
CONFIG = "response_nigeria.yaml"

# Days from case detection to first response SIA round
RESPONSE_TIME = 30

# Probability of detecting a paralytic case (0.0 to 1.0)
DETECTION_SENSITIVITY = 0.8

# Replicate number (determines random seed)
REP = 0

# Days to run after snapshot (None = use n_days from config)
N_DAYS_AFTER = None

# Output directory (relative to repo root)
OUTPUT_DIR = "results/ddns_vs_culture_response_sias/responses"

# ============================================================================
# RUN THE SIMULATION
# ============================================================================


def find_latest_snapshot(snapshots_dir: Path, config_name: str) -> Path | None:
    """Find the most recent snapshot for a given config."""
    config_snapshots_dir = snapshots_dir / config_name
    if not config_snapshots_dir.exists():
        return None

    # Find all run directories and sort by name (timestamp-based)
    run_dirs = sorted(config_snapshots_dir.glob("local_snapshot_*"), reverse=True)
    for run_dir in run_dirs:
        snapshot_file = run_dir / "snapshot.h5"
        if snapshot_file.exists():
            return snapshot_file
    return None


if __name__ == "__main__":
    script_dir = Path(__file__).parent
    config_path = script_dir / "configs" / CONFIG
    output_path = Path(script_dir).parent.parent / OUTPUT_DIR

    # Determine snapshot path
    if SNAPSHOT_PATH is None:
        # Auto-detect latest snapshot
        snapshots_dir = Path(script_dir).parent.parent / "results/ddns_vs_culture_response_sias/snapshots"
        snapshot_config_name = "snapshot_nigeria"  # Match the snapshot config name
        snapshot_path = find_latest_snapshot(snapshots_dir, snapshot_config_name)
        if snapshot_path is None:
            print("ERROR: No snapshots found.")
            print()
            print("First run run_local_snapshot.py to create a snapshot.")
            raise FileNotFoundError("No snapshots found")
        print(f"Auto-detected snapshot: {snapshot_path}")
    else:
        snapshot_path = Path(script_dir).parent.parent / SNAPSHOT_PATH

    # Verify snapshot exists
    if not snapshot_path.exists():
        print(f"ERROR: Snapshot not found at: {snapshot_path}")
        print()
        print("First run run_local_snapshot.py to create a snapshot.")
        raise FileNotFoundError(f"Snapshot not found: {snapshot_path}")

    run_id = datetime.now(UTC).strftime("local_response_%Y%m%d_%H%M%S")

    # Load config
    config = load_model_config(str(config_path))
    config_name = config_path.stem

    # Generate seed from rep
    seed = hash_seed(REP)

    # Configure for response SIA
    config.update(
        {
            "seed": seed,
            "response_sia": True,
            "response_sia_mode": "adjacency",
            "response_sia_time_to_1st_round": lp.constant(RESPONSE_TIME),
            "paralysis_detection_sensitivity": DETECTION_SENSITIVITY,
            "verbose": 1,
            "save_plots": False,
            "save_data": False,
        }
    )
    if N_DAYS_AFTER is not None:
        config["n_days"] = N_DAYS_AFTER

    # Output paths
    results_dir = output_path / config_name / run_id / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    timeseries_dir = output_path / config_name / run_id / "timeseries"
    timeseries_dir.mkdir(parents=True, exist_ok=True)

    n_days = config.get("n_days", "unknown")
    print("Running response SIA from snapshot (ddns_vs_culture):")
    print(f"  Snapshot: {snapshot_path}")
    print(f"  Config: {CONFIG}")
    print(f"  Rep: {REP}")
    print(f"  Seed: {seed}")
    print(f"  Response time: {RESPONSE_TIME} days")
    print(f"  Detection sensitivity: {DETECTION_SENSITIVITY}")
    print(f"  n_days: {n_days}")
    print(f"  Output: {output_path / config_name / run_id}")
    print()

    start_time = time.time()
    sim = lp.run_sim(init_pop_file=str(snapshot_path), **config)
    runtime_seconds = time.time() - start_time

    # Extract and save metrics
    metrics = extract_metrics(sim, REP, RESPONSE_TIME, DETECTION_SENSITIVITY, runtime_seconds)
    metrics_df = pd.DataFrame([metrics])
    filename = f"result_rep{REP}_rt{RESPONSE_TIME}_ds{DETECTION_SENSITIVITY}.csv"
    metrics_file = results_dir / filename
    metrics_df.to_csv(metrics_file, index=False)
    print(f"Saved metrics to: {metrics_file}")

    # Extract and save timeseries
    timeseries_df = extract_timeseries(sim, REP, RESPONSE_TIME, DETECTION_SENSITIVITY)
    timeseries_filename = f"timeseries_rep{REP}_rt{RESPONSE_TIME}_ds{DETECTION_SENSITIVITY}.csv"
    timeseries_file = timeseries_dir / timeseries_filename
    timeseries_df.to_csv(timeseries_file, index=False)
    print(f"Saved timeseries to: {timeseries_file}")

    print()
    print("Simulation complete!")
    print(f"  Runtime: {runtime_seconds:.2f}s")
    print(f"  Response SIA rounds: {metrics['n_response_sia_rounds']}")
    print(f"  Total infections: {metrics['total_infections']}")
    print(f"  New paralyzed: {metrics['new_paralyzed']}")
    print(f"  New detected paralyzed: {metrics['new_detected_paralyzed']}")
