import argparse
import subprocess
import sys
import time
from pathlib import Path

import sciris as sc
from active_config import DOCKER_IMAGE_TAG
from active_config import LASER_POLIO_VERSION

sys.path.append(str(Path(__file__).resolve().parent.parent / "utils"))
from get_lp_module_versions import check_version_match


def run_docker_commands(image_tag, dockerfile, laser_polio_version="latest"):
    platform = "linux/amd64"  # Required for AKS

    # Timestamp-based cache breaker
    cache_breaker = str(int(time.time()))

    # Docker commands
    build_cmd = [
        "docker",
        "build",
        ".",
        "-f",
        dockerfile,
        "-t",
        image_tag,
        "--platform",
        platform,
        "--build-arg",
        f"CACHE_BREAKER={cache_breaker}",
        "--build-arg",
        f"LASER_POLIO_VERSION={laser_polio_version}",
    ]

    create_cmd = ["docker", "create", "--name", "temp_laser", image_tag]
    cp_cmd = ["docker", "cp", "temp_laser:/app/laser_polio_deps.txt", "./laser_polio_deps.txt"]
    rm_cmd = ["docker", "rm", "temp_laser"]
    push_cmd = ["docker", "push", image_tag]

    try:
        # Docker running check
        subprocess.run(["docker", "info"], check=True, capture_output=True)

        # Build
        subprocess.run(build_cmd, check=True)
        print("🛠️ Docker image built successfully.")

        # Extract dependency list
        subprocess.run(create_cmd, check=True)
        subprocess.run(cp_cmd, check=True)
        subprocess.run(rm_cmd, check=True)
        print("📄 Extracted 'laser_polio_deps.txt' from the image.")

        # Show matches
        try:
            with open("laser_polio_deps.txt") as f:
                print("\n🔍 Dependencies containing 'laser':")
                for line_num, line in enumerate(f, 1):
                    if "laser" in line.lower():
                        print(f"{line_num}: {line.strip()}")
        except Exception as e:
            print(f"Error reading laser_polio_deps.txt: {e}")

        # Push
        subprocess.run(push_cmd, check=True)
        sc.printgreen("✅ Docker image pushed successfully.")

    except subprocess.CalledProcessError as e:
        sc.printred(f"❌ Docker command failed: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build and push Docker image for response SIA sweep.")
    parser.add_argument(
        "--tag", default=f"idm-docker-staging.packages.idmod.org/laser/response-sia-sweep:{DOCKER_IMAGE_TAG}", help="Full image tag to use"
    )
    parser.add_argument("--dockerfile", default="scripts/response_sia_sweep/docker/Dockerfile", help="Path to Dockerfile")
    parser.add_argument(
        "--laser-polio-version", default=LASER_POLIO_VERSION, help="Laser-polio version to install (default from active_config)"
    )
    args = parser.parse_args()

    print(f"🚀 Building image: {args.tag}")
    print(f"📁 Using Dockerfile: {args.dockerfile}")
    print(f"📦 Installing laser-polio: {args.laser_polio_version}")

    run_docker_commands(image_tag=args.tag, dockerfile=args.dockerfile, laser_polio_version=args.laser_polio_version)

    print("🔎 Checking version of laser_polio inside image...")
    check_version_match(
        repo="InstituteforDiseaseModeling/laser-polio",
        image_name=args.tag,
        container_path="/app/laser_polio_deps.txt",
    )
