import os
import glob
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import Normalize
from matplotlib.cm import ScalarMappable

# ------------------ CONFIG ------------------
BASE_DIR = "output"
DIR_PREFIX = "seasonal_amplitude_"  # dirs like: seasonal_amplitude_0.30
FILENAME_GLOB = "*.csv"
METRIC = "new_potentially_paralyzed"
ANNOTATE_TRACES = True              # label each line with its amplitude at the end
COLORMAP = "RdBu_r"                 # low amp → blue, high amp → red
LINEWIDTH = 2.0
ALPHA = 0.95
# --------------------------------------------

def parse_amp_from_dir(dirname: str, prefix: str):
    if not dirname.startswith(prefix):
        return None
    try:
        return float(dirname[len(prefix):])
    except ValueError:
        return None

def load_cumulative_series(csv_path):
    """Return (x, y_cum, x_label). y_cum is cumulative METRIC aggregated across nodes over time."""
    df = pd.read_csv(csv_path)

    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])
        series = (
            df.groupby("date")[METRIC]
              .sum()
              .sort_index()
              .cumsum()
        )
        return series.index, series.values, "Date"

    if "timestep" in df.columns:
        series = (
            df.groupby("timestep")[METRIC]
              .sum()
              .sort_index()
              .cumsum()
        )
        return series.index, series.values, "Timestep"

    raise ValueError(f"No 'date' or 'timestep' column in {csv_path}")

def main():
    # Discover runs like output/seasonal_amplitude_X/*.csv
    runs = []
    for d in sorted(os.listdir(BASE_DIR)):
        amp = parse_amp_from_dir(d, DIR_PREFIX)
        if amp is None:
            continue
        csvs = glob.glob(os.path.join(BASE_DIR, d, FILENAME_GLOB))
        if not csvs:
            print(f"[WARN] No CSV found in {os.path.join(BASE_DIR, d)}")
            continue
        runs.append((amp, csvs[0]))

    if not runs:
        raise SystemExit(f"No {DIR_PREFIX}* runs with CSVs found under '{BASE_DIR}/'")

    # Sort by amplitude for monotone color assignment
    runs.sort(key=lambda t: t[0])
    amps = [amp for amp, _ in runs]
    amin, amax = min(amps), max(amps)

    # Color mapping: low amp → blue, high amp → red
    try:
        from matplotlib import colormaps as cmaps  # Matplotlib ≥3.6
        cmap = cmaps.get_cmap(COLORMAP)
    except Exception:
        from matplotlib.cm import get_cmap  # fallback for very old Matplotlib
        cmap = get_cmap(COLORMAP)

    norm = Normalize(vmin=amin, vmax=amax)
    sm = ScalarMappable(norm=norm, cmap=cmap)

    # -------- Plot 1: cumulative time series traces --------
    fig, ax = plt.subplots(figsize=(12, 7))
    x_label_used = None
    final_totals = []  # collect last y for each run, aligned with 'amps'

    for amp, csv_path in runs:
        x, y, x_label = load_cumulative_series(csv_path)
        if x_label_used is None:
            x_label_used = x_label

        color = cmap(norm(amp))
        label = f"{amp:.3f}"
        ax.plot(x, y, label=label, color=color, linewidth=LINEWIDTH, alpha=ALPHA)

        if len(y) > 0:
            final_totals.append(float(y[-1]))
        else:
            final_totals.append(np.nan)

        if ANNOTATE_TRACES and len(x) > 0:
            ax.annotate(
                label,
                xy=(x[-1], y[-1]),
                xytext=(5, 0),
                textcoords="offset points",
                fontsize=8,
                color=color,
                ha="left",
                va="center",
            )

    # Colorbar for Plot 1
    cbar = fig.colorbar(sm, ax=ax, pad=0.01)
    cbar.set_label("seasonal_amplitude")

    ax.set_title(f"Cumulative {METRIC} over time across seasonal_amplitude sweep\n(aggregated across nodes)")
    ax.set_xlabel(x_label_used if x_label_used else "Time")
    ax.set_ylabel(f"Cumulative {METRIC}")
    ax.grid(True, linestyle="--", alpha=0.35)
    fig.tight_layout()
    try:
        fig.autofmt_xdate()
    except Exception:
        pass

    plt.show()

    # -------- Plot 2: seasonal_amplitude vs final cumulative total --------
    fig2, ax2 = plt.subplots(figsize=(8, 5))

    # colors for each point consistent with traces
    point_colors = [cmap(norm(a)) for a in amps]
    ax2.scatter(amps, final_totals, c=point_colors)

    # Optional: connect in sweep order to show trend clearly
    ax2.plot(amps, final_totals, alpha=0.6)

    # Colorbar for Plot 2
    sm2 = ScalarMappable(norm=norm, cmap=cmap)
    sm2.set_array([])
    cbar2 = fig2.colorbar(sm2, ax=ax2, pad=0.01)
    cbar2.set_label("seasonal_amplitude")

    ax2.set_title(f"Final cumulative {METRIC} vs seasonal_amplitude")
    ax2.set_xlabel("seasonal_amplitude")
    ax2.set_ylabel(f"Final cumulative {METRIC}")
    ax2.grid(True, linestyle="--", alpha=0.35)
    fig2.tight_layout()

    plt.show()

if __name__ == "__main__":
    main()
