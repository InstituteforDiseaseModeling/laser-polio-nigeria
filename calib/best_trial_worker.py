#!/usr/bin/env python3
"""
Worker script for running best trial analysis on AKS cluster.
This script is designed to run inside the cluster without port forwarding.
"""

import argparse
import os
import sys
import traceback
from pathlib import Path

import numpy as np
import optuna
import sciris as sc
import yaml

try:
    import psutil
except ImportError:
    psutil = None

import laser_polio as lp
from laser_polio.utils import prep_actual_data_for_calibration


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Run best trial analysis on AKS cluster")
    parser.add_argument("--study-name", required=True, help="Name of the Optuna study")
    parser.add_argument("--storage-url", required=True, help="Storage URL for Optuna study")
    parser.add_argument("--model-config", required=True, help="Model configuration YAML file")
    parser.add_argument("--results-path", help="Override results path")
    parser.add_argument("--save-plots", action="store_true", default=False, help="Save plots")
    parser.add_argument("--animate-plots", action="store_true", default=False, help="Create animated plots")
    parser.add_argument("--plot-pars", action="store_true", default=False, help="Plot parameters")
    parser.add_argument("--verbose", "-v", type=int, default=0, help="Verbose output")
    return parser.parse_args()


def load_best_trial_data(study_name: str, storage_url: str):
    """Load the best trial data from Optuna study."""
    print(f"📊 Loading study '{study_name}'...")

    # Fix storage URL for cluster-internal MySQL access
    # Replace localhost:3307 with cluster service mysql:3306
    if "localhost:3307" in storage_url:
        cluster_storage_url = storage_url.replace("localhost:3307", "mysql:3306")
        print("🔧 Using cluster-internal MySQL: mysql:3306")
        storage_url = cluster_storage_url

    # Alternatively, build from environment variables if they exist
    mysql_user = os.environ.get("MYSQL_USER")
    mysql_password = os.environ.get("MYSQL_PASSWORD")
    mysql_db = os.environ.get("MYSQL_DB")

    if mysql_user and mysql_password and mysql_db and "localhost" in storage_url:
        cluster_storage_url = f"mysql+pymysql://{mysql_user}:{mysql_password}@mysql:3306/{mysql_db}"
        print("🔧 Built cluster storage URL from environment variables")
        storage_url = cluster_storage_url

    print(f"🔗 Storage URL: {storage_url}")
    try:
        study = optuna.load_study(study_name=study_name, storage=storage_url)
        best_trial = study.best_trial
        best_params = best_trial.params

        # Extract random seed from best trial
        if "rep_scores" in best_trial.user_attrs and "rand_seed" in best_trial.user_attrs:
            rep_scores = best_trial.user_attrs["rep_scores"]
            best_idx = np.where(rep_scores == np.min(rep_scores))
            rand_seeds = best_trial.user_attrs["rand_seed"]
            rand_seed = rand_seeds[best_idx[0][0]]
        else:
            # Fallback if no rep_scores available
            rand_seed = best_trial.user_attrs.get("rand_seed", 42)
            if isinstance(rand_seed, list):
                rand_seed = rand_seed[0]

        print(f"✅ Best trial loaded: value={best_trial.value}, seed={rand_seed}")
        return best_params, rand_seed, best_trial
    except Exception as e:
        print(f"❌ Error loading study: {e}")
        raise


def setup_model_config(
    model_config_path: str,
    best_params: dict,
    rand_seed: int,
    results_path: str | None = None,
    save_plots: bool = False,
    animate_plots: bool = False,
    plot_pars: bool = False,
):
    """Setup the model configuration with best trial parameters."""
    print(f"🔧 Loading model config from {model_config_path}...")

    # Load base model config
    config_full_path = Path("calib/model_configs") / model_config_path
    with open(config_full_path) as f:
        model_config = yaml.safe_load(f)

    # Set results path
    if results_path:
        model_config["results_path"] = results_path
    else:
        # Default results path with study name
        study_name = os.environ.get("STUDY_NAME", "unknown_study")
        model_config["results_path"] = f"results/{study_name}/best_trial"

    # Set plotting options
    model_config["save_plots"] = save_plots
    model_config["animate_plots"] = animate_plots
    model_config["plot_pars"] = plot_pars

    # Apply best trial parameters and seed
    pars = sc.mergedicts(model_config, best_params)
    pars["seed"] = rand_seed

    print(f"✅ Model config prepared with {len(best_params)} optimized parameters")
    return pars, model_config


