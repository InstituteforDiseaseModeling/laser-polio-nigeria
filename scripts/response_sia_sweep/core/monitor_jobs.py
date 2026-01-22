#!/usr/bin/env python3
"""
Real-time monitoring for response-sia-sweep jobs.

This script provides comprehensive monitoring of the job sweep with automatic
cleanup suggestions and resource usage tracking.
"""

import argparse
import json
import subprocess
import time
from datetime import UTC
from datetime import datetime
from datetime import timedelta


class JobMonitor:
    """Monitors response-sia-sweep jobs and provides insights."""

    def __init__(self):
        self.job_label = "component=response-sia-sweep"

    def run_kubectl(self, cmd: list[str]) -> tuple[bool, str, str]:
        """Run kubectl command and return success status, stdout, stderr."""
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            return result.returncode == 0, result.stdout, result.stderr
        except Exception as e:
            return False, "", str(e)

    def get_job_details(self) -> dict:
        """Get detailed job information."""
        cmd = ["kubectl", "get", "jobs", "-l", self.job_label, "--no-headers", "-o", "json"]

        success, stdout, stderr = self.run_kubectl(cmd)
        if not success:
            return {"error": stderr, "jobs": []}

        try:
            data = json.loads(stdout)
            return {"jobs": data.get("items", []), "error": None}
        except json.JSONDecodeError:
            return {"error": "Failed to parse job data", "jobs": []}

    def get_pod_resource_usage(self) -> dict:
        """Get resource usage for running pods."""
        cmd = ["kubectl", "top", "pods", "-l", self.job_label, "--no-headers", "--sum"]

        success, stdout, stderr = self.run_kubectl(cmd)
        if not success:
            return {"error": stderr, "total_cpu": 0, "total_memory": 0}

        total_cpu = 0
        total_memory = 0

        for line in stdout.strip().split("\n"):
            if line.strip() and not line.startswith("SUM"):
                continue
            if line.startswith("SUM"):
                # Parse SUM line: "SUM  1200m  4800Mi"
                parts = line.split()
                if len(parts) >= 3:
                    try:
                        cpu_str = parts[1]  # "1200m"
                        memory_str = parts[2]  # "4800Mi"

                        # Parse CPU (millicores)
                        if cpu_str.endswith("m"):
                            total_cpu = int(cpu_str[:-1])
                        else:
                            total_cpu = int(cpu_str) * 1000

                        # Parse Memory (Mi/Gi)
                        if memory_str.endswith("Mi"):
                            total_memory = int(memory_str[:-2])
                        elif memory_str.endswith("Gi"):
                            total_memory = int(memory_str[:-2]) * 1024
                    except ValueError:
                        pass

        return {"total_cpu": total_cpu, "total_memory": total_memory, "error": None}

    def analyze_jobs(self) -> dict:
        """Analyze job status and provide insights."""
        job_data = self.get_job_details()
        if job_data["error"]:
            return {"error": job_data["error"]}

        jobs = job_data["jobs"]

        analysis = {
            "total_jobs": len(jobs),
            "by_status": {},
            "by_response_time": {},
            "completion_times": [],
            "failed_jobs": [],
            "old_completed_jobs": [],
            "resource_summary": {},
            "estimated_completion": None,
        }

        now = datetime.now(UTC)
        cutoff_time = now - timedelta(hours=1)  # Jobs completed > 1 hour ago

        for job in jobs:
            job_name = job["metadata"]["name"]

            # Extract response time from job name
            rt_part = job_name.split("-")[2]  # "rt15", "rt30", etc.
            response_time = int(rt_part[2:])

            # Analyze status
            conditions = job.get("status", {}).get("conditions", [])
            job_status = "Unknown"
            completion_time = None

            for condition in conditions:
                if condition.get("status") == "True":
                    if condition.get("type") == "Complete":
                        job_status = "Complete"
                        completion_time = condition.get("lastTransitionTime")
                    elif condition.get("type") == "Failed":
                        job_status = "Failed"
                        analysis["failed_jobs"].append(job_name)

            # Check for running jobs (no completion conditions)
            if job_status == "Unknown":
                active_jobs = job.get("status", {}).get("active", 0)
                if active_jobs > 0:
                    job_status = "Running"
                else:
                    job_status = "Pending"

            # Update counts
            analysis["by_status"][job_status] = analysis["by_status"].get(job_status, 0) + 1
            analysis["by_response_time"][response_time] = analysis["by_response_time"].get(response_time, 0) + 1

            # Track completion times
            if completion_time:
                try:
                    completion_dt = datetime.fromisoformat(completion_time.replace("Z", "+00:00"))
                    analysis["completion_times"].append(completion_dt)

                    # Check if job is old and completed
                    if completion_dt < cutoff_time:
                        analysis["old_completed_jobs"].append(job_name)
                except ValueError:
                    pass

        # Calculate estimated completion
        if analysis["completion_times"] and analysis["by_status"].get("Running", 0) > 0:
            avg_duration = sum((now - ct).total_seconds() / 60 for ct in analysis["completion_times"]) / len(analysis["completion_times"])

            analysis["estimated_completion"] = now + timedelta(minutes=avg_duration)

        # Add resource usage
        resource_usage = self.get_pod_resource_usage()
        if not resource_usage.get("error"):
            analysis["resource_summary"] = {
                "cpu_cores": resource_usage["total_cpu"] / 1000,
                "memory_gb": resource_usage["total_memory"] / 1024,
                "cpu_millicores": resource_usage["total_cpu"],
                "memory_mb": resource_usage["total_memory"],
            }

        return analysis

    def print_status_report(self, analysis: dict, detailed: bool = False):
        """Print a formatted status report."""
        print("Response SIA Sweep - Job Status Report")
        print("=" * 50)
        print(f"🕒 Report time: {datetime.now(UTC).strftime('%Y-%m-%d %H:%M:%S')}")

        if analysis.get("error"):
            print(f"❌ Error: {analysis['error']}")
            return

        total = analysis["total_jobs"]
        print(f"📊 Total jobs: {total}")

        # Status breakdown
        print("\n📈 Job Status:")
        for status, count in sorted(analysis["by_status"].items()):
            percentage = (count / total * 100) if total > 0 else 0
            emoji = {"Complete": "✅", "Running": "🔄", "Failed": "❌", "Pending": "⏳"}.get(status, "❓")
            print(f"  {emoji} {status}: {count} ({percentage:.1f}%)")

        # Response time breakdown
        if detailed:
            print("\n🎯 By Response Time:")
            for rt in sorted(analysis["by_response_time"].keys()):
                count = analysis["by_response_time"][rt]
                print(f"  RT{rt}: {count} jobs")

        # Resource usage
        if analysis["resource_summary"]:
            res = analysis["resource_summary"]
            print("\n💻 Current Resource Usage:")
            print(f"  CPU: {res['cpu_cores']:.1f} cores ({res['cpu_millicores']}m)")
            print(f"  Memory: {res['memory_gb']:.1f} GB ({res['memory_mb']} MB)")

        # Failed jobs
        if analysis["failed_jobs"]:
            print(f"\n❌ Failed Jobs ({len(analysis['failed_jobs'])}):")
            for job in analysis["failed_jobs"][:5]:
                print(f"  - {job}")
            if len(analysis["failed_jobs"]) > 5:
                print(f"  ... and {len(analysis['failed_jobs']) - 5} more")

        # Cleanup suggestions
        old_jobs = len(analysis["old_completed_jobs"])
        if old_jobs > 0:
            print("\n🧹 Cleanup Suggestion:")
            print(f"  {old_jobs} jobs completed >1h ago can be cleaned up")
            print("  Run: python3 scripts/response_sia_sweep/core/cleanup_completed_jobs.py")

        # Estimated completion
        if analysis["estimated_completion"]:
            eta = analysis["estimated_completion"]
            print(f"\n⏰ Estimated completion: {eta.strftime('%Y-%m-%d %H:%M:%S')}")

        print("\n" + "=" * 50)

    def monitor_continuous(self, interval_seconds: int = 60):
        """Continuously monitor jobs."""
        print(f"🔄 Starting continuous monitoring (interval: {interval_seconds}s)")
        print("Press Ctrl+C to stop...")

        try:
            while True:
                analysis = self.analyze_jobs()

                # Clear screen
                subprocess.run(["clear"], check=False)

                self.print_status_report(analysis, detailed=True)

                time.sleep(interval_seconds)

        except KeyboardInterrupt:
            print("\n\n👋 Monitoring stopped.")


def main():
    parser = argparse.ArgumentParser(description="Monitor response-sia-sweep jobs")
    parser.add_argument("--detailed", action="store_true", help="Show detailed breakdown")
    parser.add_argument("--continuous", action="store_true", help="Monitor continuously")
    parser.add_argument("--interval", type=int, default=60, help="Update interval for continuous monitoring (seconds)")

    args = parser.parse_args()

    monitor = JobMonitor()

    if args.continuous:
        monitor.monitor_continuous(args.interval)
    else:
        analysis = monitor.analyze_jobs()
        monitor.print_status_report(analysis, detailed=args.detailed)

    return 0


if __name__ == "__main__":
    exit(main())
