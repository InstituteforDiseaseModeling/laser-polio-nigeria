"""
Demo script for Response SIA (reactive vaccination campaigns).

This demonstrates the ResponseSIA component which triggers vaccination campaigns
in response to detected paralytic polio cases using adjacency-based targeting.

Usage:
    python examples/demo_response_sia.py
"""

import datetime

import sciris as sc

import laser_polio as lp
from laser_polio_nigeria.run_sim import build_nigeria_inputs

###################################
######### USER PARAMETERS #########

config = {
    # Geography
    "regions": ["NIGERIA"],
    "admin_level": 0,
    # Timing
    "start_year": 2017,
    "n_days": 365 * 13,
    # Population
    "pop_scale": 1 / 10,
    "init_region": "ANKA",
    "init_prev": 0,
    "seed_schedule": [
        {"date": "2017-10-01", "dot_name": "AFRO:NIGERIA:JIGAWA:HADEJIA", "prevalence": 100},
        {"date": "2017-10-01", "dot_name": "AFRO:NIGERIA:JIGAWA:GARKI", "prevalence": 100},
        {"date": "2020-07-01", "dot_name": "AFRO:NIGERIA:ZAMFARA:TALATA_MAFARA", "prevalence": 100},
        {"date": "2020-10-01", "dot_name": "AFRO:NIGERIA:NIGER:SULEJA", "prevalence": 100},
    ],
    # Transmission
    "r0": 12.6,
    "migration_method": "radiation",
    "radiation_k_log10": -2.0,
    "max_migr_frac": 0.05,
    "seasonal_amplitude": 0.23,
    "seasonal_peak_doy": 200,
    # Vaccination
    "vx_prob_ri": 0.0,
    # Response SIA
    "response_sia": True,
    "response_sia_mode": "adjacency",
    "response_sia_start_date": datetime.date(2026, 1, 1),
    "response_sia_time_to_1st_round": lp.constant(30),
    "response_sia_2nd_round_gap": 30,
    "response_sia_blackout_duration": 182,
    # Output
    "results_path": "results/demo_response_sia",
    "save_plots": True,
    "save_data": True,
}

######### END OF USER PARS ########
###################################

sim = lp.run_sim(
    **config,
    build_inputs=build_nigeria_inputs,
    use_pim_scalars=True,
    pim_re_center=-0.84,
    pim_re_scale=0.74,
    verbose=2,
    seed=42,
)

# Print the max date in the sia_schedule
print(f"Max date in sia_schedule: {max(s['date'] for s in sim.pars.sia_schedule)}")

# Print summary of response SIAs scheduled
response_sias = [s for s in sim.pars.sia_schedule if s.get("source") == "response"]
print(f"\n{'=' * 60}")
print(f"RESPONSE SIA SUMMARY: {len(response_sias)} rounds scheduled")
print(f"{'=' * 60}")

if response_sias:
    for i, sia in enumerate(response_sias[:5]):
        print(f"  {i + 1}. {sia['date']} - {sia['type']} - {len(sia['nodes'])} nodes")
    if len(response_sias) > 5:
        print(f"  ... and {len(response_sias) - 5} more")

sc.printcyan("\nDone.")
