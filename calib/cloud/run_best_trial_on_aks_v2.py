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
import json
import subprocess
import sys
import time
from pathlib import Path

import cloud_calib_config as cfg
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
    ap.add_argument("--job-name", default=cfg.job_name, help="Base job name; will become {job_name}-best-trial")
    ap.add_argument("--wait", action="store_true", help="Wait for the job to complete")
    ap.add_argument("--timeout-seconds", type=int, default=7200, help="Wait timeout")
    ap.add_argument("--download", default=None, help="If set, kubectl cp results to this local directory after success")
    ap.add_argument("--requests-cpu", default="2")
    ap.add_argument("--requests-mem", default="8Gi")
    ap.add_argument("--limits-cpu", default="4")
    ap.add_argument("--limits-mem", default="16Gi")
    return ap.parse_args()


def make_job_name(base: str) -> str:
    """Create simple job name: {job_name}-best-trial"""
    return f"{base}-best-trial"


def build_job(args, job_name: str) -> client.V1Job:
    # Container command & args
    # Use bash -lc so env variables expand inside the storage URL.
    # Decide results path inside the container (under the mounted PVC).
    results_path = args.results_subdir or f"results/{args.study_name}/best_trial"
    results_abs = f"{args.mount_path.rstrip('/')}/{results_path}"

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

    container = client.V1Container(
        name="runner",
        image=args.image,
        command=["bash", "-lc"],
        args=[command_line],
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
        ],
        volume_mounts=[client.V1VolumeMount(name="shared", mount_path=args.mount_path)],
        resources=client.V1ResourceRequirements(
            requests={"cpu": args.requests_cpu, "memory": args.requests_mem},
            limits={"cpu": args.limits_cpu, "memory": args.limits_mem},
        ),
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
        image_pull_secrets=([client.V1LocalObjectReference(name=args.image_pull_secret)] if args.image_pull_secret else None),
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


def load_kube():
    # Try local kubeconfig; fall back to in-cluster (if you ever run this inside a pod)
    try:
        config.load_kube_config()
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


def wait_for_completion(batch_api: client.BatchV1Api, namespace: str, job_name: str, timeout_s: int) -> bool:
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        j = batch_api.read_namespaced_job(name=job_name, namespace=namespace)
        if j.status.succeeded and j.status.succeeded >= 1:
            print(f"[INFO] Job {job_name} succeeded")
            return True
        if j.status.failed and j.status.failed >= 1:
            print(f"[ERROR] Job {job_name} failed", file=sys.stderr)
            return False
        time.sleep(5)
    print(f"[ERROR] Timeout waiting for job {job_name}", file=sys.stderr)
    return False


def find_job_pod_name(namespace: str, job_name: str) -> str:
    # Use kubectl because it's simpler than reproducing label selectors here
    cmd = ["kubectl", "get", "pods", "-n", namespace, "-l", f"job-name={job_name}", "-o", "json"]
    out = subprocess.check_output(cmd)
    data = json.loads(out)
    items = data.get("items", [])
    if not items:
        raise RuntimeError("No pods found for job (yet). Try again in a moment.")
    # pick the first (or succeeded) pod
    pod = items[0]
    return pod["metadata"]["name"]


def kubectl_cp_results(namespace: str, pod_name: str, remote_dir: str, local_dir: str):
    Path(local_dir).mkdir(parents=True, exist_ok=True)
    cmd = ["kubectl", "cp", f"{namespace}/{pod_name}:{remote_dir}", str(local_dir)]
    print(f"[INFO] Copying results: {' '.join(cmd)}")
    subprocess.check_call(cmd)


def main():
    args = parse_args()

    # Derive absolute results path inside the container for later copy
    results_path = args.results_subdir or f"results/{args.study_name}/best_trial"
    remote_results = f"{args.mount_path.rstrip('/')}/{results_path}"

    load_kube()
    batch = client.BatchV1Api()

    job_name = make_job_name(args.job_name)
    job = build_job(args, job_name)
    submit_job(batch, args.namespace, job)

    print(f"[INFO] Follow logs: kubectl logs -f job/{job_name} -n {args.namespace}")

    if args.wait:
        ok = wait_for_completion(batch, args.namespace, job_name, args.timeout_seconds)
        if not ok:
            sys.exit(1)

        if args.download:
            try:
                pod = find_job_pod_name(args.namespace, job_name)
                kubectl_cp_results(args.namespace, pod, remote_results, args.download)
                print(f"[INFO] Downloaded results to {args.download}")
            except Exception as e:
                print(f"[WARN] Download failed: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
