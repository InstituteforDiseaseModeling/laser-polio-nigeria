#!/usr/bin/env python3
import optuna
import re
import numpy as np
import matplotlib.pyplot as plt
import argparse

def extract_spd_from_study_name(name: str) -> int:
    """Extract XXX from study name like 'synth_onenode_spdeqXXX'"""
    match = re.search(r"spdeq(\d+)", name)
    value = int(match.group(1)) if match else None
    if value > 360:
        value = int(value/10)
    return value

def extract_sa_from_study_name(name: str) -> int:
    """Extract XXX from study name like 'synth_onenode_spdeqXXX'"""
    match = re.search(r"saeq([\d.]+)", name)
    value = float(match.group(1)) if match else None
    return value

def extract_r0_from_study_name(name: str) -> int:
    """Extract XXX from study name like 'synth_onenode_spdeqXXX'"""
    match = re.search(r"r0eq([\d.]+)_spd110", name)
    value = float(match.group(1)) if match else None
    print( f"Found r0 value {value} in db" )

    return value

def main():
    parser = argparse.ArgumentParser(description="Compare Optuna best-fit params to ground truth (from study names).")
    parser.add_argument("--storage", default="sqlite:///example.db", help="Optuna storage path")
    parser.add_argument("--param-name", default="seasonal_peak_doy", help="Name of the parameter being calibrated")
    parser.add_argument("--prefix", default="synth_onenode_spdeq", help="Prefix for studies to match")
    args = parser.parse_args()

    # Load all study summaries
    print(f"[INFO] Loading studies from: {args.storage}")
    study_summaries = optuna.get_all_study_summaries(storage=args.storage)

    true_params = []
    errors = []

    for summary in study_summaries:
        study_name = summary.study_name

        if not study_name.startswith(args.prefix):
            continue

        true_value = extract_sa_from_study_name(study_name)
        if true_value is None:
            continue

        try:
            study = optuna.load_study(study_name=study_name, storage=args.storage)
            best_trial = study.best_trial
            best_param = best_trial.params.get(args.param_name)

            if best_param is None:
                print(f"[WARN] {study_name} has no param '{args.param_name}'")
                continue

            error = abs(best_param - true_value)
            true_params.append(true_value)
            errors.append(error)
            print(f"{study_name}: true={true_value}, best={best_param:.2f}, error={error:.2f}")

        except Exception as e:
            print(f"[ERROR] Failed to load {study_name}: {e}")
            continue

    # Plot
    if true_params:
        true_params = np.array(true_params)
        errors = np.array(errors)

        plt.figure(figsize=(10, 5))
        plt.scatter(true_params, errors, color="steelblue", alpha=0.7)
        #plt.plot(true_params, errors, color="gray", alpha=0.4, linewidth=1)
        plt.xlabel(f"True {args.param_name}")
        plt.ylabel("Calibration error |best_fit - true|")
        plt.title(f"Calibration Accuracy vs Ground Truth ({args.param_name})")
        plt.grid(True, linestyle="--", alpha=0.4)
        plt.tight_layout()
        plt.savefig("param_error_vs_truth.png", dpi=150)
        plt.show()
    else:
        print("[INFO] No matching studies found or no successful best-fit extractions.")

if __name__ == "__main__":
    main()
