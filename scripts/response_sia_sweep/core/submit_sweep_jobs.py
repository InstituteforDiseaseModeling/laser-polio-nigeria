#!/usr/bin/env python3
"""
Enhanced job submission script with automatic cleanup and monitoring.

This script submits response-sia-sweep jobs with built-in job lifecycle management,
including automatic cleanup of completed jobs and monitoring capabilities.
"""

import argparse
import json
import subprocess
import time
from datetime import UTC
from datetime import datetime
from datetime import timedelta
from pathlib import Path

from active_config import ACTIVE_CONFIG
from active_config import DEFAULT_DETECTION_TIMES
from active_config import DEFAULT_N_REPS
from active_config import DOCKER_IMAGE_TAG


class JobManager:
    """Manages the lifecycle of response-sia-sweep jobs."""

    def __init__(self, cleanup_delay_hours: int = 1):
        """
        Initialize JobManager.

        Args:
            cleanup_delay_hours: Hours to wait after job completion before cleanup
        """
        self.cleanup_delay_hours = cleanup_delay_hours
        self.job_label = "component=response-sia-sweep"

    def run_kubectl(self, cmd: list[str]) -> tuple[bool, str, str]:
        """Run kubectl command and return success status, stdout, stderr."""
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            return result.returncode == 0, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return False, "", "Command timed out"
        except Exception as e:
            return False, "", str(e)

    def get_job_status(self) -> dict[str, int]:
        """Get count of jobs by status."""
        cmd = ["kubectl", "get", "jobs", "-l", self.job_label, "--no-headers", "-o", "custom-columns=STATUS:.status.conditions[-1].type"]

        success, stdout, stderr = self.run_kubectl(cmd)
        if not success:
            print(f"Warning: Failed to get job status: {stderr}")
            return {}

        status_counts = {}
        for line in stdout.strip().split("\n"):
            if line.strip():
                status = line.strip()
                status_counts[status] = status_counts.get(status, 0) + 1

        return status_counts

    def cleanup_old_completed_jobs(self, dry_run: bool = False) -> int:
        """Clean up completed jobs that are older than cleanup_delay_hours."""
        # Get completed jobs with their completion time
        cmd = ["kubectl", "get", "jobs", "-l", self.job_label, "--no-headers", "-o", "json"]

        success, stdout, stderr = self.run_kubectl(cmd)
        if not success:
            print(f"Warning: Failed to get job details: {stderr}")
            return 0

        try:
            jobs_data = json.loads(stdout)
        except json.JSONDecodeError:
            print("Warning: Failed to parse job data")
            return 0

        jobs_to_cleanup = []
        cutoff_time = datetime.now(UTC) - timedelta(hours=self.cleanup_delay_hours)

        for job in jobs_data.get("items", []):
            job_name = job["metadata"]["name"]

            # Check if job is completed
            conditions = job.get("status", {}).get("conditions", [])
            completed_condition = None
            for condition in conditions:
                if condition.get("type") == "Complete" and condition.get("status") == "True":
                    completed_condition = condition
                    break

            if completed_condition:
                # Parse completion time
                completion_time_str = completed_condition.get("lastTransitionTime")
                if completion_time_str:
                    try:
                        # Parse Kubernetes timestamp format: "2024-11-01T10:30:00Z"
                        completion_time = datetime.fromisoformat(completion_time_str.replace("Z", "+00:00"))

                        if completion_time < cutoff_time:
                            jobs_to_cleanup.append(job_name)
                    except ValueError:
                        # If we can't parse the time, skip this job
                        continue

        if jobs_to_cleanup:
            print(f"{'[DRY RUN] ' if dry_run else ''}Found {len(jobs_to_cleanup)} completed jobs older than {self.cleanup_delay_hours}h")

            if not dry_run:
                # Delete jobs in batches
                batch_size = 50
                deleted = 0
                for i in range(0, len(jobs_to_cleanup), batch_size):
                    batch = jobs_to_cleanup[i : i + batch_size]
                    cmd = ["kubectl", "delete", "jobs", *batch]
                    success, stdout, stderr = self.run_kubectl(cmd)

                    if success:
                        deleted += len(batch)
                        print(f"  ✓ Deleted {len(batch)} jobs")
                    else:
                        print(f"  ✗ Failed to delete batch: {stderr}")

                    time.sleep(0.5)  # Small delay between batches

                return deleted
            else:
                print(f"  Would delete: {', '.join(jobs_to_cleanup[:5])}{'...' if len(jobs_to_cleanup) > 5 else ''}")
                return len(jobs_to_cleanup)

        return 0

    def submit_jobs(self, detection_times: list[int], n_reps: int, dry_run: bool = False) -> dict[str, int]:
        """Submit jobs with enhanced management."""
        # Cleanup old jobs first
        if not dry_run:
            cleaned = self.cleanup_old_completed_jobs()
            if cleaned > 0:
                print(f"🧹 Cleaned up {cleaned} old completed jobs")

        # Generate unique run ID for this batch
        run_id = datetime.now(UTC).strftime("run_%Y%m%d_%H%M%S")

        # Job submission logic (unchanged from original)
        JOB_TEMPLATE_PATH = "scripts/response_sia_sweep/jobs/job_template.yaml"
        CONFIG_PATH = f"scripts/response_sia_sweep/configs/{ACTIVE_CONFIG}"
        IMAGE_NAME = f"idm-docker-staging.packages.idmod.org/laser/response-sia-sweep:{DOCKER_IMAGE_TAG}"
        PVC_NAME = "laser-stg-pvc"
        OUTPUT_DIR = "/shared/results"

        template_path = Path(JOB_TEMPLATE_PATH)
        if not template_path.exists():
            raise FileNotFoundError(f"Missing job template at: {template_path}")

        template_str = template_path.read_text()

        total_jobs = len(detection_times) * n_reps
        submitted = 0
        failed = 0
        skipped = 0

        print(f"🚀 {'[DRY RUN] ' if dry_run else ''}Submitting {total_jobs} jobs ({len(detection_times)} detection times × {n_reps} reps)")
        print(f"Run ID: {run_id}")
        print(f"Config: {ACTIVE_CONFIG}")
        print(f"Detection times: {detection_times}")
        print(f"Using PVC: {PVC_NAME}")
        print(f"Results will be saved to: {OUTPUT_DIR}/{ACTIVE_CONFIG.replace('.yaml', '')}/{run_id}/")
        print("=" * 60)

        for dt in detection_times:
            print(f"\n📊 Detection time = {dt} days:")
            for rep in range(n_reps):
                job_name = f"response-sia-dt{dt}-rep{rep}"

                if dry_run:
                    print(f"  [DRY RUN] Would submit: {job_name}")
                    submitted += 1
                    continue

                job_yaml = (
                    template_str.replace("{{DETECTION_TIME}}", str(dt))
                    .replace("{{REP}}", str(rep))
                    .replace("{{JOB_NAME}}", job_name)
                    .replace("{{IMAGE}}", IMAGE_NAME)
                    .replace("{{CONFIG_PATH}}", CONFIG_PATH)
                    .replace("{{OUTPUT_DIR}}", OUTPUT_DIR)
                    .replace("{{PVC_NAME}}", PVC_NAME)
                    .replace("{{RUN_ID}}", run_id)
                )

                # Add automatic cleanup annotation to the Job metadata (not pod metadata)
                job_yaml = job_yaml.replace(
                    "metadata:\n  name:",
                    f'metadata:\n  annotations:\n    response-sia-sweep/cleanup-delay-hours: "{self.cleanup_delay_hours}"\n  name:',
                )

                yaml_path = Path(f"scripts/response_sia_sweep/jobs/{job_name}.yaml")
                yaml_path.parent.mkdir(exist_ok=True)
                yaml_path.write_text(job_yaml)

                try:
                    # Check if job already exists
                    result = subprocess.run(["kubectl", "get", "job", job_name], capture_output=True, text=True)

                    if result.returncode == 0:
                        print(f"  ⚠️  Job {job_name} already exists, skipping...")
                        skipped += 1
                        continue

                    subprocess.run(["kubectl", "apply", "-f", str(yaml_path)], check=True)
                    print(f"  ✅ Submitted: {job_name}")
                    submitted += 1

                except subprocess.CalledProcessError as e:
                    print(f"  ❌ Failed: {job_name} - {e}")
                    failed += 1

        return {"submitted": submitted, "failed": failed, "skipped": skipped, "total": total_jobs}


