"""
Debug script to test why two configs produce identical results
"""

import yaml

import laser_polio as lp

# Load both configs
config1_path = "scripts/response_sia_sweep/configs/config_nigeria.yaml"
config2_path = "scripts/response_sia_sweep/configs/config_nigeria_1sia_sens1.0.yaml"

print("Loading configs...")
with open(config1_path) as f:
    config1 = yaml.safe_load(f)

with open(config2_path) as f:
    config2 = yaml.safe_load(f)

# Show differences
print("\n=== CONFIG DIFFERENCES ===")
all_keys = set(config1.keys()) | set(config2.keys())
for key in sorted(all_keys):
    val1 = config1.get(key, "NOT SET")
    val2 = config2.get(key, "NOT SET")
    if val1 != val2:
        print(f"{key}:")
        print(f"  config_nigeria.yaml: {val1}")
        print(f"  config_nigeria_1sia_sens1.0.yaml: {val2}")

# Run mini simulations
print("\n=== RUNNING MINI SIMULATIONS ===")
# Set short duration and simple seed for testing
test_config = {
    "n_days": 100,
    "seed": 12345,
    "verbose": 0,
    "response_sia_time_to_1st_round": lp.constant(value=30),
}

# Test config 1
print("\nTesting config_nigeria.yaml...")
cfg1 = {**config1, **test_config}
sim1 = lp.run_sim(**cfg1)

# Check parameters
print(f"  paralysis_detection_sensitivity: {getattr(sim1.pars, 'paralysis_detection_sensitivity', 'NOT SET')}")
print(f"  sia_campaigns_per_year: {getattr(sim1.pars, 'sia_campaigns_per_year', 'NOT SET')}")
print(f"  sia_schedule_source: {getattr(sim1.pars, 'sia_schedule_source', 'NOT SET')}")

# Test config 2
print("\nTesting config_nigeria_1sia_sens1.0.yaml...")
cfg2 = {**config2, **test_config}
sim2 = lp.run_sim(**cfg2)

# Check parameters
print(f"  paralysis_detection_sensitivity: {getattr(sim2.pars, 'paralysis_detection_sensitivity', 'NOT SET')}")
print(f"  sia_campaigns_per_year: {getattr(sim2.pars, 'sia_campaigns_per_year', 'NOT SET')}")
print(f"  sia_schedule_source: {getattr(sim2.pars, 'sia_schedule_source', 'NOT SET')}")

# Check SIA schedules
print("\n=== SIA SCHEDULES ===")
print(f"Config 1 SIA schedule length: {len(getattr(sim1.pars, 'sia_schedule', []))}")
print(f"Config 2 SIA schedule length: {len(getattr(sim2.pars, 'sia_schedule', []))}")

if hasattr(sim1.pars, "sia_schedule") and sim1.pars.sia_schedule:
    print(f"Config 1 first SIA: {sim1.pars.sia_schedule[0] if sim1.pars.sia_schedule else 'None'}")
if hasattr(sim2.pars, "sia_schedule") and sim2.pars.sia_schedule:
    print(f"Config 2 first SIA: {sim2.pars.sia_schedule[0] if sim2.pars.sia_schedule else 'None'}")

# Check if detection is working
print("\n=== DETECTION ARRAYS ===")
print(f"Config 1 has new_detected_paralyzed: {hasattr(sim1.results, 'new_detected_paralyzed')}")
print(f"Config 2 has new_detected_paralyzed: {hasattr(sim2.results, 'new_detected_paralyzed')}")

# Verify Response SIA component exists
print("\n=== RESPONSE SIA COMPONENT ===")
for comp in sim1.instances:
    if "ResponseSIA" in comp.__class__.__name__:
        print("Config 1: ResponseSIA component found")
        break
else:
    print("Config 1: ResponseSIA component NOT FOUND!")

for comp in sim2.instances:
    if "ResponseSIA" in comp.__class__.__name__:
        print("Config 2: ResponseSIA component found")
        break
else:
    print("Config 2: ResponseSIA component NOT FOUND!")

print("\nDone!")
