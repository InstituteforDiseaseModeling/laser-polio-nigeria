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
# Install laser-polio
# -----------------------------
ARG CACHE_BREAKER=1
RUN pip install --upgrade --pre \
    -i https://packages.idmod.org/api/pypi/pypi-production/simple \
    -vvv laser-polio[viz]==0.2.46.dev0 \
    --extra-index-url https://pypi.org/simple

# -----------------------------
# Install Nigeria data package
# -----------------------------
COPY .netrc /root/.netrc
RUN chmod 600 /root/.netrc

RUN pip install \
    -i https://packages.idmod.org/api/pypi/idm-pypi-staging/simple \
    nigeria-polio

# Bootstrap data into /app
RUN python3 -m nigeria_polio.bootstrap --target /app

# Copy data into canonical location expected by LASER_POLIO_DATA
RUN python3 - <<EOF
import nigeria_polio, shutil, os
pkg_path = os.path.dirname(nigeria_polio.__file__)
data_src = os.path.join(pkg_path, "data")
shutil.copytree(data_src, "/app/data", dirs_exist_ok=True)
EOF

# Remove credentials
RUN rm -f /root/.netrc

# -----------------------------
# Install calibration engine
# -----------------------------
COPY dist/laser_polio_calibration-0.1.0-py3-none-any.whl /tmp/
RUN pip install /tmp/laser_polio_calibration-0.1.0-py3-none-any.whl

# -----------------------------
# NEW: install Nigeria country package
# -----------------------------
COPY dist/laser_polio_nigeria-*.whl /tmp/
RUN pip install /tmp/laser_polio_nigeria-*.whl

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
# NEW ENTRYPOINT (country runner)
# -----------------------------
ENV LASER_POLIO_DATA=/app/data
ENTRYPOINT ["python3", "-m", "laser_polio_nigeria.calibration.calibrate"]
