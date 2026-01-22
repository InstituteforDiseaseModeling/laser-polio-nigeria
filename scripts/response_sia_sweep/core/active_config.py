"""
Active Configuration for Response SIA Sweep

Simple centralized config - update these values to change what all scripts use.
"""

# Which config file to use (in scripts/response_sia_sweep/configs/)
ACTIVE_CONFIG = "config_nigeria_0sia_response_sens0.8_larger.yaml"

# Docker image tag to use for AKS jobs
DOCKER_IMAGE_TAG = "v20251216v2"

# Laser-polio version to install in Docker image
# Set to "latest" to use the latest available version
# Or specify a version like "0.2.40" for reproducibility
LASER_POLIO_VERSION = "latest"

# Default sweep parameters (can be overridden by individual scripts)
DEFAULT_DETECTION_TIMES = [0, 30, 60, 90, 120, 150]
DEFAULT_N_REPS = 100
