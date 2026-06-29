"""
Monitor an AKS calibration job: pod status, trial progress, best parameters, and errors.
Reads JOB_NAME, STUDY_NAME, and COMPLETIONS from run_calib_aks.py automatically.

Run with the VS Code play button or from the repo root:

    python scripts/calibration/check_calib_aks.py
"""

import ast
import base64
import json
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

CYAN  = "\033[96m"
RESET = "\033[0m"

# ── Configuration ─────────────────────────────────────────────────────────────

N_TOP_TRIALS = 5     # number of best trials to display
LOCAL_PORT   = 3308  # local port for kubectl port-forward

# ── Read job config from run_calib_aks.py (single source of truth) ────────────

_aks_script = Path(__file__).parent / "run_calib_aks.py"
_tree = ast.parse(_aks_script.read_text())
_cfg = {}
for _node in ast.walk(_tree):
    if isinstance(_node, ast.Assign):
        for _t in _node.targets:
            if isinstance(_t, ast.Name) and _t.id in ("JOB_NAME", "STUDY_NAME", "COMPLETIONS"):
                _cfg[_t.id] = ast.literal_eval(_node.value)

JOB_NAME    = _cfg["JOB_NAME"]
STUDY_NAME  = _cfg["STUDY_NAME"]
COMPLETIONS = _cfg["COMPLETIONS"]

# ── Helpers ───────────────────────────────────────────────────────────────────

def kubectl(*args):
    return subprocess.run(["kubectl", *args], capture_output=True, text=True)

def section(title):
    print(f"\n{CYAN}{'─' * 4} {title} {'─' * max(0, 60 - len(title))}{RESET}")

# ── Job + pod status ──────────────────────────────────────────────────────────

print(f"Job:   {JOB_NAME}")
print(f"Study: {STUDY_NAME}")

job_result = kubectl("get", "job", JOB_NAME, "-o", "json")
if job_result.returncode != 0:
    print(f"\nERROR: Job '{JOB_NAME}' not found on cluster.")
    sys.exit(1)

job_status  = json.loads(job_result.stdout)["status"]
n_succeeded = job_status.get("succeeded", 0)
n_active    = job_status.get("active", 0)
n_failed_k8 = job_status.get("failed", 0)   # cumulative failed pod attempts

pods = json.loads(kubectl("get", "pods", "-l", f"job-name={JOB_NAME}", "-o", "json").stdout)["items"]

status_counts = Counter()
error_pods = []
for pod in pods:
    name    = pod["metadata"]["name"]
    cs_list = pod["status"].get("containerStatuses", [])
    if cs_list:
        state = cs_list[0].get("state", {})
        if "waiting" in state:
            reason = state["waiting"].get("reason", "Waiting")
            status_counts[reason] += 1
            if reason in ("CrashLoopBackOff", "Error"):
                error_pods.append(name)
        elif "running" in state:
            status_counts["Running"] += 1
        elif "terminated" in state:
            if state["terminated"].get("exitCode", 0) == 0:
                status_counts["Completed"] += 1
            else:
                status_counts["Failed"] += 1
                error_pods.append(name)
    else:
        status_counts[pod["status"].get("phase", "Unknown")] += 1

n_initializing = sum(v for k, v in status_counts.items()
                     if k in ("Pending", "ContainerCreating", "PodInitializing"))
n_errors       = sum(v for k, v in status_counts.items()
                     if k in ("Failed", "CrashLoopBackOff", "Error"))
n_yet_to_run   = max(0, COMPLETIONS - n_succeeded - n_active)

# ETA: elapsed time / completions so far → rate → remaining time
start_str = job_status.get("startTime")
eta_str = "n/a"
rate_str = "n/a"
if start_str and n_succeeded > 0:
    start_dt  = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
    elapsed_s = (datetime.now(timezone.utc) - start_dt).total_seconds()
    rate      = n_succeeded / elapsed_s                       # completions/sec
    remaining = max(0, COMPLETIONS - n_succeeded)
    eta_dt    = datetime.now(timezone.utc) + timedelta(seconds=remaining / rate)
    eta_str   = eta_dt.astimezone().strftime("%Y-%m-%d %H:%M %Z")
    rate_str  = f"{rate * 3600:.1f} completions/hr"

