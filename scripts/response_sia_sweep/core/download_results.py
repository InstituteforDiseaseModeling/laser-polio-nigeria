"""
Fixed download script that uses sleep-pod instead of jupyter-deployment
"""

import argparse
import shutil
import subprocess
from datetime import UTC
from datetime import datetime
from pathlib import Path

import yaml
from active_config import ACTIVE_CONFIG


def download_results(run_id: str | None = None, config_name: str | None = None, output_dir: str | None = None):
    """Download results for a specific run or config."""

    # Default to active config if not specified
    if config_name is None:
        config_name = ACTIVE_CONFIG

    # Always strip .yaml extension if present
    config_name = config_name.replace(".yaml", "")

    # Load config to get results_path
    config_file = f"scripts/response_sia_sweep/configs/{config_name}.yaml"
    if not Path(config_file).exists():
        config_file = f"scripts/response_sia_sweep/configs/{ACTIVE_CONFIG}"

    with open(config_file) as f:
        config = yaml.safe_load(f)
    results_path = config.get("results_path", f"results/{config_name}")

    # Get list of available runs if run_id not specified
    if run_id is None:
        print(f"Searching for runs under config: {config_name}")

        # List available runs using sleep-pod instead of jupyter-deployment
        list_cmd = f"kubectl exec sleep-pod -- ls /shared/results/{config_name}/"
        result = subprocess.run(list_cmd, shell=True, capture_output=True, text=True)

        if result.returncode != 0:
            print(f"No results found for config: {config_name}")
            return

        # Filter out "Defaulted container" message from stderr
        output_lines = result.stdout.strip().split("\n")
        runs = [r.strip() for r in output_lines if r.strip() and r.startswith("run_") and "Defaulted container" not in r]

        if not runs:
            print(f"No runs found for config: {config_name}")
            return

        print("\nAvailable runs:")
        for i, run in enumerate(runs, 1):
            print(f"  {i}. {run}")

        # Use the most recent run
        run_id = sorted(runs)[-1]
        print(f"\nUsing most recent run: {run_id}")

    # Set output directory to results_path (the downloaded data includes results_raw subdirectory)
    if output_dir is None:
        output_dir = results_path

    # Create local directory
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    # Download results using sleep-pod - copy the entire run directory
    remote_path = f"/shared/results/{config_name}/{run_id}/"

    # Download to a temp location first to preserve structure
    temp_dir = f"{output_dir}_temp_{run_id}"

    print(f"\nDownloading from: {remote_path}")
    print(f"Saving to: {output_dir}")

    # Use kubectl cp with sleep-pod
    copy_cmd = f"kubectl cp sleep-pod:{remote_path} {temp_dir}"

    print(f"\nExecuting: {copy_cmd}")
    result = subprocess.run(copy_cmd, shell=True)

    if result.returncode == 0:
        # Move files from temp directory to final location
        temp_path = Path(temp_dir)
        output_path = Path(output_dir)

        # Move results_raw directory if it exists
        temp_results_raw = temp_path / "results_raw"
        if temp_results_raw.exists():
            final_results_raw = output_path / "results_raw"
            if final_results_raw.exists():
                shutil.rmtree(final_results_raw)
            shutil.move(str(temp_results_raw), str(output_path))

        # Move errors directory if it exists (for debugging failed runs)
        temp_errors = temp_path / "errors"
        if temp_errors.exists():
            final_errors = output_path / "errors"
            if final_errors.exists():
                shutil.rmtree(final_errors)
            shutil.move(str(temp_errors), str(output_path))
            print("  ⚠️  Found error logs - jobs failed during execution")

        # Move metadata.json if it exists
        temp_metadata = temp_path / "metadata.json"
        if temp_metadata.exists():
            shutil.copy2(str(temp_metadata), str(output_path / "metadata.json"))

        # Clean up temp directory if it still exists
        if Path(temp_dir).exists():
            shutil.rmtree(temp_dir)

        # Count downloaded files
        result_files = list(Path(output_dir).rglob("*.csv"))
        metadata_files = list(Path(output_dir).rglob("metadata.json"))
        error_files = list(Path(output_dir).rglob("*.txt"))

        print("\n✅ Download complete!")
        print(f"  - Result files: {len(result_files)}")
        print(f"  - Error files: {len(error_files)}")
        print(f"  - Metadata files: {len(metadata_files)}")
        print(f"  - Saved to: {output_dir}")

        # Save download info
        download_info = Path(output_dir) / "download_info.txt"
        with open(download_info, "w") as f:
            f.write(f"Downloaded: {datetime.now(UTC).isoformat()}\n")
            f.write(f"Config: {config_name}\n")
            f.write(f"Run ID: {run_id}\n")
            f.write(f"Remote path: {remote_path}\n")
            f.write(f"Result files: {len(result_files)}\n")

        return output_dir
    else:
        print("❌ Download failed!")
        return None


