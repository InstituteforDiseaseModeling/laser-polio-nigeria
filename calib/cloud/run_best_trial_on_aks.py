#!/usr/bin/env python3
"""
Deploy best trial analysis job to AKS cluster.
This script creates a Kubernetes job that runs the best trial worker.
"""

import sys
from pathlib import Path

import cloud_calib_config as cfg
import runtime_wrapper as wrapper
import sciris as sc
from kubernetes import client
from kubernetes import config

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).resolve().parent.parent))
from get_lp_module_versions import check_version_match


def create_best_trial_job():
    """Create and deploy the best trial analysis job to AKS."""

    print("🔍 Checking Docker image version compatibility...")
    # Compare the version of laser_polio in the Docker image with the version in the GitHub repository
    check_version_match(
        repo="InstituteforDiseaseModeling/laser-polio",
        image_name="idm-docker-staging.packages.idmod.org/laser/laser-polio:latest",
        container_path="/app/laser_polio_deps.txt",
    )

    # Constants for Kubernetes configuration
    PERSISTENT_VOLUME_CLAIM_NAME = "laser-stg-pvc"
    SHARED_DIR = "/shared"
    USE_WRAPPER = False  # Disable wrapper for consistent best trial storage
    WRAP_BINARY_DIR = str(Path(SHARED_DIR) / "simulation" / "bin")

    print("🔧 Loading Kubernetes configuration...")
    # Load kubeconfig
    config.load_kube_config(config_file="~/.kube/config")
    batch_v1 = client.BatchV1Api()

    # Create unique job name for best trial
    best_trial_job_name = f"{cfg.job_name}-best-trial"

    print(f"🚀 Creating best trial analysis job: {best_trial_job_name}")
    print(f"   Study: {cfg.study_name}")
    print(f"   Model config: {cfg.model_config}")

    # Build cluster-internal storage URL
    # Replace localhost:3307 with cluster service mysql:3306
    cluster_storage_url = cfg.storage_url.replace("localhost:3307", "mysql:3306")

    # Define the container command - save directly to shared storage with consistent path
    results_path = f"/shared/results/{cfg.study_name}/best_trial"
    command = [
        "bash",
        "-c",
        f"python3 calib/best_trial_worker.py --study-name {cfg.study_name} --storage-url {cluster_storage_url} --model-config {cfg.model_config} --results-path {results_path} --verbose 0",
    ]

    # Wrap the command if needed
    wrapped_command = wrapper.wrap_command(
        command,
        shared_bin_dir=WRAP_BINARY_DIR,
        dont_wrap=not USE_WRAPPER,
    )

    # Define the container
    container = client.V1Container(
        name=best_trial_job_name,
        image=cfg.image,
        image_pull_policy="Always",
        command=wrapped_command,
        env_from=[client.V1EnvFromSource(secret_ref=client.V1SecretEnvSource(name="mysql-secrets"))],
        # Use higher memory for best trial analysis (includes plotting)
        resources=client.V1ResourceRequirements(requests={"memory": "32Gi", "cpu": "4"}, limits={"memory": "64Gi", "cpu": "8"}),
        volume_mounts=[client.V1VolumeMount(name="shared-data", mount_path=SHARED_DIR)],
        env=[
            client.V1EnvVar(name="PYTHONUNBUFFERED", value="1"),
            client.V1EnvVar(name="JOB_NAME", value=best_trial_job_name),
            client.V1EnvVar(name="STUDY_NAME", value=cfg.study_name),
            client.V1EnvVar(
                name="POD_NAME", value_from=client.V1EnvVarSource(field_ref=client.V1ObjectFieldSelector(field_path="metadata.name"))
            ),
        ],
    )

    # Pod template spec
    template = client.V1PodTemplateSpec(
        spec=client.V1PodSpec(
            containers=[container],
            restart_policy="Never",  # Don't restart on failure for best trial
            image_pull_secrets=[client.V1LocalObjectReference(name="idmodregcred3")],
            # Use 128gb node pool for best trial analysis (memory intensive)
            node_selector={"nodepool": "128gb"},
            tolerations=[client.V1Toleration(key="nodepool", operator="Equal", value="128gb", effect="NoSchedule")],
            volumes=[
                client.V1Volume(
                    name="shared-data",
                    persistent_volume_claim=client.V1PersistentVolumeClaimVolumeSource(claim_name=PERSISTENT_VOLUME_CLAIM_NAME),
                )
            ],
        )
    )

    # Job spec - single completion for best trial
    job_spec = client.V1JobSpec(
        template=template,
        parallelism=1,  # Single job for best trial
        completions=1,  # Single completion
        ttl_seconds_after_finished=3600,  # Keep for 1 hour after completion
        backoff_limit=2,  # Allow 2 retries
    )

    # Job object
    job = client.V1Job(api_version="batch/v1", kind="Job", metadata=client.V1ObjectMeta(name=best_trial_job_name), spec=job_spec)

    return job, batch_v1, best_trial_job_name


def deploy_job():
    """Deploy the best trial job to the cluster."""
    try:
        job, batch_v1, job_name = create_best_trial_job()

        # Apply the job
        response = batch_v1.create_namespaced_job(namespace=cfg.namespace, body=job)

        sc.printgreen(f"✅ Best trial job '{response.metadata.name}' created successfully!")
        print(f"📊 Study: {cfg.study_name}")
        print(f"🔧 Model config: {cfg.model_config}")
        print(f"🏷️  Namespace: {cfg.namespace}")

        # Print monitoring commands
        print("\n🔍 Monitoring commands:")
        print(f"   kubectl get jobs {job_name}")
        print(f"   kubectl get pods -l job-name={job_name}")
        print(f"   kubectl logs -l job-name={job_name} -f")
        print(f"   kubectl describe job {job_name}")

        return response

    except client.exceptions.ApiException as e:
        if e.status == 409:  # Conflict - job already exists
            sc.printyellow(f"⚠️  Job '{job_name}' already exists. Delete it first or use a different name.")
            print(f"   To delete: kubectl delete job {job_name}")
        else:
            sc.printred(f"❌ Error creating job: {e}")
        raise
    except Exception as e:
        sc.printred(f"💥 Unexpected error: {e}")
        raise


def main():
    """Main execution function."""
    print("🎯 Deploying best trial analysis to AKS...")

    try:
        # Validate configuration
        if not hasattr(cfg, "study_name") or not cfg.study_name:
            raise ValueError("study_name must be defined in cloud_calib_config.py")
        if not hasattr(cfg, "model_config") or not cfg.model_config:
            raise ValueError("model_config must be defined in cloud_calib_config.py")
        if not hasattr(cfg, "storage_url") or not cfg.storage_url:
            raise ValueError("storage_url must be defined in cloud_calib_config.py")

        # Deploy the job
        deploy_job()

        print("\n🎉 Deployment completed successfully!")
        print("The best trial analysis job has been submitted to the AKS cluster.")
        print("Results will be saved to the shared storage once the job completes.")

    except Exception as e:
        print(f"💥 Failed to deploy best trial job: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
