FROM idm-docker-staging.packages.idmod.org/laser/laser-polio-base:latest

# Set working directory
WORKDIR /app

# --- ENVIRONMENT VARS ---
ENV POLIO_ROOT=/app
ENV NUMBA_CPU_NAME=generic
ENV HEADLESS=1

# --- INSTALL laser-core and laser-polio ---
ARG CACHE_BREAKER=1
ARG LASER_POLIO_VERSION=latest

# Install specific versions to match your local environment
RUN pip install --upgrade -i https://packages.idmod.org/api/pypi/pypi-production/simple laser-core==0.6.0

# Install laser-polio - use specified version or latest
RUN if [ "$LASER_POLIO_VERSION" = "latest" ]; then \
        pip install --upgrade -i https://packages.idmod.org/api/pypi/pypi-production/simple laser-polio; \
    else \
        pip install --upgrade -i https://packages.idmod.org/api/pypi/pypi-production/simple laser-polio==$LASER_POLIO_VERSION; \
    fi

# Debug: Show what we actually installed
RUN pip list | grep laser

# --- COPY YOUR SCRIPT AND CONFIG ---
COPY scripts/response_sia_sweep/ /app/scripts/response_sia_sweep/
COPY data/ /app/data/

# Optional: If you have extra shared code
# COPY laser_polio/ /app/laser_polio/

# Fix permissions for scripts
RUN chmod +x scripts/response_sia_sweep/core/single_run.py

# Dependency analysis (good for debugging)
RUN pip3 install pipdeptree && pipdeptree -p laser-polio > /app/laser_polio_deps.txt
RUN pipdeptree -p laser-core > /app/laser_core_deps.txt

# Verify laser_core is available (catch issues early)
RUN python3 -c "import laser_core; print('✅ laser_core imported successfully')"
RUN python3 -c "from laser_core import PropertySet; print('✅ PropertySet imported successfully')"

# Test that laser_polio can import (this was failing before)
RUN python3 -c "import laser_polio; print('✅ laser_polio imported successfully')"

# Optional: Basic functionality test (uncomment if you want full validation)
# RUN python3 scripts/response_sia_sweep/core/single_run.py \
#      --config scripts/response_sia_sweep/configs/config_nigeria.yaml \
#      --response_time 30 --rep 0 --output_dir /tmp/test

# --- SET ENTRYPOINT ---
# Use single_run.py for better organization and metadata tracking
ENTRYPOINT ["python3", "/app/scripts/response_sia_sweep/core/single_run.py"]