def list_available_results():
    """List all available results on the cluster."""
    print("Searching for all available results...")

    cmd = "kubectl exec sleep-pod -- find /shared/results -name 'results_raw' -type d"
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)

    if result.returncode == 0:
        paths = [p.strip() for p in result.stdout.split("\n") if p.strip() and "Defaulted container" not in p]

        # Parse paths to extract config and run_id
        results = {}
        for path in paths:
            parts = path.split("/")
            if len(parts) >= 5:  # /shared/results/config_name/run_id/results_raw
                config = parts[3]
                run_id = parts[4]

                if config not in results:
                    results[config] = []
                results[config].append(run_id)

        if results:
            print("\nAvailable results:")
            for config, runs in sorted(results.items()):
                print(f"\n{config}:")
                for run in sorted(runs)[-5:]:  # Show last 5 runs
                    print(f"  - {run}")
        else:
            print("No results found")
    else:
        print("Failed to list results")


def cleanup_old_results(config_name: str | None = None, keep_latest: int = 3):
    """Clean up old result directories on the cluster."""
    if config_name is None:
        config_name = ACTIVE_CONFIG.replace(".yaml", "")

    print(f"Cleaning up old results for config: {config_name}")
    print(f"Keeping {keep_latest} most recent runs...")

    # List runs using sleep-pod
    list_cmd = f"kubectl exec sleep-pod -- ls -t /shared/results/{config_name}/"
    result = subprocess.run(list_cmd, shell=True, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"No results found for config: {config_name}")
        return

    runs = [r.strip() for r in result.stdout.split("\n") if r.strip() and r.startswith("run_") and "Defaulted container" not in r]

    if len(runs) <= keep_latest:
        print(f"Only {len(runs)} runs found, nothing to clean")
        return

    # Delete old runs
    runs_to_delete = sorted(runs)[:-keep_latest]

    print(f"\nWill delete {len(runs_to_delete)} old runs:")
    for run in runs_to_delete:
        print(f"  - {run}")

    confirm = input("\nProceed with cleanup? (yes/no): ")
    if confirm.lower() != "yes":
        print("Cleanup cancelled")
        return

    for run in runs_to_delete:
        rm_cmd = f"kubectl exec sleep-pod -- rm -rf /shared/results/{config_name}/{run}"
        subprocess.run(rm_cmd, shell=True)
        print(f"  ✓ Deleted {run}")

    print(f"\n✅ Cleanup complete! Deleted {len(runs_to_delete)} old runs")


def main():
    parser = argparse.ArgumentParser(description="Fixed result download using sleep-pod")
    parser.add_argument("--config", type=str, default=None, help="Config name (defaults to ACTIVE_CONFIG)")
    parser.add_argument("--run-id", type=str, default=None, help="Specific run ID to download (defaults to latest)")
    parser.add_argument("--output-dir", type=str, default=None, help="Local directory to save results")
    parser.add_argument("--list", action="store_true", help="List available results")
    parser.add_argument("--cleanup", action="store_true", help="Clean up old results")
    parser.add_argument("--keep-latest", type=int, default=3, help="Number of latest runs to keep during cleanup")

    args = parser.parse_args()

    if args.list:
        list_available_results()
    elif args.cleanup:
        cleanup_old_results(config_name=args.config, keep_latest=args.keep_latest)
    else:
        download_results(run_id=args.run_id, config_name=args.config, output_dir=args.output_dir)


if __name__ == "__main__":
    main()
