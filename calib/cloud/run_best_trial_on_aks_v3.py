#!/usr/bin/env python3
"""
Submit best_trial_pipeline.py as a Kubernetes Job on AKS.

Requirements on your laptop:
  pip install kubernetes

Cluster prerequisites:
  - Container image has best_trial_pipeline.py at /app/best_trial_pipeline.py
  - Secret with MySQL creds (user/password/db)
  - RWX PVC for writing results (e.g., azurefile-csi)

Example:
  python run_best_trial_on_aks.py \
    --image myregistry.azurecr.io/laser-polio-best:latest \
    --namespace research \
    --study-name POLIO_STUDY \
    --model-config zamfara.yaml \
    --results-subdir results/POLIO_STUDY/best_trial \
    --pvc-name shared-pvc \
    --mysql-secret mysql-secret \
    --wait --timeout-seconds 7200 \
    --download ./results/POLIO_STUDY/best_trial
"""

from __future__ import annotations

import argparse
import datetime
import subprocess
import sys
import time
from pathlib import Path

import cloud_calib_config as cfg
import runtime_wrapper
from kubernetes import client
from kubernetes import config
from kubernetes.client.rest import ApiException


def parse_args():
    ap = argparse.ArgumentParser(description="Submit best_trial_pipeline.py to AKS as a Job.")
    # What to run (defaults from cloud_calib_config.py)
    ap.add_argument("--image", default=cfg.image, help="Container image with best_trial_pipeline.py")
    ap.add_argument("--study-name", default=cfg.study_name, help="Optuna study name")
    ap.add_argument("--model-config", default=cfg.model_config, help="YAML under calib/model_configs/ inside the image")
    # Where to write results in the container (under mounted PVC)
    ap.add_argument(
        "--results-subdir",
        default=None,
        help="Path under mounted volume to store outputs (e.g., results/<study>/best_trial). If omitted, uses results/<study>/best_trial.",
    )
    # Cluster plumbing (defaults from cloud_calib_config.py)
    ap.add_argument("--namespace", default=cfg.namespace)
    ap.add_argument("--pvc-name", default="laser-stg-pvc", help="PVC name to mount")
    ap.add_argument("--mount-path", default="/shared", help="Container mount path for the PVC")
    ap.add_argument("--image-pull-secret", default="idmodregcred3", help="ImagePullSecret name, if your ACR requires it")
    # MySQL connectivity
    ap.add_argument("--mysql-secret", default="mysql-secrets", help="K8s Secret with keys: user, password, db")
    ap.add_argument("--mysql-host", default="mysql", help="Service DNS for MySQL in-cluster")
    ap.add_argument("--mysql-port", default="3306", help="Port for MySQL")
    # Storage URL override (optional; otherwise we build from env)
    ap.add_argument(
        "--storage-url",
        default=cfg.storage_url,
        help="Optuna storage URL. If not provided, uses mysql+pymysql://$MYSQL_USER:$MYSQL_PASSWORD@<host>:<port>/$MYSQL_DB",
    )
    # Behavior
    ap.add_argument("--job-name", default=cfg.job_name, help="Base job name; will become {job_name}")
    ap.add_argument("--wait", action="store_true", default=True, help="Wait for the job to complete (default: True)")
    ap.add_argument("--timeout-seconds", type=int, default=7200, help="Wait timeout in seconds; 0 = no timeout (default: 7200)")
    ap.add_argument(
        "--download",
        default="./results/{study_name}/best_trial/",
        help="Download results to this local directory (default: ./results/{study_name}/best_trial/)",
    )
    ap.add_argument("--requests-mem", default="100G")
    return ap.parse_args()


def make_job_name(base: str) -> str:
    """Add -best-trial suffix to distinguish from regular calibration jobs."""
    return f"{base}-best"


