"""
Test script to compare results from two different configs with same seed
"""

import numpy as np
import yaml

import laser_polio as lp

# Load both configs
config1_path = "scripts/response_sia_sweep/configs/config_nigeria.yaml"
config2_path = "scripts/response_sia_sweep/configs/config_nigeria_1sia_sens1.0.yaml"

print("=" * 70)
print("CONFIG COMPARISON TEST")
print("=" * 70)

print("\nLoading configurations...")
with open(config1_path) as f:
    config1 = yaml.safe_load(f)
    print(f"✓ Loaded {config1_path}")

with open(config2_path) as f:
    config2 = yaml.safe_load(f)
    print(f"✓ Loaded {config2_path}")

# Show key differences
print("\n" + "=" * 70)
print("KEY CONFIG DIFFERENCES")
print("=" * 70)
all_keys = set(config1.keys()) | set(config2.keys())
for key in sorted(all_keys):
    val1 = config1.get(key, "NOT SET")
    val2 = config2.get(key, "NOT SET")
    if val1 != val2:
        print(f"\n{key}:")
        print(f"  config_nigeria.yaml:          {val1}")
        print(f"  config_nigeria_1sia_sens1.0:  {val2}")

# Set common parameters for testing
COMMON_SEED = 42
RESPONSE_TIME = 30  # Days to first response SIA
TEST_DURATION = 365  # Run for 1 year to see differences

test_params = {
    "seed": COMMON_SEED,
    "response_sia_time_to_1st_round": lp.constant(value=RESPONSE_TIME),
    "n_days": TEST_DURATION,
    "verbose": 0,
}

print("\n" + "=" * 70)
print(f"RUNNING SIMULATIONS (seed={COMMON_SEED}, response_time={RESPONSE_TIME}, duration={TEST_DURATION})")
print("=" * 70)

# Run simulation 1
print("\n[1/2] Running config_nigeria.yaml...")
cfg1 = {**config1, **test_params}
try:
    sim1 = lp.run_sim(**cfg1)
    print("✓ Simulation 1 completed successfully")
except Exception as e:
    print(f"✗ Simulation 1 failed: {e}")
    sim1 = None

# Run simulation 2
print("\n[2/2] Running config_nigeria_1sia_sens1.0.yaml...")
cfg2 = {**config2, **test_params}
try:
    sim2 = lp.run_sim(**cfg2)
    print("✓ Simulation 2 completed successfully")
except Exception as e:
    print(f"✗ Simulation 2 failed: {e}")
    sim2 = None

