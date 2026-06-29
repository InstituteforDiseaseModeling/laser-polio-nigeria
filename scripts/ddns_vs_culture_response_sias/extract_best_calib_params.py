"""
Extract best calibration trial parameters and update the snapshot config.

Connects to the active Optuna MySQL study (via kubectl port-forward),
reads the best trial, and writes its parameters into:
  scripts/ddns_vs_culture_response_sias/configs/snapshot_nigeria.yaml

Run this after the calibration study has enough trials:
    python scripts/ddns_vs_culture_response_sias/extract_best_calib_params.py

Writes transmission parameters and the trial's rand_seed into snapshot_nigeria.yaml,
then review the config and run:
    python scripts/ddns_vs_culture_response_sias/submit_snapshot_jobs.py
"""

import ast
import base64
import json
import subprocess
import sys
import time
from pathlib import Path

import yaml

SCRIPT_DIR = Path(__file__).parent
REPO_ROOT = SCRIPT_DIR.parent.parent
SNAPSHOT_CONFIG = SCRIPT_DIR / "configs" / "snapshot_nigeria.yaml"
CALIB_SCRIPT = REPO_ROOT / "scripts" / "calibration" / "run_calib_aks.py"
LOCAL_PORT = 3308

# Parameters to extract from the best trial and write to the snapshot config.
# Maps Optuna param name → YAML key name (they match in this calibration).
PARAM_MAP = {
    "r0": "r0",
    "radiation_k_log10": "radiation_k_log10",
    "pim_re_center": "pim_re_center",
    "pim_re_scale": "pim_re_scale",
}


def read_study_name() -> str:
    tree = ast.parse(CALIB_SCRIPT.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == "STUDY_NAME":
                    return ast.literal_eval(node.value)
    raise ValueError(f"STUDY_NAME not found in {CALIB_SCRIPT}")


def get_db_credentials() -> tuple[str, str, str]:
    result = subprocess.run(
        ["kubectl", "get", "secret", "mysql-secrets", "-o", "json"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Could not read mysql-secrets: {result.stderr}")
    data = json.loads(result.stdout)["data"]
    return (
        base64.b64decode(data["MYSQL_USER"]).decode(),
        base64.b64decode(data["MYSQL_PASSWORD"]).decode(),
        base64.b64decode(data["MYSQL_DB"]).decode(),
    )


def main():
    study_name = read_study_name()
    print(f"Calibration study: {study_name}")

    db_user, db_pass, db_name = get_db_credentials()

    pf = subprocess.Popen(
        ["kubectl", "port-forward", "svc/mysql", f"{LOCAL_PORT}:3306"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    time.sleep(2)

    try:
        import optuna
        optuna.logging.set_verbosity(optuna.logging.WARNING)
        storage = f"mysql+pymysql://{db_user}:{db_pass}@127.0.0.1:{LOCAL_PORT}/{db_name}"

        try:
            study = optuna.load_study(study_name=study_name, storage=storage)
        except Exception as e:
            print(f"ERROR: Could not load study '{study_name}': {e}")
            sys.exit(1)

        completed = [t for t in study.trials if t.state.name == "COMPLETE"]
        if not completed:
            print("ERROR: No completed trials found.")
            sys.exit(1)

        best = min(completed, key=lambda t: t.value if t.value is not None else float("inf"))
        rand_seed_attr = best.user_attrs.get("rand_seed")
        rand_seed = rand_seed_attr[0] if isinstance(rand_seed_attr, list) else rand_seed_attr
        print(f"Best trial: #{best.number}  value={best.value:.4f}  seed={rand_seed}")
        print("Parameters:")
        for k, v in best.params.items():
            print(f"  {k}: {v}")

    finally:
        pf.terminate()

    # Read and update snapshot config
    with open(SNAPSHOT_CONFIG) as f:
        config = yaml.safe_load(f)

    for optuna_key, yaml_key in PARAM_MAP.items():
        if optuna_key in best.params:
            old = config.get(yaml_key, "NOT SET")
            config[yaml_key] = best.params[optuna_key]
            print(f"  {yaml_key}: {old!r} → {best.params[optuna_key]!r}")
        else:
            print(f"  WARNING: {optuna_key} not found in best trial params")

    if rand_seed is not None:
        old_seed = config.get("seed", "NOT SET")
        config["seed"] = int(rand_seed)
        print(f"  seed: {old_seed!r} → {int(rand_seed)!r}")
    else:
        print("  WARNING: rand_seed not found in best trial user_attrs — seed not updated")

    with open(SNAPSHOT_CONFIG, "w") as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)

    print(f"\nUpdated: {SNAPSHOT_CONFIG}")
    print("\nNEXT STEPS:")
    print("1. Review the updated snapshot config (params and seed)")
    print("2. Run: python scripts/ddns_vs_culture_response_sias/submit_snapshot_jobs.py")


if __name__ == "__main__":
    main()