def run_simulation(pars: dict, verbose: int = 0):
    """Run the simulation with best trial parameters."""
    print("🚀 Running simulation with best trial parameters...")
    try:
        print("🔄 About to call lp.run_sim...")
        sim = lp.run_sim(pars, verbose=verbose)
        print("✅ lp.run_sim completed successfully!")
        print("📊 Simulation results summary:")
        print(f"   - Results keys: {list(sim.results.keys()) if hasattr(sim.results, 'keys') else 'N/A'}")
        return sim
    except Exception as e:
        print(f"❌ Error running simulation: {e}")
        print(f"📋 Traceback: {traceback.format_exc()}")
        raise


def create_visualizations(sim, model_config: dict):
    """Create and save visualizations."""
    print("📈 Creating visualizations...")

    try:
        print("🔄 Loading actual data for comparison...")
        # Load actual data for comparison
        actual_data = prep_actual_data_for_calibration(
            regions=model_config["regions"],
            admin_level=None,
            start_year=model_config["start_year"],
            n_days=model_config["n_days"],
            pop_scale=model_config["pop_scale"],
            results_path=model_config["results_path"],
            save_csv=False,
        )
        print("✅ Actual data loaded successfully!")

        print("🔄 Processing actual data by month...")
        # Sum actual data by month
        actual_data_monthly = np.asarray(actual_data.groupby("month_start").sum("P").reset_index()["P"])
        print(f"✅ Processed {len(actual_data_monthly)} monthly data points")

        # Create animated maps and series plots
        output_path = f"{model_config['results_path']}/animated.mp4"
        print(f"🎬 Creating animated visualization at {output_path}")

        # Check memory usage before starting
        if psutil:
            print(f"💾 Memory usage before animation: {psutil.virtual_memory().percent}% used")
        else:
            print("💾 psutil not available for memory monitoring")

        print("🔄 About to call lp.animate_maps_plus_series...")
        print("📊 Animation parameters:")
        print(f"   - I_by_strain shape: {sim.results.I_by_strain.shape}")
        print(f"   - GDF shape: {len(sim.pars.shp)}")
        print(f"   - Actual monthly length: {len(actual_data_monthly)}")
        print(f"   - Time labels length: {len(sim.datevec)}")
        print(f"   - Strain names: {list(sim.pars['strain_ids'].keys())}")

        try:
            lp.animate_maps_plus_series(
                incidence_TNK=sim.results.I_by_strain,  # shape (T, N, K)
                gdf=sim.pars.shp,  # GeoDataFrame
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
                out_path=output_path,
            )
            print("✅ lp.animate_maps_plus_series completed successfully!")
            print(f"🎬 Animated visualization saved to: {output_path}")
        except Exception as animation_error:
            print(f"❌ Error in animate_maps_plus_series: {animation_error}")
            print(f"📋 Animation traceback: {traceback.format_exc()}")
            raise animation_error

        print(f"✅ Visualizations saved to {model_config['results_path']}")

    except Exception as e:
        print(f"⚠️ Warning: Failed to create visualizations: {e}")
        print(f"📋 Visualization traceback: {traceback.format_exc()}")
        # Don't fail the job if visualization fails


def main():
    """Main execution function."""
    args = parse_args()

    print("🎯 Starting best trial analysis worker...")
    print(f"Study: {args.study_name}")
    print(f"Model config: {args.model_config}")
    print(f"Pod: {os.environ.get('POD_NAME', 'unknown')}")
    print(f"Job: {os.environ.get('JOB_NAME', 'unknown')}")

    try:
        # Load best trial data
        print("🔄 About to load best trial data...")
        best_params, rand_seed, best_trial = load_best_trial_data(args.study_name, args.storage_url)
        print("✅ Best trial data loaded successfully!")

        # Setup model configuration
        print("🔄 About to setup model configuration...")
        pars, model_config = setup_model_config(
            args.model_config,
            best_params,
            rand_seed,
            args.results_path,
            args.save_plots,
            args.animate_plots,
            args.plot_pars,
        )
        print("✅ Model configuration setup completed!")
        print(f"🔍 Model configuration: {pars}")

        # Run simulation
        print("🔄 About to run simulation...")
        sim = run_simulation(pars, args.verbose)
        print("✅ Simulation completed successfully!")

        # Create visualizations if requested
        print(f"🎬 Creating visualizations: {args.save_plots}")
        if True:  # args.save_plots:
            print("🔄 About to create visualizations...")
            create_visualizations(sim, model_config)
            print("✅ Visualizations completed successfully!")
        else:
            print("⏭️  Skipping visualizations (save_plots=False)")

        print("🎉 Best trial analysis completed successfully!")

        # Print summary
        print("\n📋 Summary:")
        print(f"   Best trial value: {best_trial.value}")
        print(f"   Random seed used: {rand_seed}")
        print(f"   Results saved to: {model_config['results_path']}")

    except Exception as e:
        print(f"💥 Fatal error: {e}")
        print(f"📋 Fatal error traceback: {traceback.format_exc()}")
        sys.exit(1)


if __name__ == "__main__":
    main()
