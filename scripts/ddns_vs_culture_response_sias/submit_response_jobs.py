"""
Submit jobs to run response SIA scenarios from snapshots.

Phase 2: Load a deterministic snapshot and run response SIA counterfactual
scenarios with different seeds (one per rep) and parameter combinations.

Usage:
    python scripts/ddns_vs_culture_response_sias/submit_response_jobs.py --snapshot-dir /shared/snapshots/ddns_vs_culture/snapshot_nigeria/snapshot_20260626_003159

    python scripts/ddns_vs_culture_response_sias/submit_response_jobs.py \
        --snapshot-dir /shared/snapshots/ddns_vs_culture/snapshot_nigeria/run_id/

    python scripts/ddns_vs_culture_response_sias/submit_response_jobs.py \
        --snapshot-dir /shared/snapshots/ddns_vs_culture/snapshot_nigeria/run_id/ \
        --response-times 40 80 \
        --detection-sensitivities 0.8 1.0 \
        --n-reps 5
"""

import argparse
import subprocess
import tempfile
from datetime import UTC
from datetime import datetime
from pathlib import Path

from active_config import DETECTION_SENSITIVITIES
from active_config import DOCKER_IMAGE
from active_config import N_RESPONSE_REPS
from active_config import OUTPUT_DIR
from active_config import PVC_NAME
from active_config import RESPONSE_CONFIG
from active_config import RESPONSE_TIMES

SCRIPT_DIR = Path(__file__).parent
TEMPLATE_PATH = SCRIPT_DIR / "jobs" / "job_template_response.yaml"


def load_template():
    """Load the job template."""
    with open(TEMPLATE_PATH) as f:
        return f.read()


def verify_snapshot_exists(snapshot_path: str) -> bool:
    """Verify the snapshot file exists on the cluster."""
    # Try sleep-pod first (known to have /shared mounted)
    result = subprocess.run(
        ["kubectl", "get", "pod", "sleep-pod", "-o", "jsonpath={.status.phase}"],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0 and result.stdout.strip() == "Running":
        pod_name = "sleep-pod"
    else:
        # Fallback to any running pod
        result = subprocess.run(
            ["kubectl", "get", "pods", "--field-selector=status.phase=Running", "-o", "jsonpath={.items[0].metadata.name}"],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0 or not result.stdout.strip():
            print("Warning: Could not find running pod to verify snapshot")
            return False
        pod_name = result.stdout.strip()

    # Check if snapshot file exists
    result = subprocess.run(
        ["kubectl", "exec", pod_name, "--", "ls", "-la", snapshot_path],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def create_job_yaml(
    template: str,
    snapshot_path: str,
    rep: int,
    response_time: int,
    detection_sensitivity: float,
    run_id: str,
) -> str:
    """Create job YAML with substituted values."""
    ds_label = str(detection_sensitivity).replace(".", "p")
    job_name = f"ddns-culture-rep{rep}-rt{response_time}-ds{ds_label}"

    return (
        template.replace("{{JOB_NAME}}", job_name)
        .replace("{{IMAGE}}", DOCKER_IMAGE)
        .replace("{{SNAPSHOT_PATH}}", snapshot_path)
        .replace("{{CONFIG_PATH}}", RESPONSE_CONFIG)
        .replace("{{REP}}", str(rep))
        .replace("{{RESPONSE_TIME}}", str(response_time))
        .replace("{{DETECTION_SENSITIVITY}}", str(detection_sensitivity))
        .replace("{{DS_LABEL}}", ds_label)
        .replace("{{OUTPUT_DIR}}", OUTPUT_DIR)
        .replace("{{RUN_ID}}", run_id)
        .replace("{{PVC_NAME}}", PVC_NAME)
    )


def submit_job(job_yaml: str, dry_run: bool = False) -> bool:
    """Submit a job to the cluster."""
    if dry_run:
        print("DRY RUN - would submit:")
        print(job_yaml[:600] + "...")
        return True

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(job_yaml)
        f.flush()

        result = subprocess.run(["kubectl", "apply", "-f", f.name], capture_output=True, text=True)

        if result.returncode != 0:
            print(f"Error: {result.stderr}")
            return False

        print(result.stdout.strip())
        return True


def main():
    parser = argparse.ArgumentParser(description="Submit response SIA jobs from snapshot")
    parser.add_argument("--snapshot-dir", type=str, required=True, help="Directory containing snapshot.h5 on cluster")
    parser.add_argument("--dry-run", action="store_true", help="Print jobs without submitting")
    parser.add_argument("--n-reps", type=int, default=N_RESPONSE_REPS, help="Number of replicates to run")
    parser.add_argument("--response-times", type=int, nargs="+", default=RESPONSE_TIMES, help="Response times to test")
    parser.add_argument(
        "--detection-sensitivities", type=float, nargs="+", default=DETECTION_SENSITIVITIES, help="Detection sensitivities to test"
    )
    parser.add_argument("--run-id", type=str, default=None, help="Run ID (default: auto-generated)")
    parser.add_argument("--reps", type=int, nargs="+", default=None, help="Specific rep numbers to run (default: 0 to n-reps-1)")
    args = parser.parse_args()

    run_id = args.run_id or datetime.now(UTC).strftime("response_%Y%m%d_%H%M%S")

    # Snapshot path (single deterministic snapshot)
    snapshot_path = f"{args.snapshot_dir}/snapshot.h5"

    # Verify snapshot exists
    print(f"Verifying snapshot exists: {snapshot_path}")
    if not verify_snapshot_exists(snapshot_path):
        print("Warning: Could not verify snapshot exists. Continuing anyway...")

    # Determine which reps to run
    if args.reps:
        reps = args.reps
    else:
        reps = list(range(args.n_reps))

    # Calculate total jobs
    n_param_combos = len(args.response_times) * len(args.detection_sensitivities)
    total_jobs = len(reps) * n_param_combos

    print(f"\nRun ID: {run_id}")
    print(f"Snapshot: {snapshot_path}")
    print(f"Reps: {reps}")
    print(f"Response times: {args.response_times}")
    print(f"Detection sensitivities: {args.detection_sensitivities}")
    print(f"Parameter combinations per rep: {n_param_combos}")
    print(f"Total jobs: {total_jobs}")
    print()

    template = load_template()
    submitted = 0
    failed = 0

    for rep in reps:
        for response_time in args.response_times:
            for detection_sensitivity in args.detection_sensitivities:
                job_yaml = create_job_yaml(template, snapshot_path, rep, response_time, detection_sensitivity, run_id)

                if submit_job(job_yaml, args.dry_run):
                    submitted += 1
                else:
                    failed += 1

    print(f"\n{'=' * 60}")
    print(f"Submitted: {submitted}, Failed: {failed}")
    print(f"Run ID: {run_id}")
    print("\nResults will be saved to:")
    print(f"  {OUTPUT_DIR}/{Path(RESPONSE_CONFIG).stem}/{run_id}/")
    print("\nTo check status:")
    print("  kubectl get jobs -l component=ddns-vs-culture,phase=run-response")
    print("\nTo delete response jobs:")
    print("  kubectl delete jobs -l component=ddns-vs-culture,phase=run-response")


if __name__ == "__main__":
    main()
