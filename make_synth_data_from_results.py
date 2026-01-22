#!/usr/bin/env python3
import sys
import os
import pandas as pd

def main():
    if len(sys.argv) < 2:
        print("Usage: python make_synth_data_from_results.py <simulation_results.csv>")
        sys.exit(1)

    sim_path = sys.argv[1]
    outdir = os.path.dirname(sim_path)
    outfile = os.path.join(outdir, "synth_data.csv")

    print(f"[INFO] Reading simulation output: {sim_path}")
    df = pd.read_csv(sim_path)

    required_cols = {"date", "dot_name", "new_paralyzed", "new_potentially_paralyzed"}
    if not required_cols.issubset(df.columns):
        missing = required_cols - set(df.columns)
        raise ValueError(f"Missing columns in input file: {sorted(missing)}")

    # Ensure date column is datetime
    df["date"] = pd.to_datetime(df["date"])
    df["month_start"] = df["date"].values.astype("datetime64[M]")

    # Group by region and month
    grouped = (
        df.groupby(["dot_name", "month_start"])[["new_paralyzed", "new_potentially_paralyzed"]]
          .sum()
          .reset_index()
    )
    grouped["cases"] = grouped["new_paralyzed"]

    # Write to CSV
    grouped.to_csv(outfile, index=False)
    print(f"[INFO] Wrote synth_data.csv to: {outfile}")

if __name__ == "__main__":
    main()
