"""
Simple local runner for response SIA sweep - just hit play!

Edit the CONFIG, DETECTION_TIME, and REP variables below to customize your run.
"""

from datetime import UTC
from datetime import datetime
from pathlib import Path

from core.single_run import extract_metrics
from core.single_run import hash_seed
from core.single_run import load_sim_config
from core.single_run import save_results

import laser_polio as lp

# ============================================================================
# CONFIGURE YOUR RUN HERE
# ============================================================================

# Which config to use (relative to scripts/response_sia_sweep/configs/)
CONFIG = "config_nigeria_0sia_response_sens0.8_larger.yaml"

# Detection time in days
DETECTION_TIME = 30

# Replicate number (determines random seed)
REP = 0

# Output directory (relative to repo root)
OUTPUT_DIR = "results"

# ============================================================================
# RUN THE SIMULATION
# ============================================================================

if __name__ == "__main__":
    # Resolve paths
    script_dir = Path(__file__).parent
    config_path = script_dir / "configs" / CONFIG
    output_path = Path(script_dir).parent.parent / OUTPUT_DIR

    # Generate run_id
    run_id = datetime.now(UTC).strftime("local_run_%Y%m%d_%H%M%S")

    # Load config (distribution params are converted automatically in load_sim_config)
    sim_config, _, config_name = load_sim_config(config_path)
    seed = hash_seed(REP)

    # Update config with run-specific settings
    cfg = sim_config.copy()
    cfg.update(
        {
            "t_to_detect": lp.constant(value=DETECTION_TIME),
            "seed": seed,
            "verbose": 1,  # Show progress
        }
    )

    print("Running simulation:")
    print(f"  Config: {CONFIG}")
    print(f"  Detection time: {DETECTION_TIME} days")
    print(f"  Replicate: {REP}")
    print(f"  Seed: {seed}")
    print(f"  Output: {output_path / config_name / run_id}")
    print()

    # Run simulation
    sim = lp.run_sim(**cfg)

    # Extract and save results
    metrics = extract_metrics(sim, config_name, run_id)
    save_results(metrics, output_dir=str(output_path), config_name=config_name, run_id=run_id)

    print()
    print("Results summary:")
    print(f"  Total infected: {metrics['total_infected']}")
    print(f"  Total paralyzed: {metrics['total_paralyzed']}")
    print(f"  Nodes infected: {metrics['nodes_infected']}")
    print(f"  Response SIAs: {metrics['n_response_sias']}")
