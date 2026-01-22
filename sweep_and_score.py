#!/usr/bin/env python3
import os
import glob
import sys
from pathlib import Path
import argparse

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.colors import Normalize
from matplotlib.cm import ScalarMappable

# Make calib/ importable (adjust if needed)
sys.path.append("calib")

from targets import calc_calib_targets_paralysis  # your target extractor
from scoring import compute_nll_dirichlet         # your scoring function


def parse_param_from_dir(dirname: str, prefix: str):
    """Extract float parameter from a directory named like '<prefix><value>'."""
    if not dirname.startswith(prefix):
        return None
    tail = dirname[len(prefix):]
    try:
        return float(tail)
    except ValueError:
        return None


def discover_runs(base_dir: str, dir_prefix: str, file_glob: str):
    """Find (param_value, csv_path) for each run directory."""
    runs = []
    for d in sorted(os.listdir(base_dir)):
        val = parse_param_from_dir(d, dir_prefix)
        if val is None:
            continue
        csvs = glob.glob(os.path.join(base_dir, d, file_glob))
        if not csvs:
            print(f"[WARN] No CSV found in {os.path.join(base_dir, d)}")
            continue
        runs.append((val, csvs[0]))
    runs.sort(key=lambda x: x[0])
    return runs


def build_targets(csv_path: str, model_config_path: Path):
    """
    Use the same extractor for both 'actual' and 'predicted' so the shapes align.
    Treat both as simulated summaries (is_actual_data=False) because they are CSVs
    with 'new_potentially_paralyzed' counts, not 'P' rates.
    """
    return calc_calib_targets_paralysis(
        filename=csv_path,
        model_config_path=model_config_path,
        is_actual_data=False,
    )


def main():
    p = argparse.ArgumentParser(
        description="Score a sweep against a user-provided reference CSV and plot."
    )
    p.add_argument("--base-dir", default="output",
                   help="Root directory containing run subdirectories")
    p.add_argument("--dir-prefix", default="seasonal_peak_doy_",
                   help="Prefix of each run directory (e.g., 'seasonal_peak_doy_')")
    p.add_argument("--file-glob", default="*.csv",
                   help="Pattern to locate the results CSV in each run dir")
    p.add_argument("--model-config", required=True,
                   help="Path to model_config.yaml (needed by target extractor)")
    p.add_argument("--ref-csv", required=True,
                   help="Path to the reference simulation_output.csv to use as 'actual'")
    p.add_argument("--ref-param", type=float, default=None,
                   help="Optional: the parameter value of the reference (draws a vertical line)")
    p.add_argument("--outdir", default="results/score_plots",
                   help="Where to write CSV and plots")
    p.add_argument("--colormap", default="RdBu_r",
                   help="Colormap for param coloring")
    args = p.parse_args()

    base_dir = args.base_dir
    dir_prefix = args.dir_prefix
    file_glob = args.file_glob
    model_config_path = Path(args.model_config)
    ref_csv = Path(args.ref_csv)
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    if not ref_csv.exists():
        raise SystemExit(f"[ERROR] --ref-csv not found: {ref_csv}")

    # 1) Find runs
    runs = discover_runs(base_dir, dir_prefix, file_glob)
    if not runs:
        raise SystemExit(f"No {dir_prefix}* runs with CSVs found under '{base_dir}/'")

    print(f"[INFO] Using reference CSV: {ref_csv}")

    # 2) Build 'actual' from the user-provided reference
    actual = build_targets(str(ref_csv), model_config_path)

    # 3) Score each sweep run vs the reference
    rows = []
    for val, csv_path in runs:
        predicted = build_targets(csv_path, model_config_path)
        scores = compute_nll_dirichlet(actual, predicted)
        row = {
            "param_value": val,
            "total_neg_ll": scores.get("total_log_likelihood", np.nan),
        }
        for k, v in scores.items():
            if k == "total_log_likelihood":
                continue
            row[f"ll_{k}"] = v
        rows.append(row)

    df = pd.DataFrame(rows).sort_values("param_value").reset_index(drop=True)
    csv_out = outdir / f"sweep_scores_vs_reference.csv"
    df.to_csv(csv_out, index=False)
    print(f"[INFO] Wrote {csv_out}")

    # 4) Plots
    vals = df["param_value"].values
    amin, amax = float(vals.min()), float(vals.max())

    # Robust colormap getter (works on modern Matplotlib)
    try:
        from matplotlib import colormaps as cmaps
        cmap = cmaps.get_cmap(args.colormap)
    except Exception:
        from matplotlib.cm import get_cmap
        cmap = get_cmap(args.colormap)

    norm = Normalize(vmin=amin, vmax=amax)

    # (A) Total NLL vs param
    fig, ax = plt.subplots(figsize=(8, 5))
    colors = [cmap(norm(v)) for v in vals]
    y = df["total_neg_ll"].values
    ax.scatter(vals, y, c=colors)
    ax.plot(vals, y, alpha=0.5)
    if args.ref_param is not None:
        ax.axvline(args.ref_param, color="k", linestyle="--", linewidth=1, alpha=0.7, label="reference param")
    ax.set_title("Total negative log-likelihood vs parameter")
    ax.set_xlabel(dir_prefix.rstrip("_"))
    ax.set_ylabel("Total NLL")
    ax.grid(True, linestyle="--", alpha=0.35)
    sm = ScalarMappable(norm=norm, cmap=cmap); sm.set_array([])
    cbar = fig.colorbar(sm, ax=ax, pad=0.01); cbar.set_label(dir_prefix.rstrip("_"))
    if args.ref_param is not None:
        ax.legend(loc="best")
    fig.tight_layout()
    fig.savefig(outdir / "total_nll_vs_param.png", dpi=200)

    # (B) Per-component small multiples
    ll_cols = [c for c in df.columns if c.startswith("ll_")]
    if ll_cols:
        n = len(ll_cols)
        ncols = 3
        nrows = int(np.ceil(n / ncols))
        fig2, axes = plt.subplots(nrows, ncols, figsize=(5 * ncols, 4 * nrows))
        axes = np.atleast_1d(axes).flatten()

        for ax, col in zip(axes, ll_cols):
            yy = df[col].values
            ax.scatter(vals, yy, c=[cmap(norm(v)) for v in vals])
            ax.plot(vals, yy, alpha=0.5)
            if args.ref_param is not None:
                ax.axvline(args.ref_param, color="k", linestyle="--", linewidth=1, alpha=0.7)
            ax.set_xlabel(dir_prefix.rstrip("_"))
            ax.set_ylabel(col)
            ax.grid(True, linestyle="--", alpha=0.35)

        for i in range(len(ll_cols), len(axes)):
            axes[i].set_visible(False)

        sm2 = ScalarMappable(norm=norm, cmap=cmap); sm2.set_array([])
        fig2.colorbar(sm2, ax=axes.tolist(), pad=0.01).set_label(dir_prefix.rstrip("_"))
        fig2.suptitle("Per-component negative log-likelihood vs parameter", y=1.02)
        fig2.tight_layout()
        fig2.savefig(outdir / "component_nll_vs_param.png", dpi=200)

    print(f"[INFO] Plots saved under {outdir.resolve()}")


if __name__ == "__main__":
    main()
