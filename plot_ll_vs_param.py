import argparse
from pathlib import Path

import optuna
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt


def load_trials_df(study_name: str, storage_url: str) -> pd.DataFrame:
    """Return a DataFrame with trial number, objective value, params, and likelihood component columns."""
    study = optuna.load_study(study_name=study_name, storage=storage_url)

    rows = []
    all_components = set()

    for t in study.trials:
        if t.state.name != "COMPLETE":
            continue

        # 'likelihoods' is a dict you saved in objective(): {comp: value, ..., total_log_likelihood: value}
        lik = t.user_attrs.get("likelihoods", {}) or {}
        all_components |= set(lik.keys())

        row = {
            "trial": t.number,
            "objective_value": t.value,
        }
        # include all parameters to make the DF reusable
        for k, v in (t.params or {}).items():
            row[k] = v
        # flatten likelihoods
        for k, v in lik.items():
            row[f"ll_{k}"] = v
        rows.append(row)

    df = pd.DataFrame(rows)
    # ensure consistent columns even if some components are missing in a few trials
    for k in sorted(all_components):
        col = f"ll_{k}"
        if col not in df.columns:
            df[col] = np.nan
    return df


def plot_ll_vs_param(df: pd.DataFrame, param: str, outdir: Path):
    outdir.mkdir(parents=True, exist_ok=True)

    # pick likelihood columns
    ll_cols = [c for c in df.columns if c.startswith("ll_")]
    # Drop rows missing the parameter
    d = df.dropna(subset=[param])

    # Small multiples
    n = len(ll_cols)
    if n == 0:
        print("[WARN] No likelihood columns found (columns starting with 'll_'). Nothing to plot.")
        return

    ncols = 3
    nrows = int(np.ceil(n / ncols))
    fig, axes = plt.subplots(nrows, ncols, figsize=(5 * ncols, 4 * nrows))
    axes = np.atleast_1d(axes).flatten()

    for ax, col in zip(axes, ll_cols):
        ax.scatter(d[param], d[col], alpha=0.8)
        ax.set_xlabel(param)
        ax.set_ylabel(col)
        ax.set_title(f"{col} vs {param}")
        ax.grid(True, linestyle="--", alpha=0.3)

    # hide any unused subplots
    for i in range(len(ll_cols), len(axes)):
        axes[i].set_visible(False)

    fig.tight_layout()
    fig.savefig(outdir / f"likelihoods_vs_{param}.png", dpi=200)
    plt.close(fig)

    # Also produce one combined figure overlaying all components (optional)
    fig2 = plt.figure(figsize=(7, 5))
    for col in ll_cols:
        plt.scatter(d[param], d[col], alpha=0.6, label=col)
    plt.xlabel(param)
    plt.ylabel("likelihood component value")
    plt.title(f"Likelihood components vs {param}")
    plt.legend(bbox_to_anchor=(1.02, 1), loc="upper left")
    plt.tight_layout()
    fig2.savefig(outdir / f"likelihoods_vs_{param}_overlay.png", dpi=200)
    plt.close(fig2)


def main():
    p = argparse.ArgumentParser(description="Plot Optuna 'likelihoods' vs a parameter from SQLite storage.")
    p.add_argument("--study-name", required=True)
    p.add_argument("--sqlite-path", default="optuna.db",
                   help="Path to the SQLite DB file (default: optuna.db)")
    p.add_argument("--param", default="seasonal_amplitude",
                   help="Parameter name to plot on the x-axis")
    p.add_argument("--outdir", default="optuna_plots", help="Where to save plots & CSV")
    args = p.parse_args()

    storage_url = f"sqlite:///{args.sqlite_path}"

    df = load_trials_df(args.study_name, storage_url)
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    # Save a CSV snapshot for quick inspection
    csv_path = outdir / f"{args.study_name}_trials_likelihoods.csv"
    df.to_csv(csv_path, index=False)
    print(f"[INFO] Wrote {csv_path}")

    # Plot
    if args.param not in df.columns:
        print(f"[WARN] Param '{args.param}' not found in trials. Columns: {sorted(df.columns)}")
    else:
        plot_ll_vs_param(df, args.param, outdir)
        print(f"[INFO] Plots saved to {outdir.resolve()}")


if __name__ == "__main__":
    main()
