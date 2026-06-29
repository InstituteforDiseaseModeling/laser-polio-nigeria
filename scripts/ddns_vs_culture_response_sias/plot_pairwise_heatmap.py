"""
Heatmap of mean case difference for all pairwise diagnostic comparisons.

For every pair of (response_time, detection_sensitivity) combos, computes the
mean difference in paralytic cases (DDNS - Culture). Plots as a heatmap with:
  x-axis: sensitivity difference (DDNS - Culture), -50% to +50%
  y-axis: speed difference (DDNS - Culture response time), -80d to +80d
  color:  red = DDNS worse (more cases), blue = DDNS better (fewer cases)

Non-significant cells (bootstrap 95% CI includes zero) are hatched.

Usage:
    python scripts/ddns_vs_culture_response_sias/plot_pairwise_heatmap.py
    python scripts/ddns_vs_culture_response_sias/plot_pairwise_heatmap.py --response-dir results/ddns_vs_culture_response_sias/responses/response_20260627_231925
"""

import argparse
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Rectangle

LOCAL_BASE = Path("results/ddns_vs_culture_response_sias/responses")
N_BOOTSTRAP = 10_000


def find_latest_response():
    if not LOCAL_BASE.exists():
        return None
    dirs = sorted([d for d in LOCAL_BASE.iterdir() if d.is_dir()])
    return dirs[-1] if dirs else None


def load_all_results(response_dir):
    results_dir = response_dir / "results"
    if not results_dir.exists():
        raise FileNotFoundError(f"Results directory not found: {results_dir}")
    files = sorted(results_dir.glob("result_*.csv"))
    if not files:
        raise FileNotFoundError(f"No result files found in {results_dir}")
    print(f"Loading {len(files)} result files...")
    dfs = [pd.read_csv(f) for f in files]
    return pd.concat(dfs, ignore_index=True)


def get_n_years(response_dir):
    ts_dir = response_dir / "timeseries"
    if not ts_dir.exists():
        return None
    ts_file = next(ts_dir.glob("timeseries_*.csv"), None)
    if ts_file is None:
        return None
    ts = pd.read_csv(ts_file, usecols=["date"])
    return (len(ts) - 1) / 365.25


def bootstrap_significance(vals_a, vals_b, n_boot=N_BOOTSTRAP, rng=None):
    """Bootstrap test: is the mean difference significantly different from zero?

    Returns (mean_diff, is_significant) where is_significant is True if the
    95% CI of the bootstrapped mean difference excludes zero.
    """
    if rng is None:
        rng = np.random.default_rng(42)
    n_a, n_b = len(vals_a), len(vals_b)
    diffs = np.empty(n_boot)
    for i in range(n_boot):
        a_mean = vals_a[rng.integers(0, n_a, size=n_a)].mean()
        b_mean = vals_b[rng.integers(0, n_b, size=n_b)].mean()
        diffs[i] = a_mean - b_mean
    ci_lo = np.percentile(diffs, 2.5)
    ci_hi = np.percentile(diffs, 97.5)
    return diffs.mean(), (ci_lo > 0 or ci_hi < 0)