def main():
    parser = argparse.ArgumentParser(description="Enhanced response-sia-sweep job submission with lifecycle management")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without actually doing it")
    parser.add_argument("--cleanup-delay-hours", type=int, default=1, help="Hours to wait after completion before cleanup (default: 1)")
    parser.add_argument("--detection-times", nargs="+", type=int, help="Detection times to test (default from config)")
    parser.add_argument("--n-reps", type=int, help="Number of replicates per detection time (default from config)")
    parser.add_argument("--cleanup-only", action="store_true", help="Only run cleanup, don't submit new jobs")
    parser.add_argument("--status", action="store_true", help="Show current job status")

    args = parser.parse_args()

    job_manager = JobManager(cleanup_delay_hours=args.cleanup_delay_hours)

    if args.status:
        print("Current job status:")
        status_counts = job_manager.get_job_status()
        for status, count in status_counts.items():
            print(f"  {status}: {count}")
        return 0

    if args.cleanup_only:
        cleaned = job_manager.cleanup_old_completed_jobs(dry_run=args.dry_run)
        print(f"{'[DRY RUN] ' if args.dry_run else ''}Cleaned up {cleaned} jobs")
        return 0

    # Submit jobs
    detection_times = args.detection_times or DEFAULT_DETECTION_TIMES
    n_reps = args.n_reps or DEFAULT_N_REPS

    results = job_manager.submit_jobs(detection_times, n_reps, dry_run=args.dry_run)

    print("\n" + "=" * 60)
    print(
        f"📊 Summary: {results['submitted']} submitted, {results['failed']} failed, {results['skipped']} skipped, {results['total']} total"
    )

    if results["submitted"] > 0 and not args.dry_run:
        print("\n🔍 Monitor jobs with:")
        print("  kubectl get jobs -l component=response-sia-sweep")
        print("  python3 scripts/response_sia_sweep/core/submit_sweep_jobs.py --status")
        print("\n🧹 Manual cleanup:")
        print("  python3 scripts/response_sia_sweep/core/cleanup_completed_jobs.py")

    return 0


if __name__ == "__main__":
    exit(main())
