"""
Run Response SIA from Snapshot.

Loads a population snapshot and runs a simulation with response SIA enabled.
This allows testing different response SIA parameters on identical outbreak
trajectories up to the snapshot point.

The snapshot provides a deterministic population state. Each response run uses
a seed derived from the rep number, allowing reproducible stochastic variation
across different parameter combinations.

Usage:
    python scripts/ddns_vs_culture_response_sias/core/run_from_snapshot.py \
        --snapshot /shared/snapshots/ddns_vs_culture/config/run_id/snapshot.h5 \
        --config scripts/ddns_vs_culture_response_sias/configs/response_nigeria.yaml \
        --rep 0 \
        --response-time 30 \
        --detection-sensitivity 0.8 \
        --output-dir /shared/results/ddns_vs_culture
"""

import argparse
import hashlib
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


def hash_seed(rep: int) -> int:
    """Generate seed based on replicate number for reproducible stochastic runs."""
    key = f"ddns-vs-culture-rep-{rep}"
    return int(hashlib.md5(key.encode()).hexdigest(), 16) % (2**32)  # noqa: S324


def load_model_config(config_path: str) -> dict:
    """Load model configuration from YAML file."""
    with open(config_path) as f:
        return yaml.safe_load(f)


def extract_timeseries(sim, rep: int, response_time: int, detection_sensitivity: float) -> pd.DataFrame:
    """Extract timeseries of key metrics summed across all nodes."""
    results = sim.results
    n_timesteps = len(sim.datevec)

    return pd.DataFrame(
        {
            "rep": rep,
            "response_time": response_time,
            "detection_sensitivity": detection_sensitivity,
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


def extract_metrics(
    sim,
    rep: int,
    response_time: int,
    detection_sensitivity: float,
    runtime_seconds: float,
) -> dict:
    """Extract metrics from simulation results."""
    results = sim.results

    # Count response SIAs scheduled
    response_sias = [s for s in sim.pars.sia_schedule if s.get("source") == "response"]
    n_response_sia_rounds = len(response_sias)

    return {
        "rep": rep,
        "response_time": response_time,
        "detection_sensitivity": detection_sensitivity,
        "seed": sim.pars.seed,
        "runtime_seconds": round(runtime_seconds, 2),
        "timestamp": datetime.now(UTC).isoformat(),
        # Response SIA metrics
        "n_response_sia_rounds": n_response_sia_rounds,
        # Simulation outcomes
        "total_infections": int(results.I.sum()),
        "new_potentially_paralyzed": int(results.new_potentially_paralyzed.sum()),
        "new_paralyzed": int(results.new_paralyzed.sum()),
        "new_detected_paralyzed": int(results.new_detected_paralyzed.sum()),
    }


def main():
    parser = argparse.ArgumentParser(description="Run response SIA simulation from snapshot")
    parser.add_argument("--snapshot", type=str, required=True, help="Path to snapshot file (.h5)")
    parser.add_argument("--config", type=str, required=True, help="Path to model config YAML")
    parser.add_argument("--rep", type=int, required=True, help="Replicate number (used to generate seed)")
    parser.add_argument("--response-time", type=int, required=True, help="Days from detection to 1st round")
    parser.add_argument("--detection-sensitivity", type=float, required=True, help="Paralysis detection probability")
    parser.add_argument("--n-days-after", type=int, default=None, help="Days to run after snapshot (default: use n_days from config)")
    parser.add_argument("--output-dir", type=str, default="/shared/results", help="Directory for results")
    parser.add_argument("--run-id", type=str, default=None, help="Run ID for organizing results")
    args = parser.parse_args()

    if args.run_id is None:
        args.run_id = os.environ.get("RUN_ID", datetime.now(UTC).strftime("response_%Y%m%d_%H%M%S"))

    snapshot_path = Path(args.snapshot)
    seed = hash_seed(args.rep)

    # Load config
    config = load_model_config(args.config)
    config_name = Path(args.config).stem

    # Configure for response SIA
    config.update(
        {
            "seed": seed,
            "response_sia": True,
            "response_sia_mode": "adjacency",
            "response_sia_time_to_1st_round": lp.constant(args.response_time),
            "paralysis_detection_sensitivity": args.detection_sensitivity,
            "verbose": 0,
            "save_plots": False,
            "save_data": False,
        }
    )
    if args.n_days_after is not None:
        config["n_days"] = args.n_days_after

    # Output paths
    results_dir = Path(args.output_dir) / config_name / args.run_id / "results"
    results_dir.mkdir(parents=True, exist_ok=True)

    try:
        print(f"Running from snapshot: {snapshot_path}")
        print(f"  Rep: {args.rep}, Seed: {seed}")
        print(f"  Response time: {args.response_time}, Detection sensitivity: {args.detection_sensitivity}")

        start_time = time.time()
        sim = lp.run_sim(init_pop_file=str(snapshot_path), **config)
        runtime_seconds = time.time() - start_time

        # Extract and save metrics
        metrics = extract_metrics(sim, args.rep, args.response_time, args.detection_sensitivity, runtime_seconds)

        metrics_df = pd.DataFrame([metrics])
        filename = f"result_rep{args.rep}_rt{args.response_time}_ds{args.detection_sensitivity}.csv"
        metrics_file = results_dir / filename
        metrics_df.to_csv(metrics_file, index=False)
        print(f"Saved metrics to: {metrics_file}")

        # Extract and save timeseries
        timeseries_dir = Path(args.output_dir) / config_name / args.run_id / "timeseries"
        timeseries_dir.mkdir(parents=True, exist_ok=True)
        timeseries_df = extract_timeseries(sim, args.rep, args.response_time, args.detection_sensitivity)
        timeseries_filename = f"timeseries_rep{args.rep}_rt{args.response_time}_ds{args.detection_sensitivity}.csv"
        timeseries_file = timeseries_dir / timeseries_filename
        timeseries_df.to_csv(timeseries_file, index=False)
        print(f"Saved timeseries to: {timeseries_file}")

        print("Simulation complete")
        print(f"  Runtime: {runtime_seconds:.2f}s")
        print(f"  Response SIA rounds: {metrics['n_response_sia_rounds']}")
        print(f"  New paralyzed: {metrics['new_paralyzed']}")

    except Exception as e:
        print(f"Simulation failed: {e}")
        error_dir = results_dir.parent / "errors"
        error_dir.mkdir(parents=True, exist_ok=True)
        error_file = error_dir / f"error_rep{args.rep}_rt{args.response_time}_ds{args.detection_sensitivity}.txt"
        with open(error_file, "w") as f:
            f.write(f"Error: {e}\n")
            f.write(traceback.format_exc())
        raise


if __name__ == "__main__":
    main()
