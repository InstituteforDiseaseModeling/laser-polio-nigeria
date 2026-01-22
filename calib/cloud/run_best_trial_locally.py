#!/usr/bin/env python3
"""
Run the best trial locally while reading the Optuna study from AKS via kubectl port-forward.

- Port-forwards MySQL service to 127.0.0.1:3307
- Calls best_trial_pipeline.py with that storage URL
- Cleans up port-forward on exit

Requirements:
  - kubectl configured to the AKS cluster/namespace with MySQL service reachable
  - best_trial_pipeline.py available in the current repo (same Python env)
  - cloud_calib_config.py providing: study_name, model_config, (optional) storage_url
"""

import os
import socket
import subprocess
import sys
import time
from urllib.parse import urlparse
from urllib.parse import urlunparse

import cloud_calib_config as cfg

# --- Config (override here or in cloud_calib_config) ---
NAMESPACE = getattr(cfg, "namespace", os.getenv("K8S_NAMESPACE", "default"))
PF_TARGET = getattr(cfg, "mysql_portforward_target", "svc/mysql")  # e.g. "svc/mysql" or "mysql-0"
LOCAL_PORT = int(getattr(cfg, "mysql_local_port", 3307))
REMOTE_PORT = int(getattr(cfg, "mysql_remote_port", 3306))
RESULTS_PATH = getattr(cfg, "results_path", f"results/{cfg.study_name}/best_trial")
LOG_LEVEL = getattr(cfg, "log_level", "INFO")


def wait_for_port(host: str, port: int, timeout: float = 10.0) -> None:
    """Block until TCP host:port is connectable or timeout."""
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            with socket.create_connection((host, port), timeout=1.0):
                return
        except OSError:
            time.sleep(0.2)
    raise TimeoutError(f"Timed out waiting for {host}:{port}")


def start_port_forward(namespace: str, target: str, local_port: int, remote_port: int) -> subprocess.Popen:
    print(f"🔌 Port-forwarding {target} in ns={namespace} → 127.0.0.1:{local_port} (remote {remote_port})")
    proc = subprocess.Popen(
        ["kubectl", "port-forward", "-n", namespace, target, f"{local_port}:{remote_port}"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    # give kubectl a moment to start, then verify the port is open
    time.sleep(1.0)
    wait_for_port("127.0.0.1", local_port, timeout=15.0)
    return proc


def stop_port_forward(proc: subprocess.Popen) -> None:
    if proc and proc.poll() is None:
        print("🧹 Stopping port-forward…")
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


def rewrite_host_port(sqlalchemy_url: str, host: str = "127.0.0.1", port: int = 3307) -> str:
    """
    Rewrite the host:port of a SQLAlchemy URL to use 127.0.0.1:3307, preserving user/pass/db.
    Works for mysql+pymysql://user:pass@host:port/db
    """
    try:
        u = urlparse(sqlalchemy_url)
        # netloc may look like "user:pass@host:port"
        creds, at, _ = u.netloc.rpartition("@")
        new_netloc = f"{creds + at if at else ''}{host}:{port}"
        new = u._replace(netloc=new_netloc)
        return urlunparse(new)
    except Exception:
        # Fallback: common replaces
        s = sqlalchemy_url.replace("localhost:3306", f"{host}:{port}")
        s = s.replace("localhost:3307", f"{host}:{port}")
        s = s.replace("mysql:3306", f"{host}:{port}")
        return s


def build_storage_url_for_local() -> str:
    """
    Use cfg.storage_url if present; otherwise compose from env vars.
    IMPORTANT: best_trial_pipeline.py normalizes 'localhost:3307' for in-cluster,
    so we pass 127.0.0.1:3307 to avoid rewrite.
    """
    url = getattr(cfg, "storage_url", None)
    if url:
        return rewrite_host_port(url, host="127.0.0.1", port=LOCAL_PORT)
    # Compose from env if not provided
    user = os.getenv("MYSQL_USER", "user")
    pwd = os.getenv("MYSQL_PASSWORD", "password")
    db = os.getenv("MYSQL_DB", "optuna")
    return f"mysql+pymysql://{user}:{pwd}@127.0.0.1:{LOCAL_PORT}/{db}"


def run_pipeline(study_name: str, storage_url: str, model_config: str, results_path: str, log_level: str = "INFO") -> int:
    """
    Call best_trial_pipeline.py with flags to save plots and write into results_path.
    """
    print("🚀 Running best_trial_pipeline.py locally…")
    cmd = [
        sys.executable,
        "calib/best_trial_pipeline.py",
        "--study-name",
        study_name,
        "--storage-url",
        storage_url,
        "--model-config",
        model_config,
        "--results-path",
        results_path,
        "--save-plots",
        "--log-level",
        log_level,
    ]
    print("🔧 Command:", " ".join(cmd))
    proc = subprocess.run(cmd)
    return proc.returncode


def main():
    pf = None
    try:
        # 1) start kubectl port-forward to the MySQL service/pod
        pf = start_port_forward(NAMESPACE, PF_TARGET, LOCAL_PORT, REMOTE_PORT)

        # 2) compute a local storage URL (127.0.0.1:3307)
        storage_url = build_storage_url_for_local()

        # 3) run the pipeline
        rc = run_pipeline(
            study_name=cfg.study_name,
            storage_url=storage_url,
            model_config=cfg.model_config,
            results_path=RESULTS_PATH,
            log_level=LOG_LEVEL,
        )
        if rc != 0:
            sys.exit(rc)

        print(f"✅ Done. Results → {RESULTS_PATH}")
    finally:
        # 4) clean up port-forward
        stop_port_forward(pf)


if __name__ == "__main__":
    main()
