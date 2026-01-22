#!/usr/bin/env python3
"""
Test script to verify the response SIA sweep setup works correctly.

This script runs a minimal version of the sweep analysis to ensure all
components are working before running the full analysis.
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import numpy as np
from sweep_response_sia_timing import Config
from sweep_response_sia_timing import extract_metrics
from sweep_response_sia_timing import run_simulation
from sweep_response_sia_timing import run_sweep

import laser_polio as lp


def test_basic_response_sia():
    """Test that basic response SIA simulation works."""
    print("Testing basic response SIA simulation...")

    try:
        # Run a minimal simulation with response SIA enabled
        sim = lp.run_sim(
            regions=["ZAMFARA"],
            start_year=2019,
            n_days=100,  # Short simulation
            pop_scale=0.1,  # Small population for speed
            init_region="ANKA",
            init_prev=50,
            response_sia=True,
            response_sia_time_to_1st_round=lp.poisson(lam=20),
            response_sia_dist=100,
            save_plots=False,
            save_data=False,
            verbose=0,
            seed=42,
        )

        print("✅ Basic response SIA simulation successful")
        print(f"   Total infected: {sim.results.I.sum()}")
        print(f"   Simulation days: {len(sim.results.I)}")

        return True

    except Exception as e:
        print(f"❌ Basic response SIA simulation failed: {e}")
        return False


def test_parameter_sweep_components():
    """Test that sweep script components work."""
    print("\nTesting sweep script components...")

    try:
        # Test config
        config = Config()
        print(f"✅ Config loaded: {len(config.LAMBDA_VALUES)} lambda values")

        # Test single simulation
        print("   Testing single simulation...")
        sim = run_simulation(lam=30, rep=0, config=config)
        print("✅ Single simulation successful")

        # Test metric extraction
        metrics = extract_metrics(sim)
        print(f"✅ Metric extraction successful: {len(metrics)} metrics")
        for key, value in metrics.items():
            print(f"     {key}: {value}")

        return True

    except Exception as e:
        print(f"❌ Sweep components test failed: {e}")
        return False


def test_quick_sweep():
    """Test a quick minimal sweep."""
    print("\nTesting quick sweep...")

    try:
        # Create minimal config for quick test
        config = Config()
        config.LAMBDA_VALUES = np.array([20, 40])  # Only 2 points
        config.N_REPS = 2  # Only 2 reps
        config.N_DAYS = 100  # Short simulation
        config.INIT_PREV = 50  # Fewer initial cases
        config.SAVE_PLOTS = False
        config.SAVE_DATA = False
        config.VERBOSE = 0

        print(f"   Running {len(config.LAMBDA_VALUES)} x {config.N_REPS} = {len(config.LAMBDA_VALUES) * config.N_REPS} simulations")

        results = run_sweep(config)

        print("✅ Quick sweep successful")
        print(f"   Result shape: {results['metrics']['total_infected'].shape}")

        return True

    except Exception as e:
        print(f"❌ Quick sweep test failed: {e}")
        return False


def main():
    """Run all tests."""
    print("Response SIA Sweep Setup Test")
    print("=" * 30)

    tests = [
        test_basic_response_sia,
        test_parameter_sweep_components,
        test_quick_sweep,
    ]

    results = []
    for test in tests:
        results.append(test())

    print("\n" + "=" * 30)
    print("TEST RESULTS")
    print("=" * 30)

    passed = sum(results)
    total = len(results)

    if passed == total:
        print(f"🎉 All {total} tests PASSED!")
        print("\nYou're ready to run the full analysis:")
        print("  python scripts/response_sia_sweep/sweep_response_sia_timing.py --quick")
        return 0
    else:
        print(f"❌ {total - passed} of {total} tests FAILED")
        print("\nPlease fix issues before running the full analysis.")
        return 1


if __name__ == "__main__":
    exit(main())
