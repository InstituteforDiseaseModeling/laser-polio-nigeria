"""
Compare 5-year cumulative case burden for DDNS vs culture surveillance methods.

Loads all response SIA result CSVs, filters by the parameter ranges defined
in LAB_METHODS (active_config.py), and plots:
  1. Violin/box plot: distribution of 5y cumulative paralytic cases per method
  2. Violin/box plot: distribution of 5y cumulative paralytic cases per method
     broken out by detection_sensitivity
  3. Violin/box plot broken out by response_time

Usage:
    python scripts/ddns_vs_culture_response_sias/plot_ddns_vs_culture.py
    python scripts/ddns_vs_culture_response_sias/plot_ddns_vs_culture.py \
        --response-dir results/ddns_vs_culture_response_sias/responses/response_20260701_120000
"""

import argparse
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))

from active_config import LAB_METHODS

LOCAL_BASE = Path("results/ddns_vs_culture_response_sias/responses")


def find_latest_response():
    if not LOCAL_BASE.exists():
        return None
    dirs = sorted([d for d in LOCAL_BASE.iterdir() if d.is_dir()])
    return dirs[-1] if dirs else None


def load_all_results(response_dir: Path) -> pd.DataFrame:
    results_dir = response_dir / "results"
    if not results_dir.exists():
        raise FileNotFoundError(f"Results directory not found: {results_dir}")
    files = sorted(results_dir.glob("result_*.csv"))
    if not files:
        raise FileNotFoundError(f"No result files found in {results_dir}")
    print(f"Loading {len(files)} result files...")
    return pd.concat([pd.read_csv(f) for f in files], ignore_index=True)


def assign_method(df: pd.DataFrame) -> pd.DataFrame:
    """Assign lab method label to each row based on LAB_METHODS parameter ranges."""
    df = df.copy()
    df["method"] = None
    for method_key, method_cfg in LAB_METHODS.items():
        mask = df["detection_sensitivity"].isin(method_cfg["detection_sensitivities"]) & df["response_time"].isin(
            method_cfg["response_times"]
        )
        df.loc[mask, "method"] = method_cfg["label"]
    return df


def get_n_years(response_dir: Path) -> float:
    ts_dir = response_dir / "timeseries"
    if not ts_dir.exists():
        return 5.0
    ts_file = next(ts_dir.glob("timeseries_*.csv"), None)
    if ts_file is None:
        return 5.0
    ts = pd.read_csv(ts_file, usecols=["date"])
    return (len(ts) - 1) / 365.25


def plot_overall_comparison(df_methods: pd.DataFrame, n_years: float, output_dir: Path):
    """Violin plot of total 5y cumulative cases per method."""
    fig, ax = plt.subplots(figsize=(7, 5))

    method_labels = [cfg["label"] for cfg in LAB_METHODS.values()]
    method_colors = [cfg["color"] for cfg in LAB_METHODS.values()]

    data = []
    for cfg in LAB_METHODS.values():
        vals = df_methods.loc[df_methods["method"] == cfg["label"], "new_paralyzed"].values
        data.append(vals)

    parts = ax.violinplot(data, positions=range(len(method_labels)), showmedians=True, showextrema=True)
    for i, (pc, color) in enumerate(zip(parts["bodies"], method_colors)):
        pc.set_facecolor(color)
        pc.set_alpha(0.7)

    ax.set_xticks(range(len(method_labels)))
    ax.set_xticklabels(method_labels, fontsize=13)
    ax.set_ylabel(f"Cumulative paralytic cases ({n_years:.0f}y)", fontsize=12)
    ax.set_title("Expected polio burden by surveillance method\n(VDPV2 response SIAs, 5-year projection)", fontsize=12)

    for i, (vals, color) in enumerate(zip(data, method_colors)):
        med = np.median(vals)
        ax.text(i, ax.get_ylim()[1] * 0.97, f"median={med:.0f}", ha="center", va="top", fontsize=10, color=color)

    fig.tight_layout()
    out = output_dir / "ddns_vs_culture_overall.png"
    plt.savefig(out, dpi=150, bbox_inches="tight")
    print(f"Saved: {out}")
    plt.close(fig)


