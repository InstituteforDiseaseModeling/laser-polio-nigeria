FROM idm-docker-staging.packages.idmod.org/laser/laser-polio-base:latest

WORKDIR /app

# Set environment variables early
ENV POLIO_ROOT=/app
ENV NUMBA_CPU_NAME=generic
ENV HEADLESS=1

# Install laser-polio (maximize layer cache)
RUN pip3 install -i https://packages.idmod.org/api/pypi/pypi-production/simple laser-polio[nigeria]

# Copy application code and configuration files
#COPY src/laser_polio_nigeria/ ./calib/
COPY src/laser_polio_nigeria/cloud/check_study.sh ./calib/
COPY ./data/ /app/data/

# Ensure script permissions after code is copied
RUN chmod a+x calib/check_study.sh

# Analyze dependencies (after laser-polio is installed)
RUN pip3 install pipdeptree && pipdeptree -p laser-polio > /app/laser_polio_deps.txt

# Final cleanup to reduce image size
RUN pip3 cache purge

# Entrypoint
ENTRYPOINT ["python3", "-m", "laser_polio_nigeria.calibrate"]
