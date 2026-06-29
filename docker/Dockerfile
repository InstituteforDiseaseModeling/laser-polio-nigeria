FROM idm-docker-staging.packages.idmod.org/laser/laser-polio-base:latest
# FROM idm-docker-staging.packages.idmod.org/laser-polio-base:2026-01-26

WORKDIR /app

# -----------------------------
# Environment variables
# -----------------------------
ENV POLIO_ROOT=/app
ENV NUMBA_CPU_NAME=generic
ENV HEADLESS=1

# -----------------------------
# Build arguments
# -----------------------------
ARG NIGERIA_VERSION=0.1.0

# -----------------------------
# Install laser-polio
# -----------------------------
ARG LP_VERSION
RUN pip install --upgrade --pre \
    -i https://packages.idmod.org/api/pypi/pypi-production/simple \
    "laser-polio[viz]==${LP_VERSION}" \
    --extra-index-url https://pypi.org/simple

# -----------------------------
# Install Nigeria data package
# -----------------------------
COPY .netrc /root/.netrc
RUN chmod 600 /root/.netrc

ARG CACHE_BREAKER=1
RUN pip install \
    -i https://packages.idmod.org/api/pypi/idm-pypi-staging/simple \
    nigeria-polio

# Copy data from package, then run bootstrap last so it always wins on manifest.py.
# (The wheel bundles a manifest.py with a developer-machine path baked in; bootstrap
# regenerates it with the correct DATA_ROOT=/app/data for this container.)
RUN python3 - <<EOF
import nigeria_polio, shutil, os
pkg_path = os.path.dirname(nigeria_polio.__file__)
data_src = os.path.join(pkg_path, "data")
shutil.copytree(data_src, "/app/data", dirs_exist_ok=True)
EOF

RUN python3 -m nigeria_polio.bootstrap --target /app/data

# Remove credentials
RUN rm -f /root/.netrc

# Set LASER_POLIO_DATA early (needed for subsequent steps)
ENV LASER_POLIO_DATA=/app/data

# -----------------------------
# Install calibration engine from local wheel
# -----------------------------
ARG CALIB_VERSION=0.1.0
COPY dist/laser_polio_calibration-${CALIB_VERSION}-py3-none-any.whl /tmp/
RUN pip install --no-cache-dir /tmp/laser_polio_calibration-${CALIB_VERSION}-py3-none-any.whl && \
    rm /tmp/laser_polio_calibration-${CALIB_VERSION}-py3-none-any.whl

# -----------------------------
# Install Nigeria country package (local wheel)
# NOTE: This is installed AFTER stable dependencies to maximize cache hits
# -----------------------------
COPY dist/laser_polio_nigeria-${NIGERIA_VERSION}-py3-none-any.whl /tmp/
RUN pip install --no-cache-dir /tmp/laser_polio_nigeria-${NIGERIA_VERSION}-py3-none-any.whl && \
    rm /tmp/laser_polio_nigeria-${NIGERIA_VERSION}-py3-none-any.whl

# -----------------------------
# Copy configs (runtime-mounted in prod, baked here for now)
# -----------------------------
COPY config/ /app/config/

# -----------------------------
# Optional tools / debugging
# -----------------------------
COPY tools/check_study.sh .
RUN chmod a+x check_study.sh

RUN pip3 install pipdeptree && \
    pipdeptree -p laser-polio > /app/laser_polio_deps.txt

# -----------------------------
# Cleanup
# -----------------------------
RUN pip3 cache purge

# -----------------------------
# Smoke test (optional but recommended)
# -----------------------------
RUN python3 - <<EOF
from laser_polio.run_sim import run_sim
run_sim(
    regions=["ZAMFARA"],
    start_year=2020,
    n_days=1,
    init_prev=0.001,
    r0=10,
    use_pim_scalars=False,
    run=True,
    save_data=False,
    verbose=0,
)
EOF

# -----------------------------
# Health check
# -----------------------------
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD python3 -c "import laser_polio_nigeria; print('OK')" || exit 1

# -----------------------------
# NEW ENTRYPOINT (country runner)
# -----------------------------
ENTRYPOINT ["python3", "-m", "laser_polio_nigeria.calibration.calibrate"]
