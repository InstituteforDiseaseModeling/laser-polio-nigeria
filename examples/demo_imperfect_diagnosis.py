"""
Demo: Imperfect Paralytic Polio Diagnosis

This example demonstrates the new paralysis detection sensitivity feature,
which allows modeling imperfect diagnostic tests for paralytic polio cases.

The model now tracks both:
- True paralytic cases (what actually happens)
- Detected paralytic cases (what surveillance observes)
"""

import laser_polio as lp


def demo_imperfect_diagnosis():
    """
    Compare perfect vs imperfect diagnosis scenarios
    """
    print("=== Demo: Imperfect Paralytic Polio Diagnosis ===\n")

    # Scenario 1: Perfect diagnosis (100% sensitivity)
    print("Running Scenario 1: Perfect diagnosis (100% sensitivity)")
    model_perfect = lp.run_sim(
        regions=["ZAMFARA"],
        start_year=2019,
        n_days=180,  # 6 months
        init_region="ANKA",
        init_prev=50,
        seed=12345,
        r0=20,
        p_paralysis=1 / 50,  # Higher rate for demo
        paralysis_detection_sensitivity=1.0,  # Perfect detection
        verbose=0,
        save_plots=False,
        save_data=False,
    )

    true_cases_perfect = model_perfect.results.new_paralyzed.sum()
    detected_cases_perfect = model_perfect.results.new_detected_paralyzed.sum()

    print(f"  True paralytic cases: {true_cases_perfect}")
    print(f"  Detected paralytic cases: {detected_cases_perfect}")
    if true_cases_perfect > 0:
        print(f"  Detection rate: {detected_cases_perfect / true_cases_perfect:.1%}\n")
    else:
        print("  No cases occurred\n")

    # Scenario 2: Imperfect diagnosis (80% sensitivity)
    print("Running Scenario 2: Imperfect diagnosis (80% sensitivity)")
    model_imperfect = lp.run_sim(
        regions=["ZAMFARA"],
        start_year=2019,
        n_days=180,  # 6 months
        init_region="ANKA",
        init_prev=50,
        seed=12345,  # Same seed for comparison
        r0=20,
        p_paralysis=1 / 50,  # Higher rate for demo
        paralysis_detection_sensitivity=0.8,  # 80% sensitivity
        verbose=0,
        save_plots=False,
        save_data=False,
    )

    true_cases_imperfect = model_imperfect.results.new_paralyzed.sum()
    detected_cases_imperfect = model_imperfect.results.new_detected_paralyzed.sum()

    print(f"  True paralytic cases: {true_cases_imperfect}")
    print(f"  Detected paralytic cases: {detected_cases_imperfect}")
    if true_cases_imperfect > 0:
        print(f"  Detection rate: {detected_cases_imperfect / true_cases_imperfect:.1%}\n")

        # Analysis
        print("=== Analysis ===")
        print("Expected detection rate with 80% sensitivity: 80%")
        print(f"Observed detection rate: {detected_cases_imperfect / true_cases_imperfect:.1%}")
        print(f"Difference: {abs(0.8 - detected_cases_imperfect / true_cases_imperfect):.1%}")
    else:
        print("  No cases occurred\n")

    print("\n=== Available Time Series ===")
    print("The model now provides both observed and true case counts:")
    print("- new_paralyzed: Daily true paralytic incidence")
    print("- detected_paralyzed: Cumulative detected paralytic cases")
    print("- new_detected_paralyzed: Daily detected paralytic incidence")
    print("- paralyzed: Cumulative true paralytic cases")

    # Show how Response SIAs now trigger on detected cases
    print("\n=== Response SIA Behavior ===")
    print("Response SIAs now trigger based on detected cases rather than true cases.")
    print("This means:")
    print("- With 80% sensitivity, some outbreaks may be missed")
    print("- Response timing reflects what surveillance actually observes")
    print("- More realistic modeling of public health decision-making")

    return model_perfect, model_imperfect


if __name__ == "__main__":
    # Run the demo
    model_perfect, model_imperfect = demo_imperfect_diagnosis()

    # Optional: Plot comparison if matplotlib is available
    try:
        import matplotlib.pyplot as plt

        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

        # Plot daily incidence
        days = range(len(model_perfect.results.new_paralyzed[:, 0]))

        ax1.plot(days, model_perfect.results.new_paralyzed[:, 0], label="True cases (perfect)", alpha=0.7)
        ax1.plot(days, model_perfect.results.new_detected_paralyzed[:, 0], label="Detected cases (perfect)", alpha=0.7, linestyle="--")
        ax1.plot(days, model_imperfect.results.new_detected_paralyzed[:, 0], label="Detected cases (80% sens)", alpha=0.7, linestyle=":")

        ax1.set_xlabel("Days")
        ax1.set_ylabel("Daily New Cases")
        ax1.set_title("Daily Paralytic Incidence")
        ax1.legend()
        ax1.grid(True, alpha=0.3)

        # Plot cumulative
        ax2.plot(days, model_perfect.results.paralyzed[:, 0], label="True cumulative (perfect)", alpha=0.7)
        ax2.plot(days, model_perfect.results.detected_paralyzed[:, 0], label="Detected cumulative (perfect)", alpha=0.7, linestyle="--")
        ax2.plot(days, model_imperfect.results.detected_paralyzed[:, 0], label="Detected cumulative (80% sens)", alpha=0.7, linestyle=":")

        ax2.set_xlabel("Days")
        ax2.set_ylabel("Cumulative Cases")
        ax2.set_title("Cumulative Paralytic Cases")
        ax2.legend()
        ax2.grid(True, alpha=0.3)

        plt.tight_layout()
        plt.savefig("imperfect_diagnosis_demo.png", dpi=300, bbox_inches="tight")
        print("\nPlot saved as 'imperfect_diagnosis_demo.png'")

    except ImportError:
        print("\nMatplotlib not available - skipping plots")
