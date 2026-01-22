import os
import glob
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

BASE_DIR = "output_onenode"
FILENAME_GLOB = "*.csv"   # adjust if your file is named something specific
METRIC = "new_potentially_paralyzed"              # change to 'new_exposed', 'R', etc., if desired

def load_series_from_csv(csv_path):
    """Return (x, y, x_label) aggregated across nodes for the chosen METRIC."""
    df = pd.read_csv(csv_path)
    # Choose x-axis: prefer 'date' if present, else 'timestep'
    if "date" in df.columns:
        # Ensure datetime
        df["date"] = pd.to_datetime(df["date"])
        #agg = np.log( df.groupby("date")[METRIC].sum().sort_index() )
        agg = df.groupby("date")[METRIC].sum().sort_index()
        return agg.index, agg.values, "Date"
    elif "timestep" in df.columns:
        #agg = np.log( df.groupby("timestep")[METRIC].sum().sort_index() )
        agg = df.groupby("timestep")[METRIC].sum().sort_index()
        return agg.index, agg.values, "Timestep"
    else:
        raise ValueError(f"No 'date' or 'timestep' column in {csv_path}")

def main():
    runs = []
    for d in sorted(os.listdir(BASE_DIR)):
        if not d.startswith("seasonal_peak_doy_"):
            continue
        seasonal_peak_doy = d.split("_", 1)[1]
        csvs = glob.glob(os.path.join(BASE_DIR, d, FILENAME_GLOB))
        if not csvs:
            print(f"[WARN] No CSV found in {os.path.join(BASE_DIR, d)}")
            continue
        # If multiple CSVs exist, take the first one (or refine selection here)
        runs.append((seasonal_peak_doy, csvs[0]))

    if not runs:
        raise SystemExit("No seasonal_peak_doy_* runs with CSVs found under 'output/'")

    plt.figure(figsize=(11, 7))

    x_label_used = None
    for seasonal_peak_doy, csv_path in runs:
        x, y, x_label = load_series_from_csv(csv_path)
        if x_label_used is None:
            x_label_used = x_label
        plt.plot(x, y, label=f"SA={seasonal_peak_doy}")

    plt.title(f"{METRIC} over time across seasonal amp sweep (aggregated across nodes)")
    plt.xlabel(x_label_used if x_label_used else "Time")
    plt.ylabel(METRIC)
    plt.legend(ncol=2)
    plt.grid(True)
    plt.tight_layout()
    plt.show()

if __name__ == "__main__":
    main()
