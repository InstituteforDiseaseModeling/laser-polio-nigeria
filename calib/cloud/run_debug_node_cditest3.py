import cloud_calib_config as cfg
from kubernetes import client
from kubernetes import config

# Load kubeconfig
config.load_kube_config(config_file="~/.kube/cditest3.yaml")
batch_v1 = client.BatchV1Api()

# Override job name for debug
debug_job_name = f"{cfg.job_name}-debug"

# Define the debug container
container = client.V1Container(
    name=debug_job_name,
    image=cfg.image,
    image_pull_policy="Always",
    command=["sleep", "infinity"],
    env_from=[client.V1EnvFromSource(secret_ref=client.V1SecretEnvSource(name="mysql-secrets"))],
    resources=client.V1ResourceRequirements(requests={"memory": "4Gi"}),  # Less memory, change if needed
)

# Pod template
template = client.V1PodTemplateSpec(
    metadata=client.V1ObjectMeta(labels={"job-name": debug_job_name}),
    spec=client.V1PodSpec(
        containers=[container],
        restart_policy="Never",
        image_pull_secrets=[client.V1LocalObjectReference(name="idmodregcred3")],
        node_selector={"nodepool": "highcpu"},
        tolerations=[client.V1Toleration(key="nodepool", operator="Equal", value="highcpu", effect="NoSchedule")],
    )
)

# Job spec
job_spec = client.V1JobSpec(
    template=template,
    parallelism=1,
    completions=1,
    ttl_seconds_after_finished=3600,
)

# Job object
job = client.V1Job(
    api_version="batch/v1",
    kind="Job",
    metadata=client.V1ObjectMeta(name=debug_job_name),
    spec=job_spec,
)

# Create the job
try:
    response = batch_v1.create_namespaced_job(namespace=cfg.namespace, body=job)
    print(f"✅ Debug job {response.metadata.name} created successfully.")
except client.exceptions.ApiException as e:
    print(f"❌ Error applying the debug job: {e}")