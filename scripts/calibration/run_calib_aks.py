"""
Push the local Docker image to IDM registry and deploy calibration workers on AKS.
Run with the VS Code play button or from the repo root:

    python scripts/calibration/run_calib_aks.py

Prerequisites:
  - Build image first: run build_calib_docker.py
  - kubectl configured with AKS cluster access (~/.kube/config)
  - 'kubernetes' package installed: pip install kubernetes
Results land on the shared PVC (laser-stg-pvc) under results/<STUDY_NAME>/.
Use kubeutil.py from laser-polio-calibration to download them locally.
"""

import subprocess
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

# ── Configuration ─────────────────────────────────────────────────────────────

JOB_NAME     = "lpsk-nigeria-08"   # Short unique k8s name; must be lowercase, no underscores
STUDY_NAME   = "calib_nga_9y_2017_r0_radk_pim_annual_20260622"
MODEL_CONFIG = "nigeria_9y_2017_regions_r0_radk_mmf_ssn_nozi_pim_annual.yaml"
CALIB_CONFIG = "r0_radk_pim.yaml"
N_TRIALS     = 1     # trials per pod
N_REPLICATES = 1     # model runs per trial
PARALLELISM  = 50    # pods running simultaneously
COMPLETIONS  = 15000  # total pods (= total trials when N_TRIALS=1)
NODE_POOL    = "64gb"   # "64gb" (200 GiB RAM total) or "128gb" (for best-trial analysis)
MEMORY_GiB   = 50       # memory request per pod (use 50 for 64gb pool, 100 for 128gb)

# ── Constants ─────────────────────────────────────────────────────────────────

REGISTRY  = "idm-docker-staging.packages.idmod.org/laser/laser-polio"
DATE_TAG  = datetime.now().strftime("%Y-%m-%d-%H%M")
IMAGE     = f"{REGISTRY}:{DATE_TAG}"
NAMESPACE = "default"
PVC_NAME  = "laser-stg-pvc"

# ── Pre-flight ────────────────────────────────────────────────────────────────

result = subprocess.run(["docker", "image", "inspect", "laser-polio-nigeria:local"], capture_output=True)
if result.returncode != 0:
    print("ERROR: Local image 'laser-polio-nigeria:local' not found.")
    print("       Build it first: run build_calib_docker.py")
    sys.exit(1)

try:
    from kubernetes import client, config as k8s_config
    from kubernetes.client.exceptions import ApiException
except ImportError:
    print("ERROR: 'kubernetes' package not installed.")
    print("       pip install kubernetes")
    sys.exit(1)

print(f"Image:  {IMAGE}")
print(f"Job:    {JOB_NAME}")
print(f"Study:  {STUDY_NAME}")
print(f"Model:  {MODEL_CONFIG}")
print(f"Scale:  {PARALLELISM} pods × {N_TRIALS} trial(s) concurrent, {COMPLETIONS * N_TRIALS} total trials")
print()

# ── Push image ────────────────────────────────────────────────────────────────

print("==> Tagging and pushing image to registry...")
subprocess.run(["docker", "tag", "laser-polio-nigeria:local", IMAGE], check=True)
subprocess.run(["docker", "tag", "laser-polio-nigeria:local", f"{REGISTRY}:latest"], check=True)
subprocess.run(["docker", "push", IMAGE], check=True)
subprocess.run(["docker", "push", f"{REGISTRY}:latest"], check=True)

# ── Deploy Kubernetes Job ─────────────────────────────────────────────────────

print("==> Loading kubeconfig...")
k8s_config.load_kube_config()
batch_v1 = client.BatchV1Api()

container = client.V1Container(
    name=JOB_NAME,
    image=IMAGE,
    image_pull_policy="Always",
    command=[
        "python3", "-m", "laser_polio_nigeria.calibration.calibrate",
        "--study-name",   STUDY_NAME,
        "--model-config", MODEL_CONFIG,
        "--calib-config", CALIB_CONFIG,
        "--config-root",  "/app/config",
        "--n-trials",     str(N_TRIALS),
        "--n-replicates", str(N_REPLICATES),
    ],
    # mysql-secrets provides MYSQL_USER, MYSQL_PASSWORD, MYSQL_DB → storage URL auto-constructed
    env_from=[client.V1EnvFromSource(secret_ref=client.V1SecretEnvSource(name="mysql-secrets"))],
    env=[client.V1EnvVar(name="PYTHONUNBUFFERED", value="1")],
    resources=client.V1ResourceRequirements(requests={"memory": f"{MEMORY_GiB}Gi"}),
    # Mount PVC at /app/results so results (written to cwd/results/<study>) land on shared storage
    volume_mounts=[client.V1VolumeMount(name="results-data", mount_path="/app/results")],
)

template = client.V1PodTemplateSpec(
    spec=client.V1PodSpec(
        containers=[container],
        restart_policy="OnFailure",
        image_pull_secrets=[client.V1LocalObjectReference(name="idmodregcred3")],
        node_selector={"nodepool": NODE_POOL},
        tolerations=[client.V1Toleration(
            key="nodepool", operator="Equal", value=NODE_POOL, effect="NoSchedule",
        )],
        volumes=[client.V1Volume(
            name="results-data",
            persistent_volume_claim=client.V1PersistentVolumeClaimVolumeSource(claim_name=PVC_NAME),
        )],
    )
)

job = client.V1Job(
    api_version="batch/v1",
    kind="Job",
    metadata=client.V1ObjectMeta(name=JOB_NAME),
    spec=client.V1JobSpec(
        template=template,
        parallelism=PARALLELISM,
        completions=COMPLETIONS,
        ttl_seconds_after_finished=120,
        backoff_limit=1000,
    ),
)

print(f"==> Creating job '{JOB_NAME}'...")
try:
    batch_v1.create_namespaced_job(namespace=NAMESPACE, body=job)
    print(f"\n✓ Job '{JOB_NAME}' created!")
    print(f"  Results → {PVC_NAME}:/{STUDY_NAME}/")
except ApiException as e:
    if e.status == 409:
        print(f"\nERROR: Job '{JOB_NAME}' already exists. Delete it first:")
        print(f"  kubectl delete job {JOB_NAME}")
    else:
        print(f"\nERROR: {e}")
    sys.exit(1)

print()
print("Monitor:")
print(f"  kubectl get pods -l job-name={JOB_NAME} -w")
print(f"  kubectl logs -l job-name={JOB_NAME} --prefix -f")
print(f"  kubectl describe job {JOB_NAME}")
print()
print("Download results when done:")
print(f"  python laser-polio-calibration/scripts/kubeutil.py --action download \\")
print(f"    --remote-dir /app/results/{STUDY_NAME} --local-dir results/{STUDY_NAME}")
