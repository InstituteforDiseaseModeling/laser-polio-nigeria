#!/usr/bin/env bash
# Dockerized local calibration runner.
# Edit the config section below and run from the repo root:
#
#   bash scripts/calibration/run_calib_docker.sh
#
# Prerequisites:
#   1. Build the image first (requires .netrc at repo root for IDM PyPI access):
#      bash build.sh
#   2. LASER_POLIO_DATA must be set (in .env or environment).

set -euo pipefail
cd "$(dirname "$0")/../.."  # always run from repo root

# ── Configuration ────────────────────────────────────────────────────────────

QUICK_TEST=true     # true = Zamfara (~30s/trial); false = full Nigeria
BUILD_IMAGE=false   # true = rebuild wheel + Docker image before running

if [ "$QUICK_TEST" = "true" ]; then
    STUDY_NAME="zamfara_test"
    MODEL_CONFIG="zamfara_calib_test.yaml"
    CALIB_CONFIG="r0.yaml"
    N_TRIALS=3
else
    STUDY_NAME="nigeria_calib"
    MODEL_CONFIG="nigeria_7y_2017_regions_r0_radk_mmf_ssn_nozi_pim.yaml"
    CALIB_CONFIG="r0_radk_pim.yaml"
    N_TRIALS=1
fi

N_REPLICATES=1
IMAGE="laser-polio-nigeria:local"

# ── Resolve LASER_POLIO_DATA ──────────────────────────────────────────────────

if [ -z "${LASER_POLIO_DATA:-}" ] && [ -f ".env" ]; then
    LASER_POLIO_DATA=$(grep '^LASER_POLIO_DATA=' .env | cut -d= -f2- | tr -d '"')
fi

if [ -z "${LASER_POLIO_DATA:-}" ]; then
    echo "ERROR: LASER_POLIO_DATA is not set. Add it to .env or export it before running."
    exit 1
fi

echo "Data path: ${LASER_POLIO_DATA}"

# ── Optionally build image ────────────────────────────────────────────────────

if [ "$BUILD_IMAGE" = "true" ]; then
    NIGERIA_VERSION=$(python3 -c "import tomllib; d=tomllib.loads(open('pyproject.toml','rb').read()); print(d['project']['version'])")
    echo "==> Building wheel..."
    python3 -m build

    echo "==> Building Docker image (version ${NIGERIA_VERSION})..."
    docker buildx build \
      --platform linux/amd64 \
      --build-arg NIGERIA_VERSION="${NIGERIA_VERSION}" \
      --tag "${IMAGE}" \
      --file docker/Dockerfile \
      --load \
      .
fi

# ── Verify image exists ───────────────────────────────────────────────────────

if ! docker image inspect "${IMAGE}" > /dev/null 2>&1; then
    echo "ERROR: Docker image '${IMAGE}' not found."
    echo "       Run with BUILD_IMAGE=true or build manually: bash build.sh"
    exit 1
fi

# ── Prepare results directory ─────────────────────────────────────────────────

RESULTS_HOST="$(pwd)/results/${STUDY_NAME}"
mkdir -p "${RESULTS_HOST}"

# ── Run ───────────────────────────────────────────────────────────────────────

echo "==> Starting calibration in Docker (study: ${STUDY_NAME}, trials: ${N_TRIALS})..."

docker run --rm \
  --platform linux/amd64 \
  -v "${LASER_POLIO_DATA}:/app/data:ro" \
  -v "$(pwd)/config:/app/config:ro" \
  -v "${RESULTS_HOST}:/app/results/${STUDY_NAME}" \
  -e LASER_POLIO_DATA=/app/data \
  -e STORAGE_URL="sqlite:////app/results/${STUDY_NAME}/calib.db" \
  "${IMAGE}" \
  --study-name "${STUDY_NAME}" \
  --model-config "${MODEL_CONFIG}" \
  --calib-config "${CALIB_CONFIG}" \
  --config-root /app/config \
  --n-trials "${N_TRIALS}" \
  --n-replicates "${N_REPLICATES}"

echo "==> Done! Results in ${RESULTS_HOST}"
