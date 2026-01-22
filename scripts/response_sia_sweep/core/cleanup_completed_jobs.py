#!/usr/bin/env python3
"""
Cleanup script for completed response-sia-sweep jobs.

This script safely removes completed Kubernetes jobs from the response-sia-sweep
workflow to free up cluster resources and reduce namespace clutter.
"""

import argparse
import subprocess
import sys
import time


def run_kubectl_command(cmd: list[str]) -> tuple[bool, str, str]:
    """Run kubectl command and return success status, stdout, stderr."""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return result.returncode == 0, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return False, "", "Command timed out"
    except Exception as e:
        return False, "", str(e)


def get_response_sia_jobs(status_filter: str | None = None) -> list[str]:
    """Get list of response-sia jobs, optionally filtered by status."""
    cmd = ["kubectl", "get", "jobs", "--no-headers", "-o", "custom-columns=NAME:.metadata.name,STATUS:.status.conditions[-1].type"]

    success, stdout, stderr = run_kubectl_command(cmd)
    if not success:
        print(f"Error getting jobs: {stderr}")
        return []

    jobs = []
    for line in stdout.strip().split("\n"):
        if not line.strip():
            continue

        parts = line.strip().split()
        if len(parts) >= 2:
            job_name, job_status = parts[0], parts[1]

            # Filter for response-sia jobs
            if job_name.startswith("config-nigeria-"):
                if status_filter is None or job_status == status_filter:
                    jobs.append(job_name)

    return jobs


def delete_jobs_batch(job_names: list[str], batch_size: int = 50, dry_run: bool = False) -> bool:
    """Delete jobs in batches to avoid overwhelming the API server."""
    if not job_names:
        print("No jobs to delete.")
        return True

    total_jobs = len(job_names)
    print(f"{'[DRY RUN] ' if dry_run else ''}Deleting {total_jobs} jobs in batches of {batch_size}")

    success_count = 0
    failure_count = 0

    for i in range(0, total_jobs, batch_size):
        batch = job_names[i : i + batch_size]
        batch_num = (i // batch_size) + 1
        total_batches = (total_jobs + batch_size - 1) // batch_size

        print(f"{'[DRY RUN] ' if dry_run else ''}Processing batch {batch_num}/{total_batches} ({len(batch)} jobs)...")

        if dry_run:
            print(f"  Would delete: {', '.join(batch[:3])}{'...' if len(batch) > 3 else ''}")
            success_count += len(batch)
        else:
            # Delete batch
            cmd = ["kubectl", "delete", "jobs", *batch]
            success, stdout, stderr = run_kubectl_command(cmd)

            if success:
                success_count += len(batch)
                print(f"  ✓ Successfully deleted {len(batch)} jobs")
            else:
                failure_count += len(batch)
                print(f"  ✗ Failed to delete batch: {stderr}")

        # Small delay between batches to be gentle on API server
        if not dry_run and i + batch_size < total_jobs:
            time.sleep(1)

    print(f"\n{'[DRY RUN] ' if dry_run else ''}Summary:")
    print(f"  Success: {success_count}")
    print(f"  Failures: {failure_count}")
    print(f"  Total: {total_jobs}")

    return failure_count == 0


def main():
    parser = argparse.ArgumentParser(description="Cleanup completed response-sia-sweep jobs")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be deleted without actually deleting")
    parser.add_argument("--batch-size", type=int, default=50, help="Number of jobs to delete in each batch (default: 50)")
    parser.add_argument(
        "--status",
        choices=["Complete", "Failed", "Running", "All"],
        default="Complete",
        help="Job status to filter by (default: Complete). Use 'All' to delete jobs with any status",
    )

    args = parser.parse_args()

    print("Response SIA Sweep Job Cleanup Tool")
    print("=" * 40)

    # Get jobs with specified status
    if args.status == "All":
        print("Searching for ALL response-sia jobs (any status)")
        jobs = get_response_sia_jobs(status_filter=None)
    else:
        print(f"Searching for response-sia jobs with status: {args.status}")
        jobs = get_response_sia_jobs(status_filter=args.status)

    if not jobs:
        print(f"No response-sia jobs found with status '{args.status}'")
        return 0

    print(f"Found {len(jobs)} jobs to process")

    # Show sample of jobs that will be affected
    if len(jobs) <= 10:
        print(f"Jobs: {', '.join(jobs)}")
    else:
        print(f"Sample jobs: {', '.join(jobs[:5])}, ..., {', '.join(jobs[-2:])}")

    # Confirm deletion (unless dry run)
    if not args.dry_run:
        status_desc = "jobs (ALL statuses)" if args.status == "All" else f"{args.status.lower()} jobs"
        response = input(f"\nAre you sure you want to delete {len(jobs)} {status_desc}? (yes/no): ")
        if response.lower() != "yes":
            print("Cancelled.")
            return 1

    # Perform deletion
    success = delete_jobs_batch(jobs, args.batch_size, args.dry_run)

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
