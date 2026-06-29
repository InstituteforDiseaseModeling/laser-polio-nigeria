"""
Local runner for creating a population snapshot - just hit play!

Edit the CONFIG and OUTPUT_DIR variables below.
The snapshot will be saved at the final timestep of the simulation.
"""

import time
from datetime import UTC
from datetime import datetime
from pathlib import Path

import pandas as pd
from core.create_snapshot import extract_snapshot_metrics
from core.create_snapshot import extract_timeseries
from core.create_snapshot import load_model_config

import laser_polio as lp

# ============================================================================
# CONFIGURE YOUR RUN HERE
# ============================================================================

# Which config to use (relative to scripts/ddns_vs_culture_response_sias/configs/)
CONFIG = "snapshot_nigeria.yaml"

# Output directory (relative to repo root)
OUTPUT_DIR = "results/ddns_vs_culture_response_sias/snapshots"

# ============================================================================
# RUN THE SIMULATION
# ============================================================================

if __name__ == "__main__":
    script_dir = Path(__file__).parent
    config_path = script_dir / "configs" / CONFIG
    output_path = Path(script_dir).parent.parent / OUTPUT_DIR

    run_id = datetime.now(UTC).strftime("local_snapshot_%Y%m%d_%H%M%S")

    # Load config
    config = load_model_config(str(config_path))
    config_name = config_path.stem

    # Verify seed is specified
    if "seed" not in config:
        raise ValueError("Config must specify a 'seed' for deterministic snapshot creation")

    seed = config["seed"]
    n_days = config.get("n_days", 365)

    # Update config
    config.update(
        {
            "verbose": 1,
            "save_plots": False,
            "save_data": False,
        }
    )

    # Output paths
    snapshot_dir = output_path / config_name / run_id
    snapshot_dir.mkdir(parents=True, exist_ok=True)

    print("Creating snapshot:")
    print(f"  Config: {CONFIG}")
    print(f"  Seed: {seed}")
    print(f"  n_days: {n_days}")
    print(f"  Output: {snapshot_dir}")
    print()

    start_time = time.time()
    sim = lp.run_sim(**config)
    runtime_seconds = time.time() - start_time

    # Save snapshot at final timestep
    snapshot_file = snapshot_dir / "snapshot.h5"
    sim.people.save_snapshot(snapshot_file, sim.results.R[:], sim.pars)
    print(f"Saved snapshot to: {snapshot_file}")

    # Extract and save metrics
    metrics = extract_snapshot_metrics(sim, runtime_seconds)
    metrics_df = pd.DataFrame([metrics])
    metrics_file = snapshot_dir / "snapshot_metrics.csv"
    metrics_df.to_csv(metrics_file, index=False)
    print(f"Saved metrics to: {metrics_file}")

    # Extract and save timeseries
    timeseries_df = extract_timeseries(sim)
    timeseries_file = snapshot_dir / "timeseries.csv"
    timeseries_df.to_csv(timeseries_file, index=False)
    print(f"Saved timeseries to: {timeseries_file}")

    print()
    print("Snapshot creation complete!")
    print(f"  Runtime: {runtime_seconds:.2f}s")
    print(f"  Snapshot date: {metrics['snapshot_date']}")
    print(f"  Has active outbreak: {metrics['has_active_outbreak']}")
    print(f"  Infections at snapshot: {metrics['infections_at_snapshot']}")
    print(f"  Cumulative paralyzed: {metrics['cumulative_paralyzed']}")
    print()
    print("Use this snapshot path for response runs:")
    print(f'  SNAPSHOT_PATH = "{snapshot_file}"')
