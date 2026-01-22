# calib/io_utils.py
from __future__ import annotations
import h5py
import numpy as np
import pandas as pd

# This order matches the CSVs you showed earlier.
VECTOR_NAMES = [
    "S", "E", "I", "R", "P",                # 0..4
    "births", "deaths",                     # 5..6
    "new_exposed",                          # 7
    "potentially_paralyzed",                # 8
    "new_potentially_paralyzed",            # 9  <-- what you want
    "new_paralyzed",                        # 10
]

def load_sim_results_h5_to_df(path: str | os.PathLike) -> pd.DataFrame:
    with h5py.File(path, "r") as f:
        tbl = f["/results/table"][...]
    # timestamps (ns) -> datetime
    t_ns = np.asarray(tbl["values_block_2"], np.int64).ravel()
    dates = pd.to_datetime(t_ns, unit="ns", utc=True).tz_convert(None)

    # unpack 11-vector into named columns
    vec = np.asarray(tbl["values_block_3"])  # shape (N, 11)
    if vec.ndim == 1:
        vec = vec.reshape(-1, 11)
    data = {name: vec[:, i].astype(float) for i, name in enumerate(VECTOR_NAMES)}

    # optional: admin labels from values_block_5 (adm0, adm1, adm01, region)
    adm = np.asarray(tbl["values_block_5"]).astype("S")
    adm = np.char.decode(adm, "utf-8", errors="replace")
    adm = adm.reshape(-1, 4)
    df = pd.DataFrame(
        {
            "date": dates,
            "adm0": adm[:, 0],
            "adm1": adm[:, 1],
            "adm01": adm[:, 2],
            "region": adm[:, 3],
            **data,
        }
    ).sort_values("date").reset_index(drop=True)

    # quick sanity: print totals to confirm mapping
    tot = {k: float(df[k].sum()) for k in VECTOR_NAMES}
    print("[PRED DF] sums:", tot)  # run once to verify nonzeros
    return df
