# calib_job_config.py
from pathlib import Path

import yaml

# ------------------- USER CONFIGS -------------------
#
# This configuration is used by both run_calib_workers.py and run_best_trial_on_aks.py
#
# For calibration workers: Use run_calib_workers.py with the settings below
# For best trial analysis: Use run_best_trial_on_aks.py with job_name, study_name, and model_config

# # Goal: Try all core pars in Nigeria
# job_name = "lpsk12"
# study_name = "calib_nigeria_7y_2017_r0_radk_nozi_pim_20251001"
# model_config = "nigeria_7y_2017_regions_r0_radk_mmf_ssn_nozi_pim.yaml"
# calib_config = "r0_radk_pim.yaml"

# Goal: Try all core pars in Nigeria with response campaigns instead of historic SIAs
job_name = "lpsk17"
study_name = "calib_nga_7y_2017_r0_radk_nozi_pim_1sia_resp_sens0.8_20251111"
model_config = "nga_7y_2017_regions_r0_radk_mmf_ssn_nozi_pim_1sia_resp_sens0.8.yaml"
calib_config = "r0_radk_pim.yaml"

# # Goal: Try removing regional weights
# job_name = "lpsk13"
# study_name = "calib_wa_sans_nga_7y_2017_r0_radk_nozi_pim_all_regional_wts_0_20251003"
# model_config = "wa_sans_nga_7y_2017_regions_r0_radk_mmf_ssn_nozi_pim.yaml"
# calib_config = "r0_amp_doy_radk_pim_all_regional_wts_0.yaml"

# # Goal: Try removing regional weights
# job_name = "lpsk14"
# study_name = "calib_wa_sans_nga_7y_2017_r0_radk_nozi_pim_bins_by_region_wt_0_20251003"
# model_config = "wa_sans_nga_7y_2017_regions_r0_radk_mmf_ssn_nozi_pim.yaml"
# calib_config = "r0_amp_doy_radk_pim_bins_by_region_wt_0.yaml"

# # Goal: Try Nigeria at 10% of pop
# job_name = "lpsk15"
# study_name = "calib_nigeria_7y_2017_r0_radk_nozi_pim_pop10_20251007"
# model_config = "nigeria_7y_2017_regions_r0_radk_mmf_ssn_nozi_pim_pop10.yaml"
# calib_config = "r0_radk_pim.yaml"

# # Goal: Try Nigeria at 50% of pop
# job_name = "lpsk16"
# study_name = "calib_nigeria_7y_2017_r0_radk_nozi_pim_pop50_20251010"
# model_config = "nigeria_7y_2017_regions_r0_radk_mmf_ssn_nozi_pim_pop50.yaml"
# calib_config = "r0_radk_pim.yaml"

# # Goal: Try Nigeria at 50% of pop
# job_name = "lpsk1"
# study_name = "calib_nigeria_7y_2017_r0_radk_nozi_pim_pop50_20251014"
# model_config = "nigeria_7y_2017_regions_r0_radk_mmf_ssn_nozi_pim_pop50.yaml"
# calib_config = "r0_radk_pim.yaml"

fit_function = "log_likelihood"
n_trials = 1  # Number of trials to run per pod
n_replicates = 1  # Number of replicates to run for each trial
parallelism = 50  # The number of pods (i.e., jobs) to run in parallel
completions = 5000  # The total number of pods (i.e., jobs) that need to successfully complete before the job is considered "done"

# ---------------------------------------------------

# Default settings
namespace = "default"
image = "idm-docker-staging.packages.idmod.org/laser/laser-polio:latest"

# NOTE: To run best trial analysis on AKS:
# 1. Set job_name, study_name, and model_config above (calib_config not needed for best trial)
# 2. Run: python calib/cloud/run_best_trial_on_aks.py
# The job will automatically use the storage_url and create a best trial analysis job

# Define the path to the YAML file with the storage URL from the docs
# Handle both running from repo root and from calib/cloud directory
current_dir = Path(__file__).parent
storage_path = current_dir / "local_storage.yaml"

# Try loading the storage URL from YAML, fallback to env var
storage_url = None
if storage_path.exists():
    storage = yaml.safe_load(storage_path.read_text())
    storage_url = storage.get("storage_url")
# Safety check
print(f"Storage URL: {storage_url}")
if storage_url is None:
    raise RuntimeError("Missing STORAGE_URL in local_storage.yaml")
