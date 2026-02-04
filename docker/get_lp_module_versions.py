import io
import os
import re
import tarfile

import docker
import requests
import sciris as sc


def get_latest_github_tag(repo):
    url = f"https://api.github.com/repos/{repo}/releases/latest"

    # Try to get GitHub token from environment

    headers = {}
    github_token = os.getenv("GITHUB_TOKEN")
    if github_token:
        headers["Authorization"] = f"token {github_token}"

    response = requests.get(url, headers=headers, timeout=10)
    if response.status_code == 200:
        latest = response.json()
        return latest["tag_name"].lstrip("v")  # Strip leading 'v'
    else:
        # If it fails, try getting tags instead of releases
        tags_url = f"https://api.github.com/repos/{repo}/tags"
        tags_response = requests.get(tags_url, headers=headers, timeout=10)
        if tags_response.status_code == 200:
            tags = tags_response.json()
            if tags:
                return tags[0]["name"].lstrip("v")
        raise RuntimeError(f"Failed to fetch release info: {response.status_code}, {response.text}")


def get_installed_version_from_image(image_name, container_path, package_name):
    client = docker.from_env()
    container = client.containers.create(image=image_name, name="temp_laser", command="sleep 10")

    try:
        tar_stream, stat = container.get_archive(container_path)
        file_like = io.BytesIO(b"".join(tar_stream))
        with tarfile.open(fileobj=file_like) as tar:
            member = tar.getmembers()[0]
            extracted_file = tar.extractfile(member)
            if extracted_file:
                content = extracted_file.read().decode("utf-8")
                match = re.search(rf"{package_name}==([\d\.]+)", content)
                if match:
                    return match.group(1)
                else:
                    raise ValueError(f"Package {package_name} not found in container file.")
            else:
                raise OSError("Failed to extract file from tar.")
    finally:
        container.remove(force=True)


def check_version_match(repo, image_name, container_path, package_name="laser_polio"):
    # print(f"🔍 Checking version for repo: {repo} and image: {image_name}")

    try:
        latest_tag = get_latest_github_tag(repo)
        # print(f"📦 Latest GitHub release: {latest_tag}")

        image_version = get_installed_version_from_image(image_name, container_path, package_name)
        # print(f"🐳 Docker image version: {image_version}")

        if latest_tag != image_version:
            # warning_msg = f"⚠️ Version mismatch: GitHub={latest_tag}, Docker={image_version}"
            # warnings.warn(warning_msg, stacklevel=2)
            sc.printred(f"⚠️ Warning: There is a laser_polio version mismatch: GitHub={latest_tag}, Docker={image_version}")
            sc.printred("Run build_and_push.py to update the Docker image to the latest version.")
        else:
            sc.printgreen(f"✅ Version match confirmed between GitHub and Docker: {latest_tag}")
    except RuntimeError as e:
        if "404" in str(e):
            sc.printyellow("⚠️ Skipping version check - repository is private and no GitHub token provided")
            sc.printyellow("Set GITHUB_TOKEN environment variable to enable version checking")
        else:
            raise


# Example usage:
if __name__ == "__main__":
    check_version_match(
        repo="InstituteforDiseaseModeling/laser-polio",
        image_name="idm-docker-staging.packages.idmod.org/laser/laser-polio:latest",
        container_path="/app/laser_polio_deps.txt",
    )
