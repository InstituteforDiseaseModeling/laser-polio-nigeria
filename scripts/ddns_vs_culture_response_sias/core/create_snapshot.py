"""
Create Snapshot - Run calibrated simulation and save population state.

Runs a simulation with calibrated parameters (including a fixed seed from
the config file) and saves a snapshot of the population state at the end
of the simulation. This snapshot can then be used to initialize response
SIA counterfactual scenarios.

The snapshot uses the exact seed specified in the config file to ensure
a deterministic outbreak trajectory.

Usage:
    python scripts/ddns_vs_culture_response_sias/core/create_snapshot.py \
        --config scripts/ddns_vs_culture_response_sias/configs/snapshot_nigeria.yaml \
        --output-dir /shared/snapshots/ddns_vs_culture
"""

import argparse
import os
import time
import traceback
from datetime import UTC
from datetime import datetime
from pathlib import Path

import pandas as pd
import yaml

import laser_polio as lp

# Override lp.root if POLIO_ROOT environment variable is set
if os.getenv("POLIO_ROOT"):
    lp.root = Path(os.getenv("POLIO_ROOT"))


def load_model_config(config_path: str) -> dict:
    """Load model configuration from YAML file."""
    with open(config_path) as f:
        return yaml.safe_load(f)


def extract_timeseries(sim) -> pd.DataFrame:
    """Extract timeseries of key metrics summed across all nodes."""
    results = sim.results
    n_timesteps = len(sim.datevec)

    return pd.DataFrame(
        {
            "date": [str(d) for d in sim.datevec],
            "timestep": range(n_timesteps),
            "susceptible": results.S[:n_timesteps, :].sum(axis=1),
            "exposed": results.E[:n_timesteps, :].sum(axis=1),
            "infected": results.I[:n_timesteps, :].sum(axis=1),
            "recovered": results.R[:n_timesteps, :].sum(axis=1),
            "new_potentially_paralyzed": results.new_potentially_paralyzed[:n_timesteps, :].sum(axis=1),
            "new_paralyzed": results.new_paralyzed[:n_timesteps, :].sum(axis=1),
            "new_detected_paralyzed": results.new_detected_paralyzed[:n_timesteps, :].sum(axis=1),
        }
    )


def extract_snapshot_metrics(sim, runtime_seconds: float) -> dict:
    """Extract metrics about the simulation state at the final timestep."""
    results = sim.results
    final_t = len(sim.datevec) - 1
    snapshot_date = sim.datevec[final_t]

    return {
        "seed": sim.pars.seed,
        "snapshot_date": str(snapshot_date),
        "n_days": len(sim.datevec),
        "runtime_seconds": round(runtime_seconds, 2),
        "timestamp": datetime.now(UTC).isoformat(),
        # Population state at snapshot
        "total_population": int(sim.people.count),
        "infections_at_snapshot": int(results.I[final_t, :].sum()),
        "recovered_at_snapshot": int(results.R[final_t, :].sum()),
        # Cumulative metrics
        "cumulative_infections": int(results.I.sum()),
        "cumulative_paralyzed": int(results.new_paralyzed.sum()),
        "cumulative_detected": int(results.new_detected_paralyzed.sum()),
        # Whether outbreak is active at snapshot
        "has_active_outbreak": int(results.I[final_t, :].sum()) > 0,
    }


def main():
    parser = argparse.ArgumentParser(description="Create population snapshot from calibrated simulation")
    parser.add_argument("--config", type=str, required=True, help="Path to model config YAML (must include seed)")
    parser.add_argument("--output-dir", type=str, default="/shared/snapshots", help="Directory to save snapshots")
    parser.add_argument("--run-id", type=str, default=None, help="Run ID for organizing results")
    args = parser.parse_args()

    if args.run_id is None:
        args.run_id = os.environ.get("RUN_ID", datetime.now(UTC).strftime("snapshot_%Y%m%d_%H%M%S"))

    # Load config
    config = load_model_config(args.config)
    config_name = Path(args.config).stem

    # Verify seed is specified in config
    if "seed" not in config:
        raise ValueError("Config must specify a 'seed' for deterministic snapshot creation")

    seed = config["seed"]
    n_days = config.get("n_days", 365)

    # Update config (keeping the seed and n_days from file)
    config.update(
        {
            "verbose": 0,
            "save_plots": False,
            "save_data": False,
        }
    )

    # Output paths
    snapshot_dir = Path(args.output_dir) / config_name / args.run_id
    snapshot_dir.mkdir(parents=True, exist_ok=True)

    try:
        print(f"Creating snapshot: config={config_name}, seed={seed}, n_days={n_days}")

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

        print("Snapshot creation complete")
        print(f"  Runtime: {runtime_seconds:.2f}s")
        print(f"  Seed used: {seed}")
        print(f"  Has active outbreak: {metrics['has_active_outbreak']}")
        print(f"  Infections at snapshot: {metrics['infections_at_snapshot']}")

    except Exception as e:
        print(f"Snapshot creation failed: {e}")
        error_dir = snapshot_dir / "errors"
        error_dir.mkdir(parents=True, exist_ok=True)
        error_file = error_dir / "error.txt"
        with open(error_file, "w") as f:
            f.write(f"Error: {e}\n")
            f.write(traceback.format_exc())
        raise


if __name__ == "__main__":
    main()
