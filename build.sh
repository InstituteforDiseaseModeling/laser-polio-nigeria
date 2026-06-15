#!/usr/bin/env bash
# Build wheels and Docker image for laser-polio-nigeria.
# Produces two tags: a date-stamped registry image and laser-polio-nigeria:local.
#
#   bash build.sh
#
# The registry-tagged image is for pushing to Artifactory (AKS).
# The :local tag is used by scripts/calibration/run_calib_local_docker.sh.

set -euo pipefail

GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

REGISTRY="idm-docker-staging.packages.idmod.org/laser/laser-polio"
DATE_TAG=$(date +%Y-%m-%d)
LOCAL_TAG="laser-polio-nigeria:local"

NIGERIA_VERSION=$(python3 -c "import tomllib; print(tomllib.loads(open('pyproject.toml','rb').read())['project']['version'])")
CALIB_VERSION=$(python3 -c "import tomllib; print(tomllib.loads(open('../laser-polio-calibration/pyproject.toml','rb').read())['project']['version'])")

echo -e "${BLUE}==> laser-polio-nigeria   v${NIGERIA_VERSION}${NC}"
echo -e "${BLUE}==> laser-polio-calibration v${CALIB_VERSION}${NC}"
echo ""

mkdir -p dist

echo -e "${BLUE}==> Step 1: Building laser-polio-calibration wheel...${NC}"
(cd ../laser-polio-calibration && .venv/bin/python3 -m build 2>/dev/null || python3 -m build)
cp ../laser-polio-calibration/dist/laser_polio_calibration-${CALIB_VERSION}-py3-none-any.whl dist/

echo -e "\n${BLUE}==> Step 2: Building laser-polio-nigeria wheel...${NC}"
.venv/bin/python3 -m build

echo -e "\n${BLUE}==> Step 3: Building Docker image...${NC}"
docker buildx build \
  --platform linux/amd64 \
  --build-arg NIGERIA_VERSION="${NIGERIA_VERSION}" \
  --build-arg CALIB_VERSION="${CALIB_VERSION}" \
  --tag "${REGISTRY}:${DATE_TAG}" \
  --tag "${REGISTRY}:latest" \
  --tag "${LOCAL_TAG}" \
  --file docker/Dockerfile \
  --load \
  .

echo -e "\n${GREEN}✓ Build complete!${NC}"
echo -e "  ${LOCAL_TAG}"
echo -e "  ${REGISTRY}:${DATE_TAG}"
echo -e "  ${REGISTRY}:latest"
