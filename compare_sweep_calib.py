# compare_sweep_calib.py
from pathlib import Path
import glob
import numpy as np
import pandas as pd
import h5py

# --- EDIT THESE ---
CALIB_ACTUAL = Path("calib/synth_calib/results/synth_data.h5")
SWEEP_BASE   = Path("output")  # dir with seasonal_peak_doy_* subdirs
REF_METRIC   = "new_potentially_paralyzed"  # metric used by sweep traces
DM_SCALE     = 2000.0  # for "counts" view

def load_df_any(path: Path) -> pd.DataFrame:
    """
    Read CSV or LASER-style HDF5 and return a DataFrame with:
      - date (datetime64[ns])
      - P (float)               # for 'actual' from HDF5
      - dot_name (str)
    If CSV, the columns are whatever the file has (but we keep 'date' if present).
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(path)

    ext = path.suffix.lower()
    if ext == ".csv":
        df = pd.read_csv(path)
        # Normalize date if present
        if "date" in df.columns and not pd.api.types.is_datetime64_any_dtype(df["date"]):
            df["date"] = pd.to_datetime(df["date"])
        return df

    if ext in {".h5", ".hdf", ".hdf5"}:
        # Try LASER synth schema: /epi/table with structured fields
        with h5py.File(path, "r") as f:
            if "/epi/table" in f:
                dt = f["/epi/table"][...]
                # fields: values_block_0 (P), values_block_1 (epoch ns), values_block_2 (dot_name)
                v_cases = np.asarray(dt["values_block_0"], float).ravel()
                v_time_ns = np.asarray(dt["values_block_1"], np.int64).ravel()
                v_dot = np.asarray(dt["values_block_2"]).ravel().astype("S")
                dot_names = np.char.decode(v_dot, "utf-8", errors="replace")

                df = pd.DataFrame({
                    "date": pd.to_datetime(v_time_ns, unit="ns", utc=True).tz_convert(None),
                    "P": v_cases,
                    "dot_name": dot_names,
                }).sort_values("date").reset_index(drop=True)
                return df

        # Fallback: try pandas to read a table-like HDF key
        try:
            df = pd.read_hdf(path)  # default key or single table
            if "date" in df.columns and not pd.api.types.is_datetime64_any_dtype(df["date"]):
                df["date"] = pd.to_datetime(df["date"])
            return df
        except Exception:
            # Last resort: try a few keys
            for key in ["/epi", "epi", "/results", "results"]:
                try:
                    df = pd.read_hdf(path, key=key)
                    if "date" in df.columns and not pd.api.types.is_datetime64_any_dtype(df["date"]):
                        df["date"] = pd.to_datetime(df["date"])
                    return df
                except Exception:
                    pass

    raise ValueError(f"Unsupported file format or unrecognized HDF5 schema: {path}")

def cases_by_month(df: pd.DataFrame, case_col: str, scale=1.0) -> np.ndarray:
    if "date" not in df.columns:
        raise ValueError("DataFrame is missing 'date' column after normalization.")
    if not pd.api.types.is_datetime64_any_dtype(df["date"]):
        df = df.copy()
        df["date"] = pd.to_datetime(df["date"])
    monthly = (df.groupby(df["date"].dt.to_period("M"))[case_col]
                 .sum()
                 .sort_index()
                 .astype(float) * scale).values
    return monthly

def show(tag: str, v: np.ndarray):
    v = np.asarray(v, float).ravel()
    print(f"[{tag}] len={len(v)} sum={v.sum():.6f} nonzero={(v>0).sum()} "
          f"min={v.min():.6f} max={v.max():.6f} int(sum)={int(v.sum())}")
    print(f"[{tag}] first12={np.array2string(v[:12], precision=6, floatmode='fixed')}")

def pick_sweep_reference(base: Path) -> Path:
    # Choose a “middle” seasonal_peak_doy_* run as reference
    dirs = sorted([d for d in base.iterdir() if d.is_dir()])
    # If your sweep dirs are named 'seasonal_peak_doy_*', prefer those
    dirs = [d for d in dirs if d.name.startswith("seasonal_peak_doy_")] or dirs
    for d in dirs[len(dirs)//2 : ] + dirs[:len(dirs)//2]:
        csvs = sorted(d.glob("*.csv"))
        if csvs:
            return csvs[0]
    raise RuntimeError(f"No CSVs found under {base}")

def main():
    # Calibration ACTUAL (HDF5): normalize to date/P/dot_name
    dfA = load_df_any(CALIB_ACTUAL)
    vA = cases_by_month(dfA, case_col="P", scale=1.0)
    show("CALIB_ACTUAL cases_by_month (P)", vA)

    # Sweep reference (CSV): use new_potentially_paralyzed
    ref_csv = pick_sweep_reference(SWEEP_BASE)
    dfR = load_df_any(ref_csv)
    if "date" not in dfR.columns:
        raise ValueError(f"{ref_csv} has no 'date' column; cannot compare monthly.")
    vR = cases_by_month(dfR, case_col=REF_METRIC, scale=1.0)
    show(f"SWEEP_REFERENCE {ref_csv.parent.name} cases_by_month ({REF_METRIC})", vR)

    # As seen by DM (integerized “counts” view after scaling)
    vA_cnt   = np.rint(vA * DM_SCALE).astype(int)
    vR_cnt   = np.rint(vR * DM_SCALE).astype(int)
    show("CALIB_ACTUAL cases_by_month_counts", vA_cnt)
    show("SWEEP_REFERENCE cases_by_month_counts", vR_cnt)

if __name__ == "__main__":
    main()
