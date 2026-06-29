"""
Download and plot calibration results from an AKS study.
Reads the study directly from MySQL on the cluster via kubectl port-forward —
no files need to be downloaded from the PVC.

Run with the VS Code play button or from the repo root:

    python scripts/calibration/report_calib_aks.py

Output is written to results/<STUDY_NAME>/ (same layout as a local calibration run).
"""

import ast
import base64
import json
import socket
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

from laser_polio_nigeria import _load_dotenv
_load_dotenv(REPO_ROOT / ".env")  # sets LASER_POLIO_DATA for shapefile/data access

# ── Read study config from run_calib_aks.py (single source of truth) ──────────

_aks_script = Path(__file__).parent / "run_calib_aks.py"
_tree = ast.parse(_aks_script.read_text())
_cfg = {}
for _node in ast.walk(_tree):
    if isinstance(_node, ast.Assign):
        for _t in _node.targets:
            if isinstance(_t, ast.Name) and _t.id in ("STUDY_NAME", "MODEL_CONFIG"):
                _cfg[_t.id] = ast.literal_eval(_node.value)

STUDY_NAME   = _cfg["STUDY_NAME"]
MODEL_CONFIG = _cfg["MODEL_CONFIG"]

LOCAL_PORT = 3308

# ── Port-forward MySQL ─────────────────────────────────────────────────────────

def _get_db_creds():
    result = subprocess.run(
        ["kubectl", "get", "secret", "mysql-secrets", "-o", "json"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print("ERROR: Could not read mysql-secrets from cluster.")
        sys.exit(1)
    d = json.loads(result.stdout)["data"]
    return (
        base64.b64decode(d["MYSQL_USER"]).decode(),
        base64.b64decode(d["MYSQL_PASSWORD"]).decode(),
        base64.b64decode(d["MYSQL_DB"]).decode(),
    )

def _wait_for_port(port, timeout=15):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1):
                return
        except OSError:
            time.sleep(0.2)
    raise TimeoutError(f"Port-forward on 127.0.0.1:{port} didn't open in {timeout}s")

print(f"Study:  {STUDY_NAME}")
print(f"Model:  {MODEL_CONFIG}")
print()

db_user, db_pass, db_name = _get_db_creds()
storage = f"mysql+pymysql://{db_user}:{db_pass}@127.0.0.1:{LOCAL_PORT}/{db_name}"

print("==> Port-forwarding MySQL...")
pf = subprocess.Popen(
    ["kubectl", "port-forward", "svc/mysql", f"{LOCAL_PORT}:3306"],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
)
try:
    _wait_for_port(LOCAL_PORT)
except TimeoutError as e:
    print(f"ERROR: {e}")
    pf.terminate()
    sys.exit(1)

# ── Load study ─────────────────────────────────────────────────────────────────

try:
    import optuna
    from laser_polio_calibration.core.report import (
        plot_likelihood_contribution_best,
        plot_likelihood_contribution_by_param,
        plot_likelihood_slices,
        plot_likelihoods_vs_params,
        plot_mutual_information,
        plot_optimization_history,
        plot_quadratic_fit,
        plot_runtimes,
        plot_targets,
        save_study_results,
    )

    optuna.logging.set_verbosity(optuna.logging.WARNING)

    print("==> Loading Optuna study...")
    try:
        study = optuna.load_study(study_name=STUDY_NAME, storage=storage)
    except Exception as e:
        print(f"ERROR: Could not load study '{STUDY_NAME}': {e}")
        sys.exit(1)

    completed = [t for t in study.trials if t.state.name == "COMPLETE"]
    study.storage_url = storage  # type: ignore[attr-defined]  # save_study_results reads this
    print(f"     {len(completed)} completed trials, best value: {study.best_value:.4f}")
    print(f"     best params: {study.best_trial.params}")
    print()

    results_path = REPO_ROOT / "results" / STUDY_NAME
    results_path.mkdir(parents=True, exist_ok=True)
    print(f"==> Writing results to {results_path}/")

    print("     Saving study CSV...")
    save_study_results(study, output_dir=results_path)

    print("     Optimization history...")
    plot_optimization_history(study, output_dir=results_path)

    print("     Runtimes...")
    plot_runtimes(study, output_dir=results_path)

    print("     Actual vs predicted (top 10 trials)...")
    plot_targets(study, n=10, output_dir=results_path)

    print("     Likelihood contribution — best trial...")
    plot_likelihood_contribution_best(study, output_dir=results_path, use_log=True)

    print("     Likelihood contribution by parameter...")
    plot_likelihood_contribution_by_param(study, output_dir=results_path)

    print("     Likelihood slices...")
    plot_likelihood_slices(study, output_dir=results_path)

    print("     Likelihoods vs params...")
    plot_likelihoods_vs_params(study, output_dir=results_path, use_log=True)

    print("     Quadratic fit quality...")
    plot_quadratic_fit(study, output_dir=results_path)

    print("     Mutual information...")
    plot_mutual_information(study, output_dir=results_path)

    print(f"\n✓ Done. Results: {results_path}")

finally:
    pf.terminate()
