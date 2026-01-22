#!/usr/bin/env python3
"""
Minimal best-trial pipeline: load best trial → run one sim → (optional) MP4 → done.

Run locally:
  python best_trial_pipeline.py \
    --study-name MY_STUDY \
    --storage-url sqlite:///optuna.db \
    --model-config zamfara.yaml \
    --results-path results/MY_STUDY/best_trial \
    --save-plots

Run in AKS (inside your container/Job):
  python best_trial_pipeline.py \
    --study-name $STUDY_NAME \
    --storage-url mysql+pymysql://$MYSQL_USER:$MYSQL_PASSWORD@mysql:3306/$MYSQL_DB \
    --model-config $MODEL_CONFIG \
    --results-path /shared/results/$STUDY_NAME/best_trial \
    --save-plots
"""

from __future__ import annotations

import argparse
import logging
import os
from pathlib import Path

import numpy as np
import optuna
import pandas as pd
import sciris as sc
import yaml

import laser_polio as lp
from laser_polio.utils import prep_actual_data_for_calibration

# ---------------------------
# Helpers
# ---------------------------


def normalize_storage_url(storage_url: str) -> str:
    """
    Normalize Optuna storage URL so the same script works on laptop and in-cluster.
    - Rewrite 'localhost:3307' → 'mysql:3306' (typical AKS service name).
    - If MYSQL_* envs are set and URL contains 'localhost', build a cluster URL.
    """
    if "localhost:3307" in storage_url:
        storage_url = storage_url.replace("localhost:3307", "mysql:3306")
    u = os.getenv("MYSQL_USER")
    p = os.getenv("MYSQL_PASSWORD")
    db = os.getenv("MYSQL_DB")
    if u and p and db and "localhost" in storage_url:
        storage_url = f"mysql+pymysql://{u}:{p}@mysql:3306/{db}"
    return storage_url


def load_best(study_name: str, storage_url: str):
    """
    Return (best_params, chosen_seed:int, best_value, best_trial_id).
    Picks seed tied to the lowest replicate score when available.
    """
    storage_url = normalize_storage_url(storage_url)
    logging.info("Loading Optuna study=%s", study_name)
    study = optuna.load_study(study_name=study_name, storage=storage_url)
    bt = study.best_trial
    params = bt.params

    # Robust seed selection
    seed = 42
    rs = bt.user_attrs.get("rand_seed")
    rep_scores = bt.user_attrs.get("rep_scores")
    if rep_scores is not None and rs is not None:
        rep_scores = np.asarray(rep_scores)
        rs = np.asarray(rs)
        idx = int(np.argmin(rep_scores))
        seed = int(rs[idx])
    elif rs is not None:
        seed = int(rs[0]) if isinstance(rs, (list, tuple, np.ndarray)) else int(rs)
    logging.info("Best value=%.6f, chosen seed=%s, trial_id=%s", bt.value, seed, bt.number)
    return params, seed, bt.value, bt.number


def load_model_config(model_config_name: str) -> dict:
    """Load base YAML config from calib/model_configs/<name>."""
    cfg_path = Path("calib/model_configs") / model_config_name
    with open(cfg_path) as f:
        base = yaml.safe_load(f)
    return base


def prepare_pars(
    base_cfg: dict,
    best_params: dict,
    seed: int,
    study_name: str,
    results_path: str | None,
) -> tuple[dict, Path]:
    """Merge best params into base config; set seed & results path."""
    outdir = Path(results_path or f"results/{study_name}/best_trial")
    outdir.mkdir(parents=True, exist_ok=True)
    pars = sc.mergedicts(base_cfg, best_params)
    pars["seed"] = seed
    pars["results_path"] = str(outdir)
    return pars, outdir


def run_once(pars: dict, verbose: int = 0):
    """Run a single simulation."""
    logging.info("Running simulation…")
    sim = lp.run_sim(pars, verbose=verbose)
    logging.info("Simulation complete.")
    return sim


