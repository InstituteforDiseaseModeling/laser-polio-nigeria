#!/bin/bash
# Build script for laser-polio-nigeria
# Builds local wheel and Docker image with proper tagging

set -e  # Exit on error

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
IMAGE_NAME="idm-docker-staging.packages.idmod.org/laser/laser-polio"
DATE_TAG=$(date +%Y-%m-%d)

echo -e "${BLUE}==> Step 1: Building local wheel...${NC}"
python3.11 -m build

echo -e "\n${BLUE}==> Step 2: Building Docker image...${NC}"
docker buildx build \
  --platform linux/amd64 \
  --tag ${IMAGE_NAME}:${DATE_TAG} \
  --tag ${IMAGE_NAME}:latest \
  --file docker/Dockerfile \
  --load \
  .

echo -e "\n${GREEN}✓ Build complete!${NC}"
echo -e "  Tagged as: ${IMAGE_NAME}:${DATE_TAG}"
echo -e "  Tagged as: ${IMAGE_NAME}:latest"