section("Pod Status")
print(f"  Completed:    {n_succeeded:>5}")
print(f"  Running:      {n_active:>5}")
if n_initializing:
    print(f"  Initializing: {n_initializing:>5}")
print(f"  Yet to run:   {n_yet_to_run:>5}")
if n_errors:
    print(f"  Errors:       {n_errors:>5}  ({n_failed_k8} cumulative failed attempts)")
print(f"  ── target ──  {COMPLETIONS:>5}")
print(f"  Rate:         {rate_str}")
print(f"  ETA:          {eta_str}")

# ── Optuna DB via port-forward ────────────────────────────────────────────────

secret_result = kubectl("get", "secret", "mysql-secrets", "-o", "json")
if secret_result.returncode != 0:
    print("\nWARNING: Could not read mysql-secrets — skipping DB query.")
    sys.exit(0)

secret_data = json.loads(secret_result.stdout)["data"]
db_user = base64.b64decode(secret_data["MYSQL_USER"]).decode()
db_pass = base64.b64decode(secret_data["MYSQL_PASSWORD"]).decode()
db_name = base64.b64decode(secret_data["MYSQL_DB"]).decode()

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
        study = optuna.load_study(study_name=STUDY_NAME, storage=storage)
    except Exception as e:
        print(f"\nWARNING: Could not load study '{STUDY_NAME}': {e}")
        sys.exit(0)

    trials    = study.trials
    completed = [t for t in trials if t.state.name == "COMPLETE"]
    failed    = [t for t in trials if t.state.name == "FAIL"]
    running   = [t for t in trials if t.state.name == "RUNNING"]

    section("Trial Progress")
    print(f"  Completed: {len(completed):>5}")
    print(f"  Running:   {len(running):>5}")
    print(f"  Failed:    {len(failed):>5}")

    if completed:
        top        = sorted(completed, key=lambda t: t.value if t.value is not None else float("inf"))[:N_TOP_TRIALS]
        param_names = list(top[0].params.keys())
        col_w       = max(14, max(len(p) for p in param_names) + 2)

        section(f"Best {len(top)} Trials  (of {len(completed)} completed)")
        header = f"  {'Rank':>4}  {'Trial':>6}  {'Value':>12}  " + \
                 "  ".join(f"{p:>{col_w}}" for p in param_names)
        print(header)
        print("  " + "─" * (len(header) - 2))
        for rank, t in enumerate(top, 1):
            params = "  ".join(f"{t.params[p]:>{col_w}.4f}" for p in param_names)
            print(f"  {rank:>4}  {t.number:>6}  {t.value:>12.4f}  {params}")

    if failed:
        section(f"Trial Errors  ({len(failed)} failed trials)")
        msgs = [t.system_attrs.get("fail_reason", "") for t in failed
                if t.system_attrs.get("fail_reason")]
        if msgs:
            for i, msg in enumerate(dict.fromkeys(msgs), 1):
                print(f"  {i}. {msg[:120]}")
        else:
            print("  (No error details stored in DB — see pod logs below)")

finally:
    pf.terminate()

# ── Pod-level error logs ──────────────────────────────────────────────────────

if error_pods:
    section(f"Pod Error Logs  ({len(error_pods)} pod(s) with errors)")
    shown = set()
    for pod_name in error_pods[:5]:
        lines = kubectl("logs", pod_name, "--tail=30").stdout.strip().splitlines()
        error_lines = [l for l in lines if any(
            tok in l for tok in ("ERROR", "Error", "Traceback", "Exception", "failed", "WARN")
        )]
        key = "\n".join(error_lines[-5:])
        if key in shown:
            continue
        shown.add(key)
        print(f"\n  [{pod_name}]")
        for line in (error_lines[-10:] if error_lines else lines[-5:]):
            print(f"    {line}")

print()
