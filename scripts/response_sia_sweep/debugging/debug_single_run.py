"""
Debug script to test single run with active config
"""

import sys
from pathlib import Path

# Add the core directory to path to import active_config
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "core"))

import yaml
from active_config import ACTIVE_CONFIG

import laser_polio as lp

# Load the active config
config_path = Path(__file__).resolve().parent.parent / "configs" / ACTIVE_CONFIG

print(f"Loading config: {ACTIVE_CONFIG}")
with open(config_path) as f:
    config = yaml.safe_load(f)

# Show the config
print("\n=== CONFIG CONTENTS ===")
important_keys = ["paralysis_detection_sensitivity", "sia_campaigns_per_year", "sia_schedule_source", "response_sia", "r0"]
for key in important_keys:
    if key in config:
        print(f"{key}: {config[key]}")

print("\n=== RUNNING SIMULATION ===")
try:
    sim = lp.run_sim(**config)
    print("\n✓ Simulation completed successfully!")

    # Check SIA schedule
    sia_schedule = getattr(sim.pars, "sia_schedule", [])
    print(f"\nTotal SIA events scheduled: {len(sia_schedule)}")
    if sia_schedule:
        print("First 3 SIA events:")
        for i, sia in enumerate(sia_schedule[:3]):
            print(f"  {i + 1}. Date: {sia.get('date')}, Type: {sia.get('vaccinetype')}, Nodes: {len(sia.get('nodes', []))}")

    # Check results
    print("\n=== RESULTS ===")
    total_infected = sim.results.I_by_strain[:, :, 0].sum()
    total_paralyzed = sim.results.paralyzed[-1, :].sum()
    total_detected = sim.results.detected_paralyzed[-1, :].sum() if hasattr(sim.results, "detected_paralyzed") else "N/A"

    print(f"Total infected (VDPV2): {total_infected}")
    print(f"Total paralyzed (true): {total_paralyzed}")
    print(f"Total paralyzed (detected): {total_detected}")

except Exception as e:
    print(f"\n✗ Simulation failed: {e}")
    import traceback

    traceback.print_exc()

print("\nDone!")
