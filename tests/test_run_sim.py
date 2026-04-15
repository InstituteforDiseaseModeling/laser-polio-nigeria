"""
Integration tests for lp.run_sim() with build_nigeria_inputs.

All tests use n_days=30, save_plots=False, save_data=False for speed.
Slow tests (Nigeria-scale) are marked with @pytest.mark.slow and skipped by default.
"""

import pytest
import laser_polio as lp
from laser_polio_nigeria.run_sim import build_nigeria_inputs


# Shared fast kwargs for Zamfara tests
ZAMFARA_BASE = dict(
    build_inputs=build_nigeria_inputs,
    regions=["ZAMFARA"],
    start_year=2018,
    n_days=30,
    init_region="ANKA",
    init_prev=10,
    r0=14,
    verbose=0,
    save_plots=False,
    save_data=False,
    seed=1,
)


def _assert_valid_sim(sim, n_days=30):
    """Shared sanity checks for a completed simulation."""
    # sim.nt = n_days + 1 (includes t=0)
    assert sim.nt == n_days + 1
    n_nodes = len(sim.nodes)
    assert sim.results.I.shape == (sim.nt, n_nodes)
    assert sim.results.S.shape == (sim.nt, n_nodes)
    assert sim.results.I.sum() >= 0
    assert sim.results.S.sum() >= 0


def test_zamfara_radiation():
    sim = lp.run_sim(**ZAMFARA_BASE, migration_method="radiation", radiation_k_log10=-0.3)
    _assert_valid_sim(sim)


def test_zamfara_gravity():
    sim = lp.run_sim(**ZAMFARA_BASE, migration_method="gravity", gravity_k=1.0, gravity_k_exponent=-3.0)
    _assert_valid_sim(sim)


def test_zamfara_background_seeding():
    # Background seeding params are passed through as model pars; sim should not crash
    sim = lp.run_sim(
        **ZAMFARA_BASE,
        background_seeding=True,
        background_seeding_freq=10,
        background_seeding_node_frac=0.3,
        background_seeding_prev=1,
    )
    _assert_valid_sim(sim)


def test_zamfara_seed_schedule():
    seed_schedule = [
        {"date": "2018-01-05", "dot_name": "AFRO:NIGERIA:ZAMFARA:BAKURA", "prevalence": 5},
    ]
    sim = lp.run_sim(**ZAMFARA_BASE, seed_schedule=seed_schedule)
    _assert_valid_sim(sim)


def test_zamfara_pim_scalars():
    sim = lp.run_sim(**ZAMFARA_BASE, use_pim_scalars=True)
    _assert_valid_sim(sim)


def test_zamfara_vx_prob_ri_none():
    """Passing vx_prob_ri=None skips RI component without error."""
    sim = lp.run_sim(**ZAMFARA_BASE, vx_prob_ri=None)
    _assert_valid_sim(sim)


def test_results_shape():
    """Results arrays have the expected (nt, n_nodes) shape."""
    sim = lp.run_sim(**ZAMFARA_BASE)
    n_nodes = len(sim.nodes)
    assert sim.results.I.shape == (sim.nt, n_nodes)
    assert sim.results.S.shape == (sim.nt, n_nodes)
    assert sim.results.new_exposed.shape == (sim.nt, n_nodes)


def test_seeded_infections_propagate():
    """init_prev>0 should produce infections in at least the seed node."""
    kwargs = {**ZAMFARA_BASE, "init_prev": 100}
    sim = lp.run_sim(**kwargs)
    # Some infections should have occurred over 30 days with R0=14
    assert sim.results.new_exposed.sum() > 0


def test_higher_seed_produces_more_infections():
    """Higher init_prev should produce at least as many total exposures as lower init_prev."""
    sim_low = lp.run_sim(**{**ZAMFARA_BASE, "init_prev": 1})
    sim_high = lp.run_sim(**{**ZAMFARA_BASE, "init_prev": 200})
    assert sim_high.results.new_exposed.sum() >= sim_low.results.new_exposed.sum()


def test_imperfect_diagnosis_runs():
    """Both detection sensitivity scenarios run without error and produce valid shapes."""
    common = dict(
        build_inputs=build_nigeria_inputs,
        regions=["ZAMFARA"],
        start_year=2019,
        n_days=30,
        init_region="ANKA",
        init_prev=50,
        seed=12345,
        r0=20,
        p_paralysis=1 / 50,
        verbose=0,
        save_plots=False,
        save_data=False,
    )
    sim_perfect = lp.run_sim(**common, paralysis_detection_sensitivity=1.0)
    sim_imperfect = lp.run_sim(**common, paralysis_detection_sensitivity=0.8)

    _assert_valid_sim(sim_perfect)
    _assert_valid_sim(sim_imperfect)

    # Detected cases must never exceed true cases
    assert sim_perfect.results.detected_paralyzed[-1].sum() <= sim_perfect.results.paralyzed[-1].sum()
    assert sim_imperfect.results.detected_paralyzed[-1].sum() <= sim_imperfect.results.paralyzed[-1].sum()


def test_zamfara_snapshot_roundtrip(tmp_path):
    """Save init_pop snapshot, reload it, and confirm sim runs from checkpoint."""
    # First run: initialize only, save snapshot
    lp.run_sim(
        **ZAMFARA_BASE,
        run=False,
        save_init_pop=True,
        results_path=tmp_path,
    )
    init_pop_file = tmp_path / "init_pop.h5"
    assert init_pop_file.exists(), "init_pop.h5 was not saved"

    # Second run: load from snapshot and run
    sim = lp.run_sim(
        **ZAMFARA_BASE,
        init_pop_file=str(init_pop_file),
    )
    _assert_valid_sim(sim)


@pytest.mark.slow
def test_nigeria_full_year():
    """Full Nigeria 1-year run — slow, skipped by default."""
    sim = lp.run_sim(
        build_inputs=build_nigeria_inputs,
        regions=["NIGERIA"],
        start_year=2018,
        n_days=365,
        init_region="BIRINIWA",
        init_prev=200,
        r0=14,
        verbose=0,
        save_plots=False,
        save_data=False,
    )
    assert sim.nt == 366
    assert sim.results.I.shape[1] > 0
