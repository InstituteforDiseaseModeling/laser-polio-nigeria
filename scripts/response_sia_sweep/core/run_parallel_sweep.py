"""
Orchestrator script for running multiple configurations in parallel.

This script coordinates the entire workflow:
1. Submit jobs for multiple configs
2. Monitor their progress
3. Download results as they complete
4. Compile and plot results
5. Clean up completed jobs
"""

import argparse
import subprocess
from datetime import UTC
from datetime import datetime
from pathlib import Path

import yaml


class ParallelSweepOrchestrator:
    """Orchestrates parallel execution of multiple configuration sweeps."""

    def __init__(self, configs: list[str], response_times: list[int] = None, n_reps: int = None):
        """
        Initialize the orchestrator.

        Args:
            configs: List of configuration files to run
            response_times: Response times to test
            n_reps: Number of replicates per response time
        """
        self.configs = configs
        self.response_times = response_times
        self.n_reps = n_reps

        # Script paths
        self.SCRIPTS_DIR = Path("scripts/response_sia_sweep/core")
        self.submit_script = self.SCRIPTS_DIR / "multi_config_submit.py"
        self.download_script = self.SCRIPTS_DIR / "multi_config_download.py"

    def run_command(self, cmd: list[str], description: str = "") -> bool:
        """Run a command and return success status."""
        if description:
            print(f"\n{description}")

        print(f"  Command: {' '.join(cmd)}")

        try:
            result = subprocess.run(cmd, capture_output=False, text=True)
            return result.returncode == 0
        except Exception as e:
            print(f"  ❌ Error: {e}")
            return False

    def submit_jobs(self, dry_run: bool = False) -> bool:
        """Submit jobs for all configurations."""
        cmd = ["python", str(self.submit_script), "--configs"] + self.configs

        if self.response_times:
            cmd.extend(["--response-times"] + [str(rt) for rt in self.response_times])

        if self.n_reps:
            cmd.extend(["--n-reps", str(self.n_reps)])

        if dry_run:
            cmd.append("--dry-run")

        return self.run_command(cmd, "🚀 Submitting jobs for all configurations...")

    def monitor_jobs(self, watch: bool = False) -> bool:
        """Monitor job status."""
        cmd = ["python", str(self.submit_script), "--configs"] + self.configs

        if watch:
            cmd.append("--watch")
        else:
            cmd.append("--monitor")

        return self.run_command(cmd, "📊 Monitoring job status...")

    def download_results(self, monitor: bool = False, force: bool = False) -> bool:
        """Download results for all configurations."""
        cmd = ["python", str(self.download_script), "--configs"] + self.configs

        if monitor:
            cmd.append("--monitor")
            cmd.extend(["--interval", "60"])  # Check every minute
            cmd.extend(["--max-duration", "7200"])  # Monitor for up to 2 hours

        if force:
            cmd.append("--force")

        return self.run_command(cmd, "📥 Downloading results...")

    def compile_results(self) -> bool:
        """Compile and plot results for all configurations."""
        cmd = ["python", str(self.download_script), "--configs"] + self.configs
        cmd.append("--compile")

        return self.run_command(cmd, "📊 Compiling and plotting results...")

    def cleanup_jobs(self) -> bool:
        """Clean up completed jobs."""
        cmd = ["python", str(self.submit_script), "--configs"] + self.configs
        cmd.append("--cleanup")

        return self.run_command(cmd, "🧹 Cleaning up completed jobs...")

    def run_full_workflow(self, dry_run: bool = False, skip_cleanup: bool = False) -> bool:
        """Run the complete workflow from submission to results."""
        print("=" * 70)
        print("🎯 PARALLEL SWEEP ORCHESTRATOR")
        print("=" * 70)
        print(f"Configurations: {', '.join(self.configs)}")
        if self.response_times:
            print(f"Response times: {self.response_times}")
        if self.n_reps:
            print(f"Replicates: {self.n_reps}")
        print(f"Started at: {datetime.now(tz=UTC).strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 70)

        # Step 1: Submit jobs
        if not self.submit_jobs(dry_run=dry_run):
            print("❌ Failed to submit jobs")
            return False

        if dry_run:
            print("\n✅ Dry run complete - no jobs were actually submitted")
            return True

        # Step 2: Monitor and download results
        print("\n" + "=" * 70)
        print("📡 MONITORING AND DOWNLOADING PHASE")
        print("=" * 70)
        print("Will monitor jobs and download results as they complete...")
        print("This may take a while depending on job complexity...")

        # Use the download script's monitor feature
        if not self.download_results(monitor=True):
            print("⚠️  Some results may not have been downloaded")

        # Step 3: Compile all results
        print("\n" + "=" * 70)
        print("📈 COMPILATION PHASE")
        print("=" * 70)

        if not self.compile_results():
            print("⚠️  Some results may not have been compiled")

        # Step 4: Clean up (optional)
        if not skip_cleanup:
            print("\n" + "=" * 70)
            print("🧹 CLEANUP PHASE")
            print("=" * 70)

            if not self.cleanup_jobs():
                print("⚠️  Some jobs may not have been cleaned up")

        # Final summary
        print("\n" + "=" * 70)
        print("✅ WORKFLOW COMPLETE")
        print("=" * 70)
        print(f"Finished at: {datetime.now(tz=UTC).strftime('%Y-%m-%d %H:%M:%S')}")

        # Show where results are
        print("\n📁 Results locations:")
        for config in self.configs:
            config_name = config.replace(".yaml", "")
            # Try to determine results path
            config_file = Path("scripts/response_sia_sweep/configs") / config
            if config_file.exists():
                with open(config_file) as f:
                    config_data = yaml.safe_load(f)
                results_path = config_data.get("results_path", f"results/{config_name}")
                print(f"  {config}: {results_path}/")

        return True


def main():
    parser = argparse.ArgumentParser(
        description="Orchestrate parallel execution of multiple configuration sweeps",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run specific configs with custom parameters
  python run_parallel_sweep.py --configs config_nigeria.yaml config_zamfara.yaml --response-times 30 60 90 --n-reps 50

  # Run all configs with defaults
  python run_parallel_sweep.py --all-configs

  # Dry run to see what would happen
  python run_parallel_sweep.py --configs config_nigeria.yaml --dry-run

  # Just monitor existing jobs
  python run_parallel_sweep.py --configs config_nigeria.yaml --monitor-only

  # Download and compile results only
  python run_parallel_sweep.py --configs config_nigeria.yaml --download-only
        """,
    )

    # Config selection
    parser.add_argument("--configs", nargs="+", help="List of config files to run")
    parser.add_argument("--all-configs", action="store_true", help="Run all available configs")

    # Parameters
    parser.add_argument("--response-times", nargs="+", type=int, help="Response times to test")
    parser.add_argument("--n-reps", type=int, help="Number of replicates per response time")

    # Workflow control
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without actually doing it")
    parser.add_argument("--skip-cleanup", action="store_true", help="Skip cleanup of completed jobs")
    parser.add_argument("--monitor-only", action="store_true", help="Only monitor existing jobs (don't submit new ones)")
    parser.add_argument("--download-only", action="store_true", help="Only download and compile results (don't submit jobs)")

    args = parser.parse_args()

    # Determine configs
    if args.all_configs:
        config_dir = Path("scripts/response_sia_sweep/configs")
        configs = [f.name for f in config_dir.glob("*.yaml")]
        print(f"Found {len(configs)} configs")
    elif args.configs:
        configs = args.configs
    else:
        print("Error: Must specify --configs or --all-configs")
        return 1

    # Create orchestrator
    orchestrator = ParallelSweepOrchestrator(configs=configs, response_times=args.response_times, n_reps=args.n_reps)

    # Execute requested workflow
    if args.monitor_only:
        # Just monitor
        orchestrator.monitor_jobs(watch=True)
    elif args.download_only:
        # Download and compile
        orchestrator.download_results(monitor=False)
        orchestrator.compile_results()
    else:
        # Full workflow
        success = orchestrator.run_full_workflow(dry_run=args.dry_run, skip_cleanup=args.skip_cleanup)
        return 0 if success else 1

    return 0


if __name__ == "__main__":
    exit(main())
