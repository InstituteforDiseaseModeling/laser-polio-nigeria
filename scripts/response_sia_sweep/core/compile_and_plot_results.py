from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import yaml
from active_config import ACTIVE_CONFIG


def create_summary(results):
    # Group by detection time and calculate the mean and std of the metrics
    grouped = results.groupby("t_to_detect")
    means = grouped.mean()
    stds = grouped.std()

    return means, stds


def create_plotting_dict(df: pd.DataFrame) -> dict:
    """
    Create a dictionary optimized for easy plotting with error bars.

    Args:
        df: Combined results DataFrame

    Returns:
        Dictionary with detection_times, means, and stds for each metric
    """
    # Metrics to summarize
    metrics_columns = [
        col for col in df.columns if col not in ["t_to_detect", "rand_seed", "filename_response_time", "filename_seed", "source_file"]
    ]

    detection_times = sorted(df["t_to_detect"].unique())

    plotting_data = {"detection_times": detection_times, "metrics": {}}

    for metric in metrics_columns:
        if pd.api.types.is_numeric_dtype(df[metric]):
            means = []
            stds = []

            for detection_time in detection_times:
                subset = df[df["t_to_detect"] == detection_time]
                means.append(subset[metric].mean())
                stds.append(subset[metric].std())

            plotting_data["metrics"][metric] = {"means": means, "stds": stds}

    return plotting_data


def plot_summary(df: pd.DataFrame, results_path: str):
    summary = create_plotting_dict(df)
    detection_times = summary["detection_times"]

    # Create 2x2 subplot layout for multiple metrics
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    fig.suptitle("Detection Time Sweep Analysis: Key Metrics", fontsize=16)

    # Plot 1: Total Infected
    ax = axes[0, 0]
    ax.errorbar(
        detection_times,
        summary["metrics"]["total_infected"]["means"],
        yerr=summary["metrics"]["total_infected"]["stds"],
        fmt="o-",
        color="red",
        linewidth=2,
        markersize=8,
        capsize=5,
    )
    ax.set_title("Total Infected vs Detection Time")
    ax.set_xlabel("Detection Time (days)")
    ax.set_ylabel("Total Infected")
    ax.set_yscale("log")
    ax.grid(True, alpha=0.3)

    # Plot 2: Total Paralyzed Cases
    ax = axes[0, 1]
    ax.errorbar(
        detection_times,
        summary["metrics"]["total_paralyzed"]["means"],
        yerr=summary["metrics"]["total_paralyzed"]["stds"],
        fmt="d-",
        color="purple",
        linewidth=2,
        markersize=8,
        capsize=5,
    )
    ax.set_title("Total Paralyzed Cases vs Detection Time")
    ax.set_xlabel("Detection Time (days)")
    ax.set_ylabel("Total Paralyzed Cases")
    ax.grid(True, alpha=0.3)

    # Plot 3: Nodes Infected (Geographic Spread)
    ax = axes[1, 0]
    ax.errorbar(
        detection_times,
        summary["metrics"]["nodes_infected"]["means"],
        yerr=summary["metrics"]["nodes_infected"]["stds"],
        fmt="s-",
        color="orange",
        linewidth=2,
        markersize=8,
        capsize=5,
    )
    ax.set_title("Geographic Spread vs Detection Time")
    ax.set_xlabel("Detection Time (days)")
    ax.set_ylabel("Number of Nodes Infected")
    ax.grid(True, alpha=0.3)

    # Plot 4: Number of Response SIAs
    ax = axes[1, 1]
    ax.errorbar(
        detection_times,
        summary["metrics"]["n_response_sias"]["means"],
        yerr=summary["metrics"]["n_response_sias"]["stds"],
        fmt="^-",
        color="green",
        linewidth=2,
        markersize=8,
        capsize=5,
    )
    ax.set_title("Response SIA Frequency vs Detection Time")
    ax.set_xlabel("Detection Time (days)")
    ax.set_ylabel("Number of Response SIAs")
    ax.grid(True, alpha=0.3)

    plt.tight_layout()

    # Save plots
    png_path = Path("results", results_path, "summary_plot.png")
    plt.savefig(png_path, dpi=200, bbox_inches="tight")
    plt.close()
    print(f"Saved plot to {png_path}")


def main(results_path: str):
    # Load all CSV files and combine them
    csv_path = f"results/{results_path}/results_raw"
    csv_files = list(Path(csv_path).glob("*.csv"))
    dfs = [pd.read_csv(f) for f in csv_files]
    df = pd.concat(dfs, ignore_index=True)

    # Plot results
    plot_summary(df, results_path)


def get_results_path_from_config():
    """Load the results_path from the active config."""
    config_path = Path(__file__).parent.parent / "configs" / ACTIVE_CONFIG
    with open(config_path) as f:
        config = yaml.safe_load(f)
    return config.get("results_path", "results")


if __name__ == "__main__":
    # Get results path from active config instead of hardcoding
    results_path = Path(get_results_path_from_config()).name  # Just get the directory name
    main(results_path=results_path)
    print("Done")
