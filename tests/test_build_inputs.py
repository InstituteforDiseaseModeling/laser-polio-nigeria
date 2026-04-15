"""
Unit tests for build_nigeria_inputs.

These validate the input-building layer independently of the full simulation.
"""

import numpy as np
import pytest

from laser_polio_nigeria.run_sim import build_nigeria_inputs


REQUIRED_OUTPUT_KEYS = {
    "start_date",
    "n_days",
    "pop",
    "sus_by_age_node",
    "cbr",
    "init_prevs",
    "r0_scalars",
    "shp",
    "node_lookup",
    "ri",
    "ri_ipv",
    "sia_schedule",
    "sia_prob",
    "response_sia",
}

# Minimal fast config for all tests in this module
BASE_CONFIGS = {
    "regions": ["ZAMFARA"],
    "start_year": 2018,
    "n_days": 30,
    "init_region": "ANKA",
    "init_prev": 10,
}


def _make_configs(**overrides):
    configs = BASE_CONFIGS.copy()
    configs.update(overrides)
    return configs


def test_returns_required_keys():
    inputs = build_nigeria_inputs(_make_configs(), verbose=0)
    missing = REQUIRED_OUTPUT_KEYS - set(inputs)
    assert not missing, f"Missing keys: {missing}"


def test_population_nonzero():
    inputs = build_nigeria_inputs(_make_configs(), verbose=0)
    assert len(inputs["pop"]) > 0
    assert np.all(inputs["pop"] > 0), "All node populations should be positive"


def test_node_count_consistent():
    inputs = build_nigeria_inputs(_make_configs(), verbose=0)
    n = len(inputs["pop"])
    assert len(inputs["cbr"]) == n
    assert len(inputs["init_prevs"]) == n
    assert len(inputs["r0_scalars"]) == n
    assert len(inputs["ri"]) == n
    assert len(inputs["ri_ipv"]) == n
    assert len(inputs["sia_prob"]) == n
    assert len(inputs["shp"]) == n
    assert len(inputs["node_lookup"]) == n


def test_init_region_seeded():
    inputs = build_nigeria_inputs(_make_configs(init_prev=50), verbose=0)
    # At least one node should have non-zero initial prevalence
    assert np.any(inputs["init_prevs"] > 0)


def test_n_days_passed_through():
    inputs = build_nigeria_inputs(_make_configs(n_days=60), verbose=0)
    assert inputs["n_days"] == 60


def test_pop_scale():
    inputs_full = build_nigeria_inputs(_make_configs(pop_scale=1.0), verbose=0)
    inputs_half = build_nigeria_inputs(_make_configs(pop_scale=0.5), verbose=0)
    # Half-scale pop should be roughly half of full-scale
    ratio = inputs_half["pop"].sum() / inputs_full["pop"].sum()
    assert abs(ratio - 0.5) < 0.01


def test_sia_schedule_default_not_empty():
    # With default sia_source="default", there should be some SIA events over a year.
    # Use start_year=2019: synthetic schedule has mOPV2 campaigns in odd years only.
    inputs = build_nigeria_inputs(_make_configs(n_days=365, start_year=2019), verbose=0)
    assert inputs["sia_schedule"] is not None
    assert len(inputs["sia_schedule"]) > 0, "Expected at least one SIA event in a year"


def test_sia_schedule_none_source():
    inputs = build_nigeria_inputs(_make_configs(sia_schedule_source="none"), verbose=0)
    assert inputs["sia_schedule"] is None


def test_age_pyramid_path_injected():
    # age_pyramid_path should be injected into configs so run_sim can forward it to pars
    configs = _make_configs()
    build_nigeria_inputs(configs, verbose=0)
    assert "age_pyramid_path" in configs, (
        "build_nigeria_inputs should inject age_pyramid_path into configs"
    )


def test_start_date_from_start_year():
    from laser_polio import date as lp_date
    inputs = build_nigeria_inputs(_make_configs(start_year=2020), verbose=0)
    assert inputs["start_date"] == lp_date("2020-01-01")


def test_start_date_override():
    from laser_polio import date as lp_date
    inputs = build_nigeria_inputs(_make_configs(start_date="2020-06-15"), verbose=0)
    assert inputs["start_date"] == lp_date("2020-06-15")