def plot_by_sensitivity(df_methods: pd.DataFrame, n_years: float, output_dir: Path):
    """Box plot of cases broken out by detection_sensitivity, colored by method."""
    fig, ax = plt.subplots(figsize=(12, 5))

    all_sens = sorted(df_methods["detection_sensitivity"].dropna().unique())
    positions = np.arange(len(all_sens))
    width = 0.35

    for i, (method_key, cfg) in enumerate(LAB_METHODS.items()):
        subset = df_methods[df_methods["method"] == cfg["label"]]
        data_by_sens = [subset.loc[subset["detection_sensitivity"] == s, "new_paralyzed"].values for s in all_sens]
        offset = (i - 0.5) * width
        bp = ax.boxplot(
            data_by_sens,
            positions=positions + offset,
            widths=width * 0.85,
            patch_artist=True,
            manage_ticks=False,
            medianprops={"color": "black", "linewidth": 1.5},
        )
        for patch in bp["boxes"]:
            patch.set_facecolor(cfg["color"])
            patch.set_alpha(0.6)

    ax.set_xticks(positions)
    ax.set_xticklabels([f"{int(s * 100)}%" for s in all_sens], fontsize=9)
    ax.set_xlabel("Detection sensitivity", fontsize=12)
    ax.set_ylabel(f"Cumulative paralytic cases ({n_years:.0f}y)", fontsize=12)
    ax.set_title("Cumulative cases by detection sensitivity and method", fontsize=12)

    handles = [
        plt.Rectangle((0, 0), 1, 1, fc=cfg["color"], alpha=0.7)
        for cfg in LAB_METHODS.values()
    ]
    labels = [cfg["label"] for cfg in LAB_METHODS.values()]
    ax.legend(handles, labels, loc="upper right")

    fig.tight_layout()
    out = output_dir / "ddns_vs_culture_by_sensitivity.png"
    plt.savefig(out, dpi=150, bbox_inches="tight")
    print(f"Saved: {out}")
    plt.close(fig)


def plot_by_response_time(df_methods: pd.DataFrame, n_years: float, output_dir: Path):
    """Box plot of cases broken out by response_time, colored by method."""
    fig, ax = plt.subplots(figsize=(12, 5))

    all_rt = sorted(df_methods["response_time"].dropna().unique())
    positions = np.arange(len(all_rt))
    width = 0.35

    for i, (method_key, cfg) in enumerate(LAB_METHODS.items()):
        subset = df_methods[df_methods["method"] == cfg["label"]]
        data_by_rt = [subset.loc[subset["response_time"] == rt, "new_paralyzed"].values for rt in all_rt]
        offset = (i - 0.5) * width
        bp = ax.boxplot(
            data_by_rt,
            positions=positions + offset,
            widths=width * 0.85,
            patch_artist=True,
            manage_ticks=False,
            medianprops={"color": "black", "linewidth": 1.5},
        )
        for patch in bp["boxes"]:
            patch.set_facecolor(cfg["color"])
            patch.set_alpha(0.6)

    ax.set_xticks(positions)
    ax.set_xticklabels([str(int(rt)) for rt in all_rt], fontsize=9)
    ax.set_xlabel("Response time (days, detection → 1st SIA round)", fontsize=12)
    ax.set_ylabel(f"Cumulative paralytic cases ({n_years:.0f}y)", fontsize=12)
    ax.set_title("Cumulative cases by response time and method", fontsize=12)

    handles = [
        plt.Rectangle((0, 0), 1, 1, fc=cfg["color"], alpha=0.7)
        for cfg in LAB_METHODS.values()
    ]
    labels = [cfg["label"] for cfg in LAB_METHODS.values()]
    ax.legend(handles, labels, loc="upper left")

    fig.tight_layout()
    out = output_dir / "ddns_vs_culture_by_response_time.png"
    plt.savefig(out, dpi=150, bbox_inches="tight")
    print(f"Saved: {out}")
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description="Compare DDNS vs culture response SIA outcomes")
    parser.add_argument("--response-dir", type=str, default=None, help="Path to response results directory")
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
    print(f"Simulation duration: {n_years:.2f} years")

    df = assign_method(df)
    df_methods = df[df["method"].notna()].copy()

    n_unassigned = df["method"].isna().sum()
    if n_unassigned > 0:
        print(f"Note: {n_unassigned} rows not assigned to any method (outside LAB_METHODS ranges)")

    for cfg in LAB_METHODS.values():
        n = (df_methods["method"] == cfg["label"]).sum()
        print(f"  {cfg['label']}: {n} runs")

    output_dir = response_dir
    plot_overall_comparison(df_methods, n_years, output_dir)
    plot_by_sensitivity(df_methods, n_years, output_dir)
    plot_by_response_time(df_methods, n_years, output_dir)

    print("\nDone. Plots saved to:", output_dir)
    return 0


if __name__ == "__main__":
    exit(main())
