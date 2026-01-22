"""
Enhanced Response SIA Single Run with Better Result Organization
"""

import argparse
import hashlib
import json
import os
import traceback
from datetime import UTC
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

import laser_polio as lp

# Override lp.root if POLIO_ROOT environment variable is set (for Docker/remote execution)
if os.getenv("POLIO_ROOT"):
    lp.root = Path(os.getenv("POLIO_ROOT"))

# Parameters that should be distributions (callable) - convert int/float to lp.constant
DISTRIBUTION_PARAMS = [
    "t_to_detect",
    "response_sia_time_to_1st_round",
]


def load_sim_config(config_input, sweep_only_keys=None):
    """
    Load simulation config from YAML file or dictionary, remove sweep-only keys.

    Args:
        config_input (str | Path | dict): Path to YAML file or config dict.
        sweep_only_keys (list): Optional list of sweep-only keys to remove from sim_config.

    Returns:
        tuple: (sim_config, results_path, config_name)
    """
    # Load YAML or use provided dict
    if isinstance(config_input, str | Path):
        config_path = Path(config_input)
        # Extract config name from filename (e.g., "config_nigeria.yaml" -> "config_nigeria")
        config_name = config_path.stem

        with open(config_input) as f:
            config = yaml.safe_load(f)
    elif isinstance(config_input, dict):
        config = config_input
        config_name = config.get("config_name", "unknown_config")
    else:
        raise TypeError("config_input must be a file path or dictionary")

    # Config is now flattened - extract results_path and create sim_config
    results_path = config.get("results_path", "results")
    sim_config = dict(config)  # shallow copy

    # Remove sweep-only and metadata keys from simulation config
    sweep_only_keys = sweep_only_keys or ["response_time_values", "n_reps", "results_path"]
    for key in sweep_only_keys:
        sim_config.pop(key, None)

    # Convert plain numeric values to distributions where needed
    # (YAML files may specify integers but the model expects callable distributions)
    for param in DISTRIBUTION_PARAMS:
        if param in sim_config and isinstance(sim_config[param], int | float):
            sim_config[param] = lp.constant(value=sim_config[param])

    return sim_config, results_path, config_name


def hash_seed(rep: int) -> int:
    """Generate seed based only on replicate number, so same replicate uses same seed across all response times."""
    key = f"rep-{rep}"
    return int(hashlib.md5(key.encode()).hexdigest(), 16) % (2**32)  # noqa: S324


def extract_metrics(sim, config_name: str, run_id: str):
    """Extract metrics and add metadata about the run."""
    total_infected = sim.results.I_by_strain[:, :, 0].sum()
    peak_infected = sim.results.I.sum(axis=1).max()
    nodes_infected = np.sum(sim.results.I_by_strain[:, :, 0].sum(axis=0) > 0)
    total_nodes = sim.results.I_by_strain[:, :, 0].shape[1]
    daily_infections = sim.results.I_by_strain[:, :, 0].sum(axis=1)
    infected_days = np.where(daily_infections > 0)[0]
    outbreak_duration = len(infected_days) if infected_days.size else 0
    peak_day = np.argmax(daily_infections) if daily_infections.sum() else 0
    sia_schedule = getattr(sim.pars, "sia_schedule", []) or []  # Handle None case
    n_response_sias = len([e for e in sia_schedule if e.get("source") == "response"])
    total_paralyzed = sim.results.paralyzed[-1, :].sum()

    # Add detected paralyzed if available
    total_detected = sim.results.detected_paralyzed[-1, :].sum() if hasattr(sim.results, "detected_paralyzed") else total_paralyzed

    return {
        # Metadata
        "config_name": config_name,
        "run_id": run_id,
        "timestamp": datetime.now(UTC).isoformat(),
        # Original metrics
        "t_to_detect": sim.pars.t_to_detect.pars["value"],
        "rand_seed": sim.pars.seed,
        "total_infected": total_infected,
        "peak_infected": peak_infected,
        "nodes_infected": nodes_infected,
        "geographic_spread_fraction": nodes_infected / total_nodes,
        "n_response_sias": n_response_sias,
        "outbreak_duration": outbreak_duration,
        "time_to_peak": peak_day,
        "total_paralyzed": total_paralyzed,
        "total_detected_paralyzed": total_detected,
        # Add key parameters for verification
        "paralysis_detection_sensitivity": getattr(sim.pars, "paralysis_detection_sensitivity", 1.0),
    }


def save_results(metrics, output_dir: str, config_name: str, run_id: str):
    """Save results with hierarchical organization."""
    # Create hierarchical path: output_dir/config_name/run_id/results_raw/
    results_path = Path(output_dir, config_name, run_id, "results_raw")
    results_path.mkdir(parents=True, exist_ok=True)

    # Save individual result file
    df = pd.DataFrame([metrics])
    suffix = f"time={metrics.get('t_to_detect')}_seed={metrics['rand_seed']}"
    filename = f"result_{suffix}.csv"
    full_path = results_path / filename
    df.to_csv(full_path, index=False)

    print(f"Saved to: {full_path}")

    # Also save a metadata file for this run
    metadata_path = results_path.parent / "metadata.json"
    metadata = {
        "config_name": config_name,
        "run_id": run_id,
        "timestamp": datetime.now(UTC).isoformat(),
        "output_file": str(full_path),
        "detection_time": metrics.get("t_to_detect"),
        "seed": metrics["rand_seed"],
    }

    with open(metadata_path, "w") as f:
        json.dump(metadata, f, indent=2)


def main():
    parser = argparse.ArgumentParser(description="Enhanced single response SIA timing simulation.")
    parser.add_argument("--config", type=str, required=True, help="Path to YAML config file")
    parser.add_argument("--detection_time", type=int, required=True, help="Time to detect outbreak (days)")
    parser.add_argument("--rep", type=int, required=True, help="Replication number")
    parser.add_argument("--output_dir", type=str, default="/shared/results", help="Base folder for results")
    parser.add_argument("--run_id", type=str, default=None, help="Run ID for grouping results (auto-generated if not provided)")
    args = parser.parse_args()

    # Generate run_id if not provided (use env var from Kubernetes job)
    if args.run_id is None:
        # Try to get from environment (set by Kubernetes)
        args.run_id = os.environ.get("RUN_ID", datetime.now(UTC).strftime("run_%Y%m%d_%H%M%S"))

    sim_config, _, config_name = load_sim_config(args.config)
    seed = hash_seed(args.rep)

    cfg = sim_config.copy()
    cfg.update(
        {
            "t_to_detect": lp.constant(value=args.detection_time),
            "seed": seed,
            "verbose": 0,
        }
    )

    try:
        print(f"Running sim: config={config_name}, run_id={args.run_id}, detection_time={args.detection_time}, rep={args.rep}, seed={seed}")
        sim = lp.run_sim(**cfg)
        metrics = extract_metrics(sim, config_name, args.run_id)
        save_results(metrics, output_dir=args.output_dir, config_name=config_name, run_id=args.run_id)
        print("✓ Simulation complete")
    except Exception as e:
        print(f"✗ Simulation failed: {e}")
        # Save error metadata with hierarchical structure
        error_path = Path(args.output_dir, config_name, args.run_id, "errors")
        error_path.mkdir(parents=True, exist_ok=True)
        error_file = error_path / f"error_time={args.detection_time}_rep={args.rep}.txt"
        with open(error_file, "w") as f:
            f.write(f"Error: {e}\n")
            f.write(traceback.format_exc())


if __name__ == "__main__":
    main()