def build_job(args, job_name, results_abs: str) -> client.V1Job:
    # Container command & args
    # Use bash -lc so env variables expand inside the storage URL.
    # Decide results path inside the container (under the mounted PVC).

    if args.storage_url:
        storage_arg = f"--storage-url {args.storage_url}"
    else:
        storage_arg = f"--storage-url mysql+pymysql://$MYSQL_USER:$MYSQL_PASSWORD@{args.mysql_host}:{args.mysql_port}/$MYSQL_DB"

    command_line = (
        "python3 calib/best_trial_pipeline.py "
        f"--study-name {args.study_name} "
        f"{storage_arg} "
        f"--model-config {args.model_config} "
        f"--results-path {results_abs} "
        "--save-plots "
        "--log-level INFO"
    )

    wrapped_command = runtime_wrapper.wrap_command(
        [command_line],
        shared_bin_dir=str(Path(args.mount_path) / "simulation" / "bin"),
        dont_wrap=False,
    )

    container = client.V1Container(
        name="runner",
        image=args.image,
        command=wrapped_command,
        env=[
            client.V1EnvVar(
                name="MYSQL_USER",
                value_from=client.V1EnvVarSource(secret_key_ref=client.V1SecretKeySelector(name=args.mysql_secret, key="MYSQL_USER")),
            ),
            client.V1EnvVar(
                name="MYSQL_PASSWORD",
                value_from=client.V1EnvVarSource(secret_key_ref=client.V1SecretKeySelector(name=args.mysql_secret, key="MYSQL_PASSWORD")),
            ),
            client.V1EnvVar(
                name="MYSQL_DB",
                value_from=client.V1EnvVarSource(secret_key_ref=client.V1SecretKeySelector(name=args.mysql_secret, key="MYSQL_DB")),
            ),
            client.V1EnvVar(name="PYTHONUNBUFFERED", value="1"),
            client.V1EnvVar(name="JOB_NAME", value=job_name),
            client.V1EnvVar(
                name="POD_NAME", value_from=client.V1EnvVarSource(field_ref=client.V1ObjectFieldSelector(field_path="metadata.name"))
            ),
        ],
        volume_mounts=[client.V1VolumeMount(name="shared", mount_path=args.mount_path)],
        resources=client.V1ResourceRequirements(requests={"memory": args.requests_mem}),
    )

    volumes = [
        client.V1Volume(
            name="shared",
            persistent_volume_claim=client.V1PersistentVolumeClaimVolumeSource(claim_name=args.pvc_name),
        )
    ]

    pod_spec = client.V1PodSpec(
        restart_policy="Never",
        containers=[container],
        volumes=volumes,
        image_pull_secrets=(
            [client.V1LocalObjectReference(name=args.image_pull_secret), client.V1LocalObjectReference(name="registry4idm")]
        ),
        node_selector={"nodepool": "128gb"},
        tolerations=[client.V1Toleration(key="nodepool", operator="Equal", value="128gb", effect="NoSchedule")],
    )

    template = client.V1PodTemplateSpec(
        metadata=client.V1ObjectMeta(labels={"job-name": job_name}),
        spec=pod_spec,
    )

    job_spec = client.V1JobSpec(
        backoff_limit=0,
        template=template,
    )

    job = client.V1Job(
        metadata=client.V1ObjectMeta(name=job_name, namespace=args.namespace),
        spec=job_spec,
    )
    return job


def load_kube(config_path: str | None):
    if config_path and not Path(config_path).exists():
        raise FileNotFoundError(f"Config file {config_path} does not exist.")

    try:
        config.load_kube_config(config_file=config_path)
    except Exception:
        config.load_incluster_config()


def delete_job_if_exists(batch_api: client.BatchV1Api, namespace: str, job_name: str):
    """Delete a job if it exists."""
    try:
        batch_api.read_namespaced_job(name=job_name, namespace=namespace)
        print(f"[INFO] Found existing job {job_name}, deleting it...")
        batch_api.delete_namespaced_job(name=job_name, namespace=namespace)
        print(f"[INFO] Deleted existing job {job_name}")
        # Wait a moment for deletion to complete
        time.sleep(2)
    except ApiException as e:
        if e.status == 404:
            # Job doesn't exist, which is fine
            pass
        else:
            print(f"[WARN] Could not check/delete existing job: {e}", file=sys.stderr)


def submit_job(batch_api: client.BatchV1Api, namespace: str, job: client.V1Job):
    job_name = job.metadata.name

    # Delete existing job if it exists
    delete_job_if_exists(batch_api, namespace, job_name)

    try:
        resp = batch_api.create_namespaced_job(namespace=namespace, body=job)
        print(f"[INFO] Created job {resp.metadata.name} in {namespace}")
        return resp.metadata.name
    except ApiException as e:
        print(f"[ERROR] create_namespaced_job failed: {e}", file=sys.stderr)
        raise


