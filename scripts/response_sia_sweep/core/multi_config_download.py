"""
Download results for multiple configurations.

This script handles downloading and organizing results from multiple
configuration runs, including partial downloads as jobs complete.
"""

import argparse
import os
import subprocess
import sys
import time
from datetime import UTC
from datetime import datetime
from pathlib import Path

import yaml


class MultiConfigDownloader:
    """Manages downloading results for multiple configurations."""

    def __init__(self, configs: list[str]):
        """
        Initialize downloader for multiple configs.

        Args:
            configs: List of config file names to download results for
        """
        self.configs = configs
        self.CONFIG_DIR = Path("scripts/response_sia_sweep/configs")

    def run_kubectl(self, cmd: list[str]) -> tuple[bool, str, str]:
        """Run kubectl command and return success status, stdout, stderr."""
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            return result.returncode == 0, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return False, "", "Command timed out"
        except Exception as e:
            return False, "", str(e)

    def get_available_runs(self, config_name: str) -> list[str]:
        """Get list of available runs for a config on the cluster."""
        # List available runs using sleep-pod
        list_cmd = f"kubectl exec sleep-pod -- ls /shared/results/{config_name}/"
        result = subprocess.run(list_cmd, shell=True, capture_output=True, text=True)

        if result.returncode != 0:
            return []

        # Filter out "Defaulted container" message
        output_lines = result.stdout.strip().split("\n")
        runs = [r.strip() for r in output_lines if r.strip() and r.startswith("run_") and "Defaulted container" not in r]

        return sorted(runs)

    def check_run_completeness(self, config_name: str, run_id: str) -> dict[str, int]:
        """Check how many results are available for a run."""
        # Check for results_raw directory
        check_cmd = f"kubectl exec sleep-pod -- ls /shared/results/{config_name}/{run_id}/"
        result = subprocess.run(check_cmd, shell=True, capture_output=True, text=True)

        if result.returncode != 0:
            return {"results": 0, "errors": 0}

        output = result.stdout.strip()

        stats = {"results": 0, "errors": 0}

        # Check for results
        if "results_raw" in output:
            count_cmd = f"kubectl exec sleep-pod -- ls /shared/results/{config_name}/{run_id}/results_raw/ | wc -l"
            result = subprocess.run(count_cmd, shell=True, capture_output=True, text=True)
            if result.returncode == 0:
                try:
                    # Extract number, filtering out any "Defaulted container" messages
                    count_str = result.stdout.strip().split("\n")[0]
                    stats["results"] = int(count_str)
                except (ValueError, IndexError):
                    pass

        # Check for errors
        if "errors" in output:
            count_cmd = f"kubectl exec sleep-pod -- ls /shared/results/{config_name}/{run_id}/errors/ | wc -l"
            result = subprocess.run(count_cmd, shell=True, capture_output=True, text=True)
            if result.returncode == 0:
                try:
                    count_str = result.stdout.strip().split("\n")[0]
                    stats["errors"] = int(count_str)
                except (ValueError, IndexError):
                    pass

        return stats

    def download_config_results(self, config: str, run_id: str | None = None, force: bool = False) -> bool:
        """
        Download results for a specific config.

        Args:
            config: Config file name
            run_id: Specific run ID to download (latest if None)
            force: Force re-download even if local files exist

        Returns:
            True if download successful, False otherwise
        """
        config_name = config.replace(".yaml", "")

        # Get available runs if not specified
        if run_id is None:
            runs = self.get_available_runs(config_name)
            if not runs:
                print(f"  ❌ No runs found for {config}")
                return False
            run_id = runs[-1]  # Use most recent

        # Load config to get results_path
        config_file = self.CONFIG_DIR / config
        if not config_file.exists():
            print(f"  ❌ Config file not found: {config_file}")
            return False

        with open(config_file) as f:
            config_data = yaml.safe_load(f)
        results_path = config_data.get("results_path", f"results/{config_name}")

        # Check if already downloaded
        local_path = Path(results_path)
        if local_path.exists() and not force:
            # Check if we have results
            local_results = list((local_path / "results_raw").glob("*.csv")) if (local_path / "results_raw").exists() else []
            if local_results:
                print(f"  ⏭️  Skipping {config} - {len(local_results)} results already downloaded")
                return True

        # Check completeness on cluster
        stats = self.check_run_completeness(config_name, run_id)
        print(f"  📊 {config} ({run_id}): {stats['results']} results, {stats['errors']} errors")

        if stats["results"] == 0 and stats["errors"] == 0:
            print(f"  ⚠️  No data available yet for {config}")
            return False

        # Use the download_results script with the current Python interpreter

        cmd = [
            sys.executable,  # Use the same Python interpreter that's running this script
            "scripts/response_sia_sweep/core/download_results.py",
            "--config",
            config,
            "--run-id",
            run_id,
        ]

        print(f"  ⬇️  Downloading {config}...")
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode == 0:
            print(f"  ✅ Downloaded {config} to {results_path}")
            return True
        else:
            print(f"  ❌ Failed to download {config}: {result.stderr}")
            return False

    def download_all_configs(self, force: bool = False) -> dict[str, bool]:
        """Download results for all configurations."""
        print(f"\n📥 Downloading results for {len(self.configs)} configurations")
        print("=" * 60)

        results = {}
        for config in self.configs:
            print(f"\n{config}:")
            success = self.download_config_results(config, force=force)
            results[config] = success

        return results

    def monitor_and_download(self, interval: int = 60, max_duration: int = 3600) -> dict[str, bool]:
        """
        Monitor running jobs and download results as they complete.

        Args:
            interval: Seconds between checks
            max_duration: Maximum seconds to monitor before stopping

        Returns:
            Dictionary of config -> download success status
        """
        print(f"👀 Monitoring and downloading results every {interval} seconds")
        print(f"   Will stop after {max_duration / 60:.0f} minutes")
        print("   Press Ctrl+C to stop early")

        start_time = time.time()
        download_status = dict.fromkeys(self.configs, False)

        try:
            while time.time() - start_time < max_duration:
                print(f"\n⏰ Check at {datetime.now(tz=UTC).strftime('%H:%M:%S')}")

                any_new = False
                for config in self.configs:
                    if not download_status[config]:
                        # Try to download
                        success = self.download_config_results(config)
                        if success:
                            download_status[config] = True
                            any_new = True

                # Check if all downloaded
                if all(download_status.values()):
                    print("\n🎉 All configurations downloaded successfully!")
                    break

                # Show status
                print("\n📈 Download Status:")
                for config, downloaded in download_status.items():
                    status = "✅" if downloaded else "⏳"
                    print(f"  {status} {config}")

                if not any_new:
                    print(f"\n💤 No new results. Waiting {interval} seconds...")
                    time.sleep(interval)
                else:
                    print("\n✨ New results downloaded!")

        except KeyboardInterrupt:
            print("\n\n👋 Monitoring stopped by user")

        return download_status

    def compile_all_results(self) -> dict[str, bool]:
        """Compile and plot results for all downloaded configurations."""
        print("\n📊 Compiling results for all configurations")
        print("=" * 60)

        compile_status = {}

        for config in self.configs:
            config_name = config.replace(".yaml", "")

            # Load config to get results_path
            config_file = self.CONFIG_DIR / config
            if not config_file.exists():
                compile_status[config] = False
                continue

            with open(config_file) as f:
                config_data = yaml.safe_load(f)
            results_path = config_data.get("results_path", f"results/{config_name}")

            # Check if results exist
            results_dir = Path(results_path) / "results_raw"
            if not results_dir.exists():
                print(f"  ⏭️  Skipping {config} - no results found")
                compile_status[config] = False
                continue

            csv_files = list(results_dir.glob("*.csv"))
            if not csv_files:
                print(f"  ⏭️  Skipping {config} - no CSV files found")
                compile_status[config] = False
                continue

            print(f"  📈 Compiling {config} ({len(csv_files)} files)...")

            # Run compile script with this config
            cmd = ["python", "scripts/response_sia_sweep/core/compile_and_plot_results.py"]

            # Temporarily set active config

            old_config = os.environ.get("ACTIVE_CONFIG")
            os.environ["ACTIVE_CONFIG"] = config

            result = subprocess.run(cmd, capture_output=True, text=True)

            # Restore old config
            if old_config:
                os.environ["ACTIVE_CONFIG"] = old_config
            else:
                os.environ.pop("ACTIVE_CONFIG", None)

            if result.returncode == 0:
                print(f"  ✅ Compiled and plotted {config}")
                compile_status[config] = True
            else:
                print(f"  ❌ Failed to compile {config}: {result.stderr}")
                compile_status[config] = False

        return compile_status


