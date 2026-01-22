import subprocess
import time
from pathlib import Path

import cloud_calib_config as cfg
import numpy as np
import optuna
import sciris as sc
import yaml

import laser_polio as lp
from laser_polio.utils import prep_actual_data_for_calibration


def port_forward():
    print("🔌 Setting up port forwarding to MySQL...")
    pf = subprocess.Popen(["kubectl", "port-forward", "mysql-0", "3307:3306"])
    time.sleep(3)  # wait for port-forward to take effect
    return pf


def main():
    pf_process = port_forward()
    try:
        print(f"📊 Loading study '{cfg.study_name}'...")
        # Load the study
        study = optuna.load_study(study_name=cfg.study_name, storage=cfg.storage_url)
        best_params = study.best_trial.params

        with open(Path("calib/model_configs/") / cfg.model_config) as f:
            model_config = yaml.safe_load(f)
        model_config["results_path"] = "results/" + cfg.study_name + "/best_trial"
        model_config["save_plots"] = True
        model_config["animate_plots"] = False
        model_config["plot_pars"] = True
        # pars = PropertySet(model_config)
        pars = sc.mergedicts(model_config, best_params)  # apply best trial overrides

        # Extract rand_seed from the best trial (which can have reps)
        rep_scores = study.best_trial.user_attrs["rep_scores"]
        best_idx = np.where(rep_scores == np.min(rep_scores))
        rand_seeds = study.best_trial.user_attrs["rand_seed"]
        rand_seed = rand_seeds[best_idx[0][0]]
        pars["seed"] = rand_seed

        # Run sim & save plots
        print("💫Running sim with best trial parameters...")
        sim = lp.run_sim(pars, verbose=1)

        # Load actual data for plotting
        actual_data = prep_actual_data_for_calibration(
            regions=model_config["regions"],
            admin_level=None,
            start_year=model_config["start_year"],
            n_days=model_config["n_days"],
            pop_scale=model_config["pop_scale"],
            results_path=model_config["results_path"],
            save_csv=False,
        )
        # Sum actual data by month
        actual_data_monthly = np.asarray(actual_data.groupby("month_start").sum("P").reset_index()["P"])

        # Animate maps of infections & series for predicted/actual cases
        lp.animate_maps_plus_series(
            incidence_TNK=sim.results.I_by_strain,  # shape (T, N, K) : infections by node & strain
            gdf=sim.pars.shp,  # GeoDataFrame length N, already ordered to match N
            actual_monthly=actual_data_monthly,
            pred_T=np.sum(sim.results.new_potentially_paralyzed, axis=1) / 2000,
            time_labels=sim.datevec,
            strain_names=sim.pars["strain_ids"].keys(),
            fps=100,
            dpi=160,
            cmap="viridis",
            log=False,
            fig_width_per_panel=4.0,
            fig_height=6.0,
            out_path=f"{model_config['results_path']}/animated.mp4",
        )

    finally:
        print("🧹 Cleaning up port forwarding...")
        pf_process.terminate()
        print("🎉Done!")


if __name__ == "__main__":
    main()