def make_matplotlib_animation(sim, model_cfg: dict, outdir: Path) -> Path:
    """
    Create the monthly bars + monthly line + moving cursor animation (MP4),
    using your working lp.animate_maps_plus_series().
    """
    print("Loading actual data for animation…")
    logging.info("Preparing actuals for animation…")
    summary_cfg = model_cfg.get("summary_config", {}) or {}
    actual_df = prep_actual_data_for_calibration(
        regions=model_cfg.get("regions", ("ZAMFARA",)),
        admin_level=model_cfg.get("admin_level", "adm0"),
        start_year=model_cfg["start_year"],
        n_days=model_cfg["n_days"],
        summary_time_periods=summary_cfg.get("time_periods"),
        summary_region_groupings=summary_cfg.get("region_groupings"),
        summary_grouping_level=summary_cfg.get("grouping_level", "adm0"),
        pop_scale=model_cfg.get("pop_scale", 1.0),
        results_path=outdir,
        save_csv=False,
    )
    print("✅ Actual data loaded successfully!")

    print("Aggregating actual data by month…")
    # Monthly aggregation (fallback to 'date' if 'month_start' missing)
    if "month_start" in actual_df.columns:
        group_key = "month_start"
    elif "date" in actual_df.columns:
        actual_df["_month_start"] = pd.to_datetime(actual_df["date"]).values.astype("datetime64[M]").astype("datetime64[ns]")
        group_key = "_month_start"
    else:
        raise ValueError("Cannot aggregate monthly actuals: neither 'month_start' nor 'date' in actual_df.")

    actual_monthly = actual_df.groupby(group_key)["P"].sum().to_numpy()
    print("✅ Actual data aggregated successfully!")

    print("Rendering animation…")
    out_mp4 = outdir / "animated.mp4"
    logging.info("Rendering animation → %s", out_mp4)
    lp.animate_maps_plus_series(
        incidence_TNK=sim.results.I_by_strain,
        gdf=sim.pars.shp,
        actual_monthly=actual_monthly,
        pred_T=np.sum(sim.results.new_potentially_paralyzed, axis=1) / 2000,
        time_labels=sim.datevec,
        strain_names=sim.pars["strain_ids"].keys(),
        fps=60,
        dpi=150,
        cmap="viridis",
        log=False,
        fig_width_per_panel=4.0,
        fig_height=6.0,
        out_path=str(out_mp4),
    )
    print("✅ Animation saved successfully!")
    logging.info("Saved %s", out_mp4)
    return out_mp4


# ---------------------------
# CLI
# ---------------------------


def parse_args():
    ap = argparse.ArgumentParser(description="Run best-trial simulation and (optionally) save MP4 animation.")
    ap.add_argument("--study-name", required=True, help="Optuna study name")
    ap.add_argument("--storage-url", required=True, help="Optuna storage URL (sqlite or mysql+pymysql)")
    ap.add_argument("--model-config", required=True, help="YAML under calib/model_configs/")
    ap.add_argument("--results-path", default=None, help="Directory for outputs (default uses study name)")
    ap.add_argument("--save-plots", action="store_true", help="Create Matplotlib MP4")
    ap.add_argument("--verbose", type=int, default=1, help="Verbosity for lp.run_sim")
    ap.add_argument("--log-level", default="INFO", help="Logging level (DEBUG, INFO, …)")
    return ap.parse_args()


def main():
    args = parse_args()
    logging.basicConfig(level=args.log_level.upper(), format="%(asctime)s %(levelname)s %(message)s")

    # 1) Best trial
    best_params, seed, best_val, trial_id = load_best(args.study_name, args.storage_url)

    # 2) Config & pars
    base_cfg = load_model_config(args.model_config)
    pars, outdir = prepare_pars(base_cfg, best_params, seed, args.study_name, args.results_path)

    # 3) Run one sim
    sim = run_once(pars, verbose=args.verbose)

    # 4) Optional MP4
    if args.save_plots:
        try:
            make_matplotlib_animation(sim, base_cfg, outdir)
        except Exception as e:
            logging.exception("Matplotlib animation failed: %s", e)

    logging.info("Done. Results → %s", outdir)


if __name__ == "__main__":
    main()