def main():
    parser = argparse.ArgumentParser(description="Download and manage results for multiple configurations")

    # Config selection
    parser.add_argument("--configs", nargs="+", help="List of config files to download results for")
    parser.add_argument("--all-configs", action="store_true", help="Download results for all available configs")

    # Actions
    parser.add_argument("--force", action="store_true", help="Force re-download even if local results exist")
    parser.add_argument("--monitor", action="store_true", help="Monitor and download results as jobs complete")
    parser.add_argument("--compile", action="store_true", help="Compile and plot results after downloading")
    parser.add_argument("--interval", type=int, default=60, help="Seconds between checks when monitoring (default: 60)")
    parser.add_argument("--max-duration", type=int, default=3600, help="Maximum seconds to monitor (default: 3600 = 1 hour)")

    args = parser.parse_args()

    # Determine which configs
    if args.all_configs:
        config_dir = Path("scripts/response_sia_sweep/configs")
        configs = [f.name for f in config_dir.glob("*.yaml")]
        print(f"Found {len(configs)} configs: {', '.join(configs)}")
    elif args.configs:
        configs = args.configs
    else:
        print("Error: Must specify --configs or --all-configs")
        return 1

    # Create downloader
    downloader = MultiConfigDownloader(configs)

    # Execute requested action
    if args.monitor:
        download_status = downloader.monitor_and_download(interval=args.interval, max_duration=args.max_duration)

        # Show final summary
        print("\n📊 Final Download Summary:")
        for config, success in download_status.items():
            status = "✅" if success else "❌"
            print(f"  {status} {config}")

        # Optionally compile results
        if args.compile:
            compile_status = downloader.compile_all_results()
            print("\n📈 Compilation Summary:")
            for config, success in compile_status.items():
                status = "✅" if success else "❌"
                print(f"  {status} {config}")

    else:
        # Direct download
        download_status = downloader.download_all_configs(force=args.force)

        # Show summary
        print("\n📊 Download Summary:")
        success_count = sum(1 for s in download_status.values() if s)
        fail_count = len(download_status) - success_count

        for config, success in download_status.items():
            status = "✅" if success else "❌"
            print(f"  {status} {config}")

        print(f"\nTotal: {success_count} succeeded, {fail_count} failed")

        # Optionally compile results
        if args.compile:
            compile_status = downloader.compile_all_results()
            print("\n📈 Compilation Summary:")
            for config, success in compile_status.items():
                status = "✅" if success else "❌"
                print(f"  {status} {config}")

    return 0


if __name__ == "__main__":
    exit(main())
