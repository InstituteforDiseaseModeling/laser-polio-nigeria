"""
Plot AFP case counts from an actual_data.csv in two ways:
  1. Monthly timeseries (cases summed across all geographies)
  2. Seasonal profile — cases by calendar month, summed across all years

Run from repo root:
    python scripts/sandbox/plot_actual_cases_timeseries.py [results/some_study]
"""

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

STUDY_DIR = Path("results/nigeria_calib_dockerlocal_20260617v2")
DATA_PATH = STUDY_DIR / "actual_data.csv"
OUT_PATH = STUDY_DIR / "actual_cases_timeseries.png"

df = pd.read_csv(DATA_PATH, parse_dates=["date"])

monthly = df.groupby("date")["P"].sum().reset_index()
monthly.columns = ["date", "cases"]

seasonal = df.copy()
seasonal["month"] = seasonal["date"].dt.month
seasonal = seasonal.groupby("month")["P"].sum().reset_index()
seasonal.columns = ["month", "cases"]
MONTH_LABELS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

fig, axes = plt.subplots(2, 1, figsize=(12, 8))

ax = axes[0]
ax.bar(monthly["date"], monthly["cases"], width=25, color="steelblue", edgecolor="none")
ax.set_title("Monthly AFP Cases — Nigeria (all LGAs summed)")
ax.set_xlabel("Date")
ax.set_ylabel("Cases")
ax.tick_params(axis="x", rotation=45)

ax = axes[1]
ax.bar(seasonal["month"], seasonal["cases"], color="steelblue", edgecolor="none")
ax.set_title("Seasonal Profile — Cases by Calendar Month (all years summed)")
ax.set_xlabel("Month")
ax.set_ylabel("Cases")
ax.set_xticks(range(1, 13))
ax.set_xticklabels(MONTH_LABELS)

plt.tight_layout()
plt.savefig(OUT_PATH, dpi=150, bbox_inches="tight")
print(f"Saved: {OUT_PATH}")
plt.show()
