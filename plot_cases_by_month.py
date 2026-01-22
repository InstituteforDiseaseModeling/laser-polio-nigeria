# plot_actual_from_synth_h5.py
from pathlib import Path
import h5py
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

H5_PATH = Path("calib/synth_calib/results/synth_data.h5")
DS_PATH = "/epi/table"  # from your inspection

def load_epi_table(h5_path: Path, ds_path: str = DS_PATH) -> pd.DataFrame:
    if not h5_path.exists():
        raise FileNotFoundError(h5_path)
    with h5py.File(h5_path, "r") as f:
        ds = f[ds_path]
        arr = ds[...]  # structured numpy array

    # Extract fields; each field is shape (N, 1) → flatten/ravel
    v_cases = np.asarray(arr["values_block_0"], dtype=float).ravel()
    v_time_ns = np.asarray(arr["values_block_1"], dtype=np.int64).ravel()
    v_dot = np.asarray(arr["values_block_2"]).ravel().astype("S")  # bytes
    dot_names = np.char.decode(v_dot, "utf-8", errors="replace")

    df = pd.DataFrame({
        "date": pd.to_datetime(v_time_ns, unit="ns", utc=True).tz_convert(None),
        "P": v_cases,
        "dot_name": dot_names,
        # "period_idx": np.asarray(arr["values_block_3"]).ravel(),  # optional
    })
    # Basic sanity
    df = df.sort_values("date").reset_index(drop=True)
    return df

def main():
    df = load_epi_table(H5_PATH, DS_PATH)
    print("[INFO] rows:", len(df), "date range:", df["date"].min(), "→", df["date"].max())
    print("[INFO] unique dot_names:", df["dot_name"].nunique())
    print("[INFO] nonzero rows:", int((df["P"] > 0).sum()), "total P:", df["P"].sum())

    # Monthly totals (sum across nodes)
    monthly = (df.groupby(df["date"].dt.to_period("M"))["P"]
                 .sum()
                 .sort_index()
                 .to_timestamp())
    nonzero_months = int((monthly.values > 0).sum())
    print(f"[INFO] monthly length={len(monthly)}, nonzero months={nonzero_months}, first 12:", monthly.values[:12])

    # 12-bin month-of-year totals (sum across all years)
    df_m = df.assign(month=df["date"].dt.month)
    moy12 = (df_m.groupby("month")["P"]
                .sum()
                .reindex(range(1, 13), fill_value=0.0))

    # Plot 1: monthly totals
    plt.figure(figsize=(11, 5))
    plt.plot(monthly.index, monthly.values)
    plt.title("Actual monthly totals (sum across nodes)")
    plt.xlabel("Month")
    plt.ylabel("P")
    plt.grid(True, linestyle="--", alpha=0.4)
    plt.tight_layout()
    plt.gcf().autofmt_xdate()
    plt.show()

    # Plot 2: month-of-year (phase)
    plt.figure(figsize=(9, 4))
    x = np.arange(1, 13)
    plt.bar(x, moy12.values)
    plt.xticks(x, x)
    plt.title("Actual totals by month-of-year (1..12)")
    plt.xlabel("Month-of-year")
    plt.ylabel("P (summed across years)")
    plt.grid(True, axis="y", linestyle="--", alpha=0.4)
    plt.tight_layout()
    plt.show()

if __name__ == "__main__":
    main()