def main():
    parser = argparse.ArgumentParser(description="Pairwise diagnostic comparison heatmap")
    parser.add_argument("--response-dir", type=str, default=None)
    args = parser.parse_args()

    if args.response_dir:
        response_dir = Path(args.response_dir)
    else:
        response_dir = find_latest_response()
        if response_dir is None:
            print(f"No response results found in {LOCAL_BASE}")
            return 1

    print(f"Loading results from: {response_dir}")
    df = load_all_results(response_dir)

    n_years = get_n_years(response_dir)
    if n_years is None:
        print("Warning: Could not determine simulation duration. Assuming 5 years.")
        n_years = 5.0
    print(f"  Simulation duration: {n_years:.2f} years")

    # Build per-rep case arrays per (rt, ds) combo
    rep_lookup = {}
    for (rt, ds), group in df.groupby(["response_time", "detection_sensitivity"]):
        rep_lookup[(rt, ds)] = group["new_paralyzed"].values / n_years

    combos = sorted(rep_lookup.keys())
    print(f"  {len(combos)} parameter combos, computing pairwise comparisons...")

    # Compute all pairwise (sens_diff, speed_diff) -> list of (ddns_combo, culture_combo) pairs
    cell_pairs = defaultdict(list)
    for ddns_combo in combos:
        for culture_combo in combos:
            if ddns_combo == culture_combo:
                continue
            sens_diff = round(ddns_combo[1] - culture_combo[1], 2)
            speed_diff = ddns_combo[0] - culture_combo[0]
            if -0.50 <= sens_diff <= 0.50 and -80 <= speed_diff <= 80:
                cell_pairs[(speed_diff, sens_diff)].append((ddns_combo, culture_combo))

    # For each cell, pool all contributing pairs and bootstrap significance
    print(f"  {len(cell_pairs)} unique cells, bootstrapping significance...")
    rng = np.random.default_rng(42)
    cell_mean = {}
    cell_sig = {}

    for (speed_diff, sens_diff), pairs in cell_pairs.items():
        # Pool per-rep differences across all pairs contributing to this cell
        all_ddns_vals = []
        all_culture_vals = []
        for ddns_combo, culture_combo in pairs:
            all_ddns_vals.append(rep_lookup[ddns_combo])
            all_culture_vals.append(rep_lookup[culture_combo])
        pooled_ddns = np.concatenate(all_ddns_vals)
        pooled_culture = np.concatenate(all_culture_vals)
        mean_diff, is_sig = bootstrap_significance(pooled_ddns, pooled_culture, rng=rng)
        cell_mean[(speed_diff, sens_diff)] = mean_diff
        cell_sig[(speed_diff, sens_diff)] = is_sig

    # Build pivot tables
    all_sens_diffs = sorted({k[1] for k in cell_mean})
    all_speed_diffs = sorted({k[0] for k in cell_mean}, reverse=True)

    mean_matrix = np.full((len(all_speed_diffs), len(all_sens_diffs)), np.nan)
    sig_matrix = np.full((len(all_speed_diffs), len(all_sens_diffs)), False)

    for i, sd in enumerate(all_speed_diffs):
        for j, ss in enumerate(all_sens_diffs):
            if (sd, ss) in cell_mean:
                mean_matrix[i, j] = cell_mean[(sd, ss)]
                sig_matrix[i, j] = cell_sig[(sd, ss)]

    n_sig = sig_matrix.sum()
    n_total = (~np.isnan(mean_matrix)).sum()
    print(f"  Significant cells: {n_sig}/{n_total}")

    # Plot
    fig, ax = plt.subplots(figsize=(12, 8))

    valid = mean_matrix[~np.isnan(mean_matrix)]
    vmax = max(abs(valid.min()), abs(valid.max()))
    im = ax.imshow(
        mean_matrix,
        cmap="RdBu_r",
        aspect="auto",
        vmin=-vmax,
        vmax=vmax,
        interpolation="nearest",
    )

    # Axis labels
    col_labels = [f"{v * 100:+.0f}%" for v in all_sens_diffs]
    row_labels = [f"{int(v):+d}d" for v in all_speed_diffs]
    ax.set_xticks(range(len(col_labels)))
    ax.set_xticklabels(col_labels, fontsize=9, rotation=45, ha="right")
    ax.set_yticks(range(len(row_labels)))
    ax.set_yticklabels(row_labels, fontsize=9)

    # Endpoint labels on x-axis
    ax.set_xlabel("Sensitivity difference (DDNS - Culture)", fontsize=12)
    ax.text(0, 1.08, "← DDNS less sensitive", transform=ax.transAxes, ha="left", fontsize=10, color="grey")
    ax.text(1, 1.08, "DDNS more sensitive →", transform=ax.transAxes, ha="right", fontsize=10, color="grey")

    # Endpoint labels on y-axis
    ax.set_ylabel("Response time difference (DDNS - Culture)", fontsize=12)
    ax.text(-0.14, 1, "← DDNS slower", transform=ax.transAxes, ha="left", va="top", fontsize=10, color="grey", rotation=90)
    ax.text(-0.14, 0, "← DDNS faster", transform=ax.transAxes, ha="left", va="bottom", fontsize=10, color="grey", rotation=90)
    ax.set_title(
        "Mean Difference in Annual Paralytic Cases (DDNS - Culture)\n"
        "Red = DDNS worse, Blue = DDNS better | Hatched = not significant (p > 0.05)",
        fontsize=13,
    )

    cbar = fig.colorbar(im, ax=ax, shrink=0.7)
    cbar.set_label("Mean annual case difference", fontsize=11)

    # Annotate cells and hatch non-significant
    for i in range(len(all_speed_diffs)):
        for j in range(len(all_sens_diffs)):
            val = mean_matrix[i, j]
            if np.isnan(val):
                continue
            text_color = "white" if abs(val) > vmax * 0.6 else "black"
            ax.text(j, i, f"{val:+.1f}", ha="center", va="center", fontsize=7, color=text_color)

            if not sig_matrix[i, j]:
                ax.add_patch(
                    Rectangle(
                        (j - 0.5, i - 0.5),
                        1,
                        1,
                        fill=False,
                        edgecolor="grey",
                        linewidth=0.5,
                        hatch="///",
                        alpha=0.5,
                    )
                )

    fig.tight_layout()
    output_path = response_dir / "pairwise_heatmap.png"
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    print(f"\nSaved: {output_path}")
    plt.show()

    return 0


if __name__ == "__main__":
    exit(main())
