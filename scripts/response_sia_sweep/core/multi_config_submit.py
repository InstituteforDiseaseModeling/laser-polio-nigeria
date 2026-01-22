"""
Submit jobs for multiple configurations in parallel.

This script allows running multiple model configurations simultaneously,
tracking their progress, and downloading results as they complete.
"""

import argparse
import subprocess
import time
from datetime import UTC
from datetime import datetime
from pathlib import Path

import yaml

# Import default settings
from active_config import DEFAULT_N_REPS
from active_config import DEFAULT_RESPONSE_TIMES
from active_config import DOCKER_IMAGE_TAG

UTC = UTC


class MultiConfigJobManager:
    """Manages submission and monitoring of jobs for multiple configurations."""

    def __init__(self, configs: list[str], response_times: list[int] = None, n_reps: int = None):
        """
        Initialize multi-config job manager.

        Args:
            configs: List of config file names to run
            response_times: Response times to test (uses DEFAULT if None)
            n_reps: Number of replicates per response time (uses DEFAULT if None)
        """
        self.configs = configs
        self.response_times = response_times or DEFAULT_RESPONSE_TIMES
        self.n_reps = n_reps or DEFAULT_N_REPS
        self.job_label = "component=response-sia-sweep"

        # Track run IDs for each config
        self.run_ids: dict[str, str] = {}

        # Job template and paths
        self.JOB_TEMPLATE_PATH = "scripts/response_sia_sweep/jobs/job_template.yaml"
        self.CONFIG_DIR = "scripts/response_sia_sweep/configs"
        self.IMAGE_NAME = f"idm-docker-staging.packages.idmod.org/laser/response-sia-sweep:{DOCKER_IMAGE_TAG}"
        self.PVC_NAME = "laser-stg-pvc"
        self.OUTPUT_DIR = "/shared/results"

    def validate_configs(self) -> bool:
        """Validate that all config files exist."""
        all_valid = True
        for config in self.configs:
            config_path = Path(self.CONFIG_DIR) / config
            if not config_path.exists():
                print(f"❌ Config file not found: {config_path}")
                all_valid = False
            else:
                # Load and validate config has required fields
                with open(config_path) as f:
                    config_data = yaml.safe_load(f)
                if "results_path" not in config_data:
                    print(f"⚠️  Warning: Config {config} missing 'results_path' field")
        return all_valid

    def run_kubectl(self, cmd: list[str]) -> tuple[bool, str, str]:
        """Run kubectl command and return success status, stdout, stderr."""
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            return result.returncode == 0, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return False, "", "Command timed out"
        except Exception as e:
            return False, "", str(e)

    def get_job_status_for_config(self, config_name: str) -> dict[str, int]:
        """Get job status for a specific config."""
        # Make job-safe name for label matching
        job_safe_name = config_name.replace(".yaml", "").replace("_", "-").replace(".", "-").lower()
        config_label = f"config={job_safe_name}"
        cmd = [
            "kubectl",
            "get",
            "jobs",
            "-l",
            f"{self.job_label},{config_label}",
            "--no-headers",
            "-o",
            "custom-columns=STATUS:.status.conditions[-1].type",
        ]

        success, stdout, stderr = self.run_kubectl(cmd)
        if not success:
            return {}

        status_counts = {}
        for line in stdout.strip().split("\n"):
            if line.strip():
                status = line.strip()
                status_counts[status] = status_counts.get(status, 0) + 1

        return status_counts

    def submit_jobs_for_config(self, config: str, dry_run: bool = False) -> dict[str, int]:
        """Submit all jobs for a single config."""
        config_name = config.replace(".yaml", "")
        # Make job-safe name (Kubernetes requires lowercase alphanumeric and hyphens only)
        job_safe_config_name = config_name.replace("_", "-").replace(".", "-").lower()

        # Generate unique run ID for this config
        # Add microseconds and config identifier to ensure uniqueness
        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S%f")[:-3]  # Include milliseconds
        run_id = f"run_{timestamp}"
        self.run_ids[config] = run_id

        # Load job template
        template_path = Path(self.JOB_TEMPLATE_PATH)
        if not template_path.exists():
            raise FileNotFoundError(f"Missing job template at: {template_path}")

        template_str = template_path.read_text()

        # Statistics
        total_jobs = len(self.response_times) * self.n_reps
        submitted = 0
        failed = 0
        skipped = 0

        print(f"\n📁 Config: {config}")
        print(f"   Run ID: {run_id}")
        print(f"   Jobs: {total_jobs} ({len(self.response_times)} response times × {self.n_reps} reps)")

        for rt in self.response_times:
            for rep in range(self.n_reps):
                # Use job-safe config name in job name for uniqueness
                job_name = f"{job_safe_config_name}-rt{rt}-rep{rep}"

                if dry_run:
                    submitted += 1
                    continue

                # Prepare job YAML with config-specific values
                job_yaml = (
                    template_str.replace("{{RESPONSE_TIME}}", str(rt))
                    .replace("{{REP}}", str(rep))
                    .replace("{{JOB_NAME}}", job_name)
                    .replace("{{IMAGE}}", self.IMAGE_NAME)
                    .replace("{{CONFIG_PATH}}", f"{self.CONFIG_DIR}/{config}")
                    .replace("{{OUTPUT_DIR}}", self.OUTPUT_DIR)
                    .replace("{{PVC_NAME}}", self.PVC_NAME)
                    .replace("{{RUN_ID}}", run_id)
                )

                # Add config label to job for easier filtering
                job_yaml = job_yaml.replace(
                    "labels:\n    component: response-sia-sweep",
                    f"labels:\n    component: response-sia-sweep\n    config: {job_safe_config_name}",
                )

                # Save job YAML
                yaml_path = Path(f"scripts/response_sia_sweep/jobs/{job_name}.yaml")
                yaml_path.parent.mkdir(exist_ok=True)
                yaml_path.write_text(job_yaml)

                try:
                    # Check if job already exists
                    result = subprocess.run(["kubectl", "get", "job", job_name], capture_output=True, text=True)

                    if result.returncode == 0:
                        skipped += 1
                        continue

                    subprocess.run(["kubectl", "apply", "-f", str(yaml_path)], check=True, capture_output=True)
                    submitted += 1

                    # Small delay to avoid overwhelming the API
                    if submitted % 10 == 0:
                        print(f"   Progress: {submitted}/{total_jobs} submitted...")
                        time.sleep(0.5)

                except subprocess.CalledProcessError:
                    failed += 1

        print(f"   ✅ Submitted: {submitted}, ⚠️ Skipped: {skipped}, ❌ Failed: {failed}")

        return {"submitted": submitted, "failed": failed, "skipped": skipped, "total": total_jobs}

    def submit_all_configs(self, dry_run: bool = False) -> dict[str, dict[str, int]]:
        """Submit jobs for all configurations."""
        if not self.validate_configs():
            print("❌ Config validation failed. Please fix issues before proceeding.")
            return {}

        print(f"\n🚀 {'[DRY RUN] ' if dry_run else ''}Submitting jobs for {len(self.configs)} configurations")
        print(f"Response times: {self.response_times}")
        print(f"Replicates per response time: {self.n_reps}")
        print(f"Total jobs per config: {len(self.response_times) * self.n_reps}")
        print("=" * 60)

        results = {}
        for config in self.configs:
            results[config] = self.submit_jobs_for_config(config, dry_run=dry_run)

        return results

    def monitor_all_configs(self) -> dict[str, dict[str, int]]:
        """Monitor job status for all configurations."""
        print("\n📊 Job Status by Configuration:")
        print("=" * 60)

        all_status = {}
        for config in self.configs:
            config_name = config.replace(".yaml", "")
            status = self.get_job_status_for_config(config_name)
            all_status[config] = status

            if status:
                print(f"\n{config}:")
                for status_type, count in status.items():
                    print(f"  {status_type}: {count}")
            else:
                print(f"\n{config}: No jobs found")

        return all_status

    def check_completion(self) -> dict[str, bool]:
        """Check which configs have all jobs completed."""
        completion_status = {}

        for config in self.configs:
            status = self.get_job_status_for_config(config.replace(".yaml", ""))

            # Config is complete if all jobs are in "Complete" status
            total_jobs = sum(status.values())
            completed_jobs = status.get("Complete", 0)

            completion_status[config] = total_jobs > 0 and completed_jobs == total_jobs

        return completion_status

    def cleanup_completed_configs(self, dry_run: bool = False) -> dict[str, int]:
        """Clean up jobs for completed configurations."""
        cleanup_results = {}

        for config in self.configs:
            config_name = config.replace(".yaml", "")

            # Get all jobs for this config
            cmd = [
                "kubectl",
                "get",
                "jobs",
                "-l",
                f"{self.job_label},config={config_name}",
                "--no-headers",
                "-o",
                "custom-columns=NAME:.metadata.name",
            ]

            success, stdout, stderr = self.run_kubectl(cmd)
            if not success:
                cleanup_results[config] = 0
                continue

            job_names = [line.strip() for line in stdout.strip().split("\n") if line.strip()]

            if not job_names:
                cleanup_results[config] = 0
                continue

            if dry_run:
                print(f"[DRY RUN] Would delete {len(job_names)} jobs for {config}")
                cleanup_results[config] = len(job_names)
            else:
                # Delete jobs in batches
                batch_size = 50
                deleted = 0

                for i in range(0, len(job_names), batch_size):
                    batch = job_names[i : i + batch_size]
                    cmd = ["kubectl", "delete", "jobs", *batch]
                    success, stdout, stderr = self.run_kubectl(cmd)

                    if success:
                        deleted += len(batch)

                cleanup_results[config] = deleted
                print(f"Deleted {deleted} jobs for {config}")

        return cleanup_results