if sim1 and sim2:
    print("\n" + "=" * 70)
    print("PARAMETER CHECK")
    print("=" * 70)

    # Check key parameters
    params_to_check = [
        "paralysis_detection_sensitivity",
        "sia_campaigns_per_year",
        "sia_schedule_source",
        "seed",
        "n_days",
    ]

    for param in params_to_check:
        val1 = getattr(sim1.pars, param, "NOT SET")
        val2 = getattr(sim2.pars, param, "NOT SET")
        match = "✓" if val1 == val2 else "✗"
        print(f"{match} {param:35} Config1: {val1:20} Config2: {val2}")

    print("\n" + "=" * 70)
    print("SIA SCHEDULE ANALYSIS")
    print("=" * 70)

    sia1 = getattr(sim1.pars, "sia_schedule", [])
    sia2 = getattr(sim2.pars, "sia_schedule", [])

    print(f"Config 1 SIA events: {len(sia1)}")
    print(f"Config 2 SIA events: {len(sia2)}")

    if sia1:
        print("\nConfig 1 first 3 SIAs:")
        for i, sia in enumerate(sia1[:3]):
            print(f"  {i + 1}. Date: {sia.get('date')}, Type: {sia.get('vaccinetype')}, Nodes: {len(sia.get('nodes', []))} nodes")

    if sia2:
        print("\nConfig 2 first 3 SIAs:")
        for i, sia in enumerate(sia2[:3]):
            print(f"  {i + 1}. Date: {sia.get('date')}, Type: {sia.get('vaccinetype')}, Nodes: {len(sia.get('nodes', []))} nodes")

    print("\n" + "=" * 70)
    print("RESULTS COMPARISON")
    print("=" * 70)

    # Extract key metrics
    metrics = {}

    # Total infections by strain (VDPV2 = strain 0)
    metrics["total_infected_vdpv2_1"] = sim1.results.I_by_strain[:, :, 0].sum()
    metrics["total_infected_vdpv2_2"] = sim2.results.I_by_strain[:, :, 0].sum()

    # Peak infections
    metrics["peak_infected_1"] = sim1.results.I.sum(axis=1).max()
    metrics["peak_infected_2"] = sim2.results.I.sum(axis=1).max()

    # Geographic spread
    metrics["nodes_infected_1"] = np.sum(sim1.results.I_by_strain[:, :, 0].sum(axis=0) > 0)
    metrics["nodes_infected_2"] = np.sum(sim2.results.I_by_strain[:, :, 0].sum(axis=0) > 0)

    # Paralysis cases (TRUE cases)
    metrics["total_paralyzed_true_1"] = sim1.results.paralyzed[-1, :].sum()
    metrics["total_paralyzed_true_2"] = sim2.results.paralyzed[-1, :].sum()

    # Detected paralysis cases (what surveillance sees)
    if hasattr(sim1.results, "detected_paralyzed"):
        metrics["total_paralyzed_detected_1"] = sim1.results.detected_paralyzed[-1, :].sum()
    else:
        metrics["total_paralyzed_detected_1"] = "N/A"

    if hasattr(sim2.results, "detected_paralyzed"):
        metrics["total_paralyzed_detected_2"] = sim2.results.detected_paralyzed[-1, :].sum()
    else:
        metrics["total_paralyzed_detected_2"] = "N/A"

    # Response SIAs triggered
    response_sias_1 = [s for s in sia1 if s.get("source") == "response"]
    response_sias_2 = [s for s in sia2 if s.get("source") == "response"]
    metrics["n_response_sias_1"] = len(response_sias_1)
    metrics["n_response_sias_2"] = len(response_sias_2)

    # Print comparison
    print(f"{'Metric':<40} {'Config 1':>15} {'Config 2':>15} {'Match':>10}")
    print("-" * 80)

    comparison_metrics = [
        ("Total Infected (VDPV2)", "total_infected_vdpv2_1", "total_infected_vdpv2_2"),
        ("Peak Daily Infected", "peak_infected_1", "peak_infected_2"),
        ("Nodes with Infections", "nodes_infected_1", "nodes_infected_2"),
        ("True Paralysis Cases", "total_paralyzed_true_1", "total_paralyzed_true_2"),
        ("Detected Paralysis Cases", "total_paralyzed_detected_1", "total_paralyzed_detected_2"),
        ("Response SIAs Triggered", "n_response_sias_1", "n_response_sias_2"),
    ]

    for label, key1, key2 in comparison_metrics:
        val1 = metrics[key1]
        val2 = metrics[key2]
        if val1 == "N/A" or val2 == "N/A":
            match = "N/A"
        else:
            match = "✓ SAME" if val1 == val2 else "✗ DIFF"
        print(f"{label:<40} {val1!s:>15} {val2!s:>15} {match:>10}")

    # Check time series
    print("\n" + "=" * 70)
    print("TIME SERIES COMPARISON (first 30 days)")
    print("=" * 70)

    # Daily new infections for first 30 days
    daily_I_1 = sim1.results.I_by_strain[:30, :, 0].sum(axis=1)
    daily_I_2 = sim2.results.I_by_strain[:30, :, 0].sum(axis=1)

    print(f"{'Day':<5} {'Config1 New I':>15} {'Config2 New I':>15} {'Difference':>15}")
    print("-" * 50)

    for day in range(min(30, len(daily_I_1))):
        diff = daily_I_2[day] - daily_I_1[day]
        if daily_I_1[day] > 0 or daily_I_2[day] > 0 or day < 5:  # Show first 5 days + any with infections
            print(f"{day:<5} {daily_I_1[day]:>15.0f} {daily_I_2[day]:>15.0f} {diff:>15.0f}")

    # Final summary
    print("\n" + "=" * 70)
    print("FINAL VERDICT")
    print("=" * 70)

    # Check if results are identical
    key_metrics_same = all(
        [
            metrics["total_infected_vdpv2_1"] == metrics["total_infected_vdpv2_2"],
            metrics["peak_infected_1"] == metrics["peak_infected_2"],
            metrics["nodes_infected_1"] == metrics["nodes_infected_2"],
            metrics["total_paralyzed_true_1"] == metrics["total_paralyzed_true_2"],
        ]
    )

    if key_metrics_same:
        print("❌ RESULTS ARE IDENTICAL - The two configurations produced the same epidemic outcomes!")
        print("\nPossible reasons:")
        print("1. Parameters that differ between configs are not affecting the simulation")
        print("2. The paralysis_detection_sensitivity is 1.0 in both (perfect detection)")
        print("3. The SIA schedule differences are not impacting the outbreak")
    else:
        print("✓ RESULTS ARE DIFFERENT - The configurations produced different epidemic outcomes!")
        print("\nKey differences observed in:")
        if metrics["total_infected_vdpv2_1"] != metrics["total_infected_vdpv2_2"]:
            print(f"  - Total infections: {metrics['total_infected_vdpv2_1']} vs {metrics['total_infected_vdpv2_2']}")
        if metrics["n_response_sias_1"] != metrics["n_response_sias_2"]:
            print(f"  - Response SIAs triggered: {metrics['n_response_sias_1']} vs {metrics['n_response_sias_2']}")

print("\n" + "=" * 70)
print("TEST COMPLETE")
print("=" * 70)
