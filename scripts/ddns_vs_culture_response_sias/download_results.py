"""
Download snapshot and response SIA results from the cluster.

Downloads the latest (or specified) snapshot and response results,
including the .h5 snapshot file, metrics, and timeseries.

Uses a temporary utility pod with tar installed (required by kubectl cp).

Usage:
    python scripts/ddns_vs_culture_response_sias/download_results.py
    python scripts/ddns_vs_culture_response_sias/download_results.py --snapshot-only
    python scripts/ddns_vs_culture_response_sias/download_results.py --response-only
    python scripts/ddns_vs_culture_response_sias/download_results.py --snapshot-run-id snapshot_20260626_003159
"""

import argparse
import subprocess
import sys
import time
import uuid
from pathlib import Path

from kubernetes import client
from kubernetes import config
from kubernetes.client.rest import ApiException

sys.path.insert(0, str(Path(__file__).parent))

from active_config import OUTPUT_DIR
from active_config import PVC_NAME
from active_config import SNAPSHOT_DIR

# Cluster paths (derived from active_config)
CLUSTER_SNAPSHOT_BASE = f"{SNAPSHOT_DIR}/snapshot_nigeria"
CLUSTER_RESPONSE_BASE = f"{OUTPUT_DIR}/response_nigeria"

# Local paths
LOCAL_BASE = Path("results/ddns_vs_culture_response_sias")

# Utility pod image (has tar installed, required by kubectl cp)
UTIL_IMAGE = "registry4idm.azurecr.io/nfstest:1.1"
UTIL_REGISTRY_SECRET = "registry4idm"  # noqa: S105
NAMESPACE = "default"


def run_cmd(cmd, check=True):
    """Run a shell command and return output."""
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if check and result.returncode != 0:
        print(f"Error: {result.stderr}")
        return None
    return result.stdout.strip()


def create_util_pod(pod_name):
    """Create a temporary utility pod with tar installed and shared storage mounted."""
    print(f"Creating utility pod '{pod_name}'...")
    pod = client.V1Pod(
        metadata=client.V1ObjectMeta(name=pod_name, namespace=NAMESPACE),
        spec=client.V1PodSpec(
            containers=[
                client.V1Container(
                    name="util",
                    image=UTIL_IMAGE,
                    command=["sleep", "infinity"],
                    volume_mounts=[client.V1VolumeMount(name="shared-data", mount_path="/shared")],
                )
            ],
            restart_policy="Never",
            image_pull_secrets=[client.V1LocalObjectReference(name=UTIL_REGISTRY_SECRET)],
            volumes=[
                client.V1Volume(
                    name="shared-data",
                    persistent_volume_claim=client.V1PersistentVolumeClaimVolumeSource(claim_name=PVC_NAME),
                )
            ],
        ),
    )
    api = client.CoreV1Api()
    api.create_namespaced_pod(namespace=NAMESPACE, body=pod)


def wait_for_pod(pod_name, timeout=120):
    """Wait for pod to be running."""
    print(f"Waiting for pod '{pod_name}'...", end="", flush=True)
    api = client.CoreV1Api()
    start = time.time()
    while time.time() - start < timeout:
        try:
            pod = api.read_namespaced_pod(name=pod_name, namespace=NAMESPACE)
            if pod.status.phase == "Running":
                print(" Ready.")
                return True
        except ApiException:
            pass
        print(".", end="", flush=True)
        time.sleep(2)
    print(" Timed out!")
    return False


def delete_pod(pod_name):
    """Delete the utility pod."""
    print(f"Cleaning up pod '{pod_name}'...")
    try:
        api = client.CoreV1Api()
        api.delete_namespaced_pod(name=pod_name, namespace=NAMESPACE)
    except ApiException as e:
        print(f"Warning: Could not delete pod: {e}")


def find_latest_run(pod_name, cluster_base, label):
    """Find the most recent run directory on the cluster."""
    print(f"\nFinding {label} results on cluster...")
    dirs = run_cmd(f"kubectl exec {pod_name} -- ls {cluster_base} 2>/dev/null")

    if not dirs:
        print(f"No {label} results found at {cluster_base}")
        return None

    runs = sorted(dirs.strip().split("\n"))
    latest = runs[-1]
    print(f"Found {len(runs)} run(s). Latest: {latest}")
    return latest


def list_cluster_files(pod_name, cluster_path):
    """List files at a cluster path."""
    output = run_cmd(f"kubectl exec {pod_name} -- find {cluster_path} -type f 2>/dev/null")
    if not output:
        return []
    return output.strip().split("\n")