def main():
    parser = argparse.ArgumentParser(description="Submit and manage response-sia-sweep jobs for multiple configurations in parallel")

    # Config selection
    parser.add_argument("--configs", nargs="+", help="List of config files to run (e.g., config_nigeria.yaml config_zamfara.yaml)")
    parser.add_argument("--all-configs", action="store_true", help="Run all available configs in the configs directory")

    # Job parameters
    parser.add_argument("--response-times", nargs="+", type=int, help=f"Response times to test (default: {DEFAULT_RESPONSE_TIMES})")
    parser.add_argument("--n-reps", type=int, help=f"Number of replicates per response time (default: {DEFAULT_N_REPS})")

    # Actions
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without actually doing it")
    parser.add_argument("--monitor", action="store_true", help="Monitor status of running jobs")
    parser.add_argument("--cleanup", action="store_true", help="Clean up completed jobs")
    parser.add_argument("--watch", action="store_true", help="Continuously monitor jobs until all complete")

    args = parser.parse_args()

    # Determine which configs to run
    if args.all_configs:
        config_dir = Path("scripts/response_sia_sweep/configs")
        configs = [f.name for f in config_dir.glob("*.yaml")]
        print(f"Found {len(configs)} configs: {', '.join(configs)}")
    elif args.configs:
        configs = args.configs
    else:
        print("Error: Must specify --configs or --all-configs")
        return 1

    # Create manager
    manager = MultiConfigJobManager(configs=configs, response_times=args.response_times, n_reps=args.n_reps)

    # Execute requested action
    if args.monitor:
        manager.monitor_all_configs()
    elif args.cleanup:
        cleanup_results = manager.cleanup_completed_configs(dry_run=args.dry_run)
        print("\n🧹 Cleanup summary:")
        for config, count in cleanup_results.items():
            print(f"  {config}: {count} jobs")
    elif args.watch:
        print("👀 Watching jobs until all complete (press Ctrl+C to stop)...")

        try:
            while True:
                # Clear screen for clean display
                print("\033[2J\033[H")  # ANSI escape codes to clear screen

                # Show current status
                print(f"⏰ {datetime.now(tz=UTC).strftime('%Y-%m-%d %H:%M:%S')}")
                all_status = manager.monitor_all_configs()

                # Check completion
                completion = manager.check_completion()

                print("\n📈 Completion Status:")
                all_complete = True
                for config, is_complete in completion.items():
                    status = "✅ Complete" if is_complete else "⏳ Running"
                    print(f"  {config}: {status}")
                    if not is_complete:
                        all_complete = False

                if all_complete:
                    print("\n🎉 All configurations complete!")
                    break

                # Wait before next check
                time.sleep(30)

        except KeyboardInterrupt:
            print("\n\n👋 Monitoring stopped by user")
    else:
        # Submit jobs
        results = manager.submit_all_configs(dry_run=args.dry_run)

        # Print summary
        print("\n" + "=" * 60)
        print("📊 Submission Summary:")

        total_submitted = 0
        total_failed = 0
        total_skipped = 0

        for config, stats in results.items():
            print(f"\n{config}:")
            print(f"  Submitted: {stats['submitted']}")
            print(f"  Failed: {stats['failed']}")
            print(f"  Skipped: {stats['skipped']}")

            total_submitted += stats["submitted"]
            total_failed += stats["failed"]
            total_skipped += stats["skipped"]

        print("\nTotal across all configs:")
        print(f"  Submitted: {total_submitted}")
        print(f"  Failed: {total_failed}")
        print(f"  Skipped: {total_skipped}")

        if not args.dry_run and total_submitted > 0:
            print("\n🔍 Monitor with:")
            print(f"  python scripts/response_sia_sweep/core/multi_config_submit.py --configs {' '.join(configs)} --monitor")
            print(f"  python scripts/response_sia_sweep/core/multi_config_submit.py --configs {' '.join(configs)} --watch")

    return 0


if __name__ == "__main__":
    exit(main())