def wait_for_completion(batch_api: client.BatchV1Api, namespace: str, job_name: str, timeout_s: int = 0) -> bool:
    t0 = time.time()
    print(f"[INFO] Monitoring job {job_name} (checking every 30 seconds)...")

    while timeout_s == 0 or time.time() - t0 < timeout_s:
        j = batch_api.read_namespaced_job(name=job_name, namespace=namespace)
        elapsed = int(time.time() - t0)
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")  # noqa: DTZ005

        if j.status.succeeded and j.status.succeeded >= 1:
            print(f"[{timestamp}] Job {job_name} succeeded (elapsed: {elapsed}s)")
            return True
        if j.status.failed and j.status.failed >= 1:
            print(f"[{timestamp}] Job {job_name} failed (elapsed: {elapsed}s)", file=sys.stderr)
            return False

        # Show status update
        active = j.status.active or 0
        print(f"[{timestamp}] Job {job_name} still running (active pods: {active}, elapsed: {elapsed}s)")
        time.sleep(30)

    elapsed = int(time.time() - t0)
    print(f"[ERROR] Timeout waiting for job {job_name} after {elapsed}s", file=sys.stderr)
    return False


def validate_local_dir(local_dir: str):
    local_dir_path = Path(local_dir)
    if not local_dir_path.exists():
        print(f"[INFO] Creating local directory {local_dir}")
        local_dir_path.mkdir(parents=True, exist_ok=True)
    elif not local_dir_path.is_dir():
        raise ValueError(f"Local path {local_dir} exists and is not a directory.")
    return local_dir_path.absolute()


def run_kubeutil_download(namespace: str, remote_dir: str, local_dir: str, config_file: str | None, script_path: str = "kubeutil.py"):
    """
    Execute kubeutil.py with the given arguments. Kubeutil spins up its own pod to do the copy.

    1. namespace: K8s namespace
    2. remote_dir: Directory in the cluster to copy from
    3. local_dir: Local directory to copy to
    4. config_file: Optional kubeconfig file path
    5. script_path: Path to kubeutil.py
    """
    local_dir_abs = validate_local_dir(local_dir)
    if not Path(script_path).exists():
        raise FileNotFoundError(f"kubeutil.py not found at {script_path}")

    cmd = [
        "python3",
        script_path,
        "--namespace",
        namespace,
        "--remote-dir",
        remote_dir,
        "--local-dir",
        local_dir_abs,
        "--action",
        "download",
    ]

    if config_file:
        cmd += ["--config", config_file]
    subprocess.check_call(cmd)


def main():
    args = parse_args()

    # Derive absolute results path inside the container for later copy
    results_path = f"/app/output/{args.study_name}/"
    remote_root_path = f"/shared/simulation/run/{cfg.job_name}/"

    # kube_config = "/home/ned/cditest4.yaml"
    kube_config = None  # Use default

    # Handle dynamic substitution in download path
    if args.download:
        download_path = args.download.format(study_name=args.study_name)
        full_path = validate_local_dir(download_path)
    else:
        full_path = None

    job_name = make_job_name(args.job_name)
    load_kube(config_path=kube_config)
    batch = client.BatchV1Api()
    job = build_job(args, job_name, results_path)
    submit_job(batch, args.namespace, job)
    print(f"[INFO] Follow logs: kubectl logs -f job/{job_name} -n {args.namespace}")

    if args.wait:
        ok = wait_for_completion(batch, args.namespace, job_name, timeout_s=args.timeout_seconds)
        if not ok:
            sys.exit(1)

        if args.download:
            try:
                run_kubeutil_download(
                    namespace=args.namespace,
                    remote_dir=remote_root_path,
                    local_dir=download_path,
                    config_file=kube_config,
                    script_path="calib/cloud/kubeutil.py",
                )
                print(f"[INFO] Downloaded results to {full_path}")
            except Exception as e:
                print(f"[WARN] Download failed: {e}", file=sys.stderr)
            print(f"[INFO] Job {job_name} completed.")


if __name__ == "__main__":
    main()
