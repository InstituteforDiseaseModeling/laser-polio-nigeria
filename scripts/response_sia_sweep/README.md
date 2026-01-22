# Response SIA Sweep

Parameter sweep analyzing how response SIA timing affects polio outbreak dynamics. Tests different values of `response_sia_time_to_1st_round` (time from case detection to first SIA round) across multiple replicates.

## Quick Start

Instructions for running the detection speed sweep. 
1. Create a new config in /configs
2. Update core/active_config.py with the new config name & a new docker image tag.
3. Run core/build_and_push_response_sweep.py
4. Run core/submit_sweep_jobs.py
5. Run core/download_results.py
6. Run core/compile_and_plot_results.py

```bash
# 1. Configure the sweep (edit if needed)
vim scripts/response_sia_sweep/core/active_config.py

# 2. Submit jobs to AKS
python scripts/response_sia_sweep/core/submit_sweep_jobs.py

# 3. Monitor progress
python scripts/response_sia_sweep/core/monitor_jobs.py

# 4. Download and analyze results when complete
python scripts/response_sia_sweep/core/download_results.py \
  --config scripts/response_sia_sweep/configs/config_zamfara.yaml
python scripts/response_sia_sweep/core/compile_and_plot_results.py
```

## Core Scripts

### Configuration
- **`core/active_config.py`** - Main configuration (which config file, Docker image, sweep parameters)
- **`configs/config_zamfara.yaml`** - Zamfara region simulation (~1M population)
- **`configs/config_nigeria.yaml`** - Full Nigeria simulation (~200M population)

### Execution
- **`core/submit_sweep_jobs.py`** - Submit jobs with automatic cleanup
- **`core/single_run.py`** - Individual simulation runner with hierarchical organization (runs inside Kubernetes pods)

### Management
- **`core/monitor_jobs.py`** - Real-time job status and resource monitoring
- **`core/cleanup_completed_jobs.py`** - Clean up completed jobs
- **`core/download_results.py`** - Download results from AKS storage

### Analysis
- **`core/compile_and_plot_results.py`** - Generate summary statistics and plots

## Configuration

Edit `core/active_config.py` to set:

```python
ACTIVE_CONFIG = "config_zamfara.yaml"  # or "config_nigeria.yaml"
DEFAULT_RESPONSE_TIMES = [15, 30, 45, 60, 75, 90]  # days
DEFAULT_N_REPS = 100  # replicates per response time
DOCKER_IMAGE_TAG = "v1.0"  # Docker image version
```

## Key Metrics

Each simulation extracts:
- **total_infected** - Total cases over simulation period
- **peak_infected** - Maximum daily infected count
- **nodes_infected** / **total_nodes** - Geographic spread fraction
- **response_sias_triggered** - Number of response campaigns
- **outbreak_duration** - Days from first to last infection

## Typical Job Scale

- **6 response times × 100 replicates = 600 parallel jobs**
- **Per job**: 2 CPU cores, 8GB RAM, ~15-30 minutes runtime
- **Total resources**: ~1200 CPU cores, 4.8TB RAM
- **Wall-clock time**: 13-19 days for full sweep

## Output

Results saved to `/shared/results/` on AKS:
- Individual job CSV files: `response_time_{RT}_rep_{REP}.csv`
- Aggregated summary: `summary_statistics.csv`
- Plots: `response_sia_timing_analysis.png`

## Job Management

The enhanced workflow includes automatic job lifecycle management:

- **Automatic cleanup** of completed jobs (configurable delay)
- **Real-time monitoring** with resource tracking
- **Batch job submission** with duplicate detection
- **Failure detection** and reporting

Use `monitor_jobs.py --continuous` for real-time dashboard.

# Response time assumptions & pars

1. The time from onset of paralyis to detection of a case is drawn from a gamma distribution `np.random.gamma(shape, scale, size=cases)`. The shape and scale pars for Nigeria are estimated to be 5.7476, and 10.8485, respectively (from Arie/Kurt). Based on these pars, the mean is ~62.4 days [22.3, 123.0].
2. The first response campaign occurs 30 days after the case detection.
3. The second response campaign occurs 30 days after the first response. 
4. Another response campaign cannot occur within 180 days of the first response (150 days after second response). 

Kurt's detection delay pars are here: https://github.com/EMOD-Hub/EMOD-Generic-Scripts/blob/main/model_polio_nga01/Assets/data/obr_lag_param.json
They get used here: https://github.com/EMOD-Hub/EMOD-Generic-Scripts/blob/main/model_polio_nga01/Assets/data/obr_lag_param.json
