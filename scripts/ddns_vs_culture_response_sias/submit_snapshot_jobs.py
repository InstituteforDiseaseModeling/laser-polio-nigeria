"""
Submit job to create a population snapshot.

Phase 1: Run a calibrated simulation (with fixed seed from config) and save
a snapshot at the final timestep. This snapshot is deterministic and can be
used to initialize multiple response SIA counterfactual scenarios.

Usage:
    python scripts/ddns_vs_culture_response_sias/submit_snapshot_jobs.py
    python scripts/ddns_vs_culture_response_sias/submit_snapshot_jobs.py --dry-run
"""

import argparse
import subprocess
import tempfile
from datetime import UTC
from datetime import datetime
from pathlib import Path

from active_config import DOCKER_IMAGE
from active_config import PVC_NAME
from active_config import SNAPSHOT_CONFIG
from active_config import SNAPSHOT_DIR

SCRIPT_DIR = Path(__file__).parent
TEMPLATE_PATH = SCRIPT_DIR / "jobs" / "job_template_snapshot.yaml"


def load_template():
    """Load the job template."""
    with open(TEMPLATE_PATH) as f:
        return f.read()


def create_job_yaml(template: str, run_id: str) -> str:
    """Create job YAML with substituted values."""
    job_name = "ddns-culture-snapshot"

    return (
        template.replace("{{JOB_NAME}}", job_name)
        .replace("{{IMAGE}}", DOCKER_IMAGE)
        .replace("{{CONFIG_PATH}}", SNAPSHOT_CONFIG)
        .replace("{{OUTPUT_DIR}}", SNAPSHOT_DIR)
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
    parser = argparse.ArgumentParser(description="Submit snapshot creation job")
    parser.add_argument("--dry-run", action="store_true", help="Print job without submitting")
    parser.add_argument("--run-id", type=str, default=None, help="Run ID (default: auto-generated)")
    args = parser.parse_args()

    run_id = args.run_id or datetime.now(UTC).strftime("snapshot_%Y%m%d_%H%M%S")

    print(f"Run ID: {run_id}")
    print(f"Snapshot config: {SNAPSHOT_CONFIG}")
    print("Single deterministic snapshot (seed and n_days from config file)")
    print()

    template = load_template()
    job_yaml = create_job_yaml(template, run_id)

    if submit_job(job_yaml, args.dry_run):
        print(f"\n{'=' * 60}")
        print("Submitted: 1")
        print(f"Run ID: {run_id}")
        print("\nSnapshot will be saved to:")
        print(f"  {SNAPSHOT_DIR}/{Path(SNAPSHOT_CONFIG).stem}/{run_id}/snapshot.h5")
        print("\nTo check status:")
        print("  kubectl get jobs -l component=ddns-vs-culture,phase=create-snapshot")
        print("\nTo delete snapshot job:")
        print("  kubectl delete jobs -l component=ddns-vs-culture,phase=create-snapshot")
    else:
        print("Failed to submit job")


if __name__ == "__main__":
    main()