def download_dir(pod_name, cluster_path, local_path):
    """Download a directory from the cluster via the utility pod."""
    local_path.mkdir(parents=True, exist_ok=True)
    print(f"  Downloading: {cluster_path}")
    print(f"          to: {local_path}")

    result = subprocess.run(
        f"kubectl cp {NAMESPACE}/{pod_name}:{cluster_path} {local_path}",
        shell=True,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        print(f"  Download failed: {result.stderr}")
        return False

    return True


def download_snapshot(pod_name, run_id=None):
    """Download snapshot results (metrics, timeseries, and .h5 file)."""
    print("=" * 60)
    print("DOWNLOADING SNAPSHOT RESULTS")
    print("=" * 60)

    if run_id is None:
        run_id = find_latest_run(pod_name, CLUSTER_SNAPSHOT_BASE, "snapshot")
        if not run_id:
            return None

    cluster_path = f"{CLUSTER_SNAPSHOT_BASE}/{run_id}"
    local_path = LOCAL_BASE / "snapshots" / run_id

    # Show what's available
    files = list_cluster_files(pod_name, cluster_path)
    print(f"Files on cluster ({len(files)}):")
    for f in files:
        print(f"  {f}")

    # Download everything (including .h5)
    if download_dir(pod_name, cluster_path, local_path):
        # Verify download
        local_files = [f for f in local_path.rglob("*") if f.is_file()]
        print(f"\nDownloaded {len(local_files)} files:")
        for f in sorted(local_files):
            size_mb = f.stat().st_size / (1024 * 1024)
            print(f"  {f.relative_to(local_path)} ({size_mb:.1f} MB)")
        print(f"\nSnapshot saved to: {local_path}")
        return run_id
    return None


def download_response(pod_name, run_id=None):
    """Download response SIA results (metrics and timeseries)."""
    print("\n" + "=" * 60)
    print("DOWNLOADING RESPONSE SIA RESULTS")
    print("=" * 60)

    if run_id is None:
        run_id = find_latest_run(pod_name, CLUSTER_RESPONSE_BASE, "response")
        if not run_id:
            return None

    cluster_path = f"{CLUSTER_RESPONSE_BASE}/{run_id}"
    local_path = LOCAL_BASE / "responses" / run_id

    # Show what's available
    for subdir in ["results", "timeseries", "errors"]:
        count = run_cmd(f"kubectl exec {pod_name} -- ls {cluster_path}/{subdir} 2>/dev/null | wc -l")
        if count:
            print(f"  {subdir}: {count.strip()} files")

    # Download everything
    if download_dir(pod_name, cluster_path, local_path):
        # Verify download
        results_files = list((local_path / "results").glob("*.csv")) if (local_path / "results").exists() else []
        timeseries_files = list((local_path / "timeseries").glob("*.csv")) if (local_path / "timeseries").exists() else []
        error_files = list((local_path / "errors").glob("*.txt")) if (local_path / "errors").exists() else []

        print("\nDownloaded:")
        print(f"  {len(results_files)} result files")
        print(f"  {len(timeseries_files)} timeseries files")
        if error_files:
            print(f"  {len(error_files)} error files (check these!)")
        print(f"\nResponse results saved to: {local_path}")
        return run_id
    return None


def main():
    parser = argparse.ArgumentParser(description="Download snapshot and response SIA results from cluster")
    parser.add_argument("--snapshot-only", action="store_true", help="Only download snapshot results")
    parser.add_argument("--response-only", action="store_true", help="Only download response results")
    parser.add_argument("--snapshot-run-id", type=str, default=None, help="Specific snapshot run ID to download")
    parser.add_argument("--response-run-id", type=str, default=None, help="Specific response run ID to download")
    args = parser.parse_args()

    # Default: download both
    do_snapshot = not args.response_only
    do_response = not args.snapshot_only

    # Load kube config and create utility pod
    config.load_kube_config()
    pod_name = f"download-util-{uuid.uuid4().hex[:8]}"

    create_util_pod(pod_name)
    try:
        if not wait_for_pod(pod_name):
            print("Failed to start utility pod.")
            return 1

        snapshot_run_id = None
        response_run_id = None

        if do_snapshot:
            snapshot_run_id = download_snapshot(pod_name, args.snapshot_run_id)

        if do_response:
            response_run_id = download_response(pod_name, args.response_run_id)

        # Summary
        print("\n" + "=" * 60)
        print("DOWNLOAD COMPLETE")
        print("=" * 60)
        if snapshot_run_id:
            print(f"  Snapshot: {LOCAL_BASE / 'snapshots' / snapshot_run_id}")
        if response_run_id:
            print(f"  Response: {LOCAL_BASE / 'responses' / response_run_id}")
        if not snapshot_run_id and not response_run_id:
            print("  No results downloaded.")
            return 1

        return 0
    finally:
        delete_pod(pod_name)


if __name__ == "__main__":
    exit(main())
