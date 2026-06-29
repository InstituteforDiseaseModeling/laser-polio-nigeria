# DDNS vs Culture Response SIAs

Compares the expected 5-year polio case burden under two surveillance paradigms — **DDNS** (direct detection in wastewater/NS samples) and **culture** — by sweeping over their key parameters (detection sensitivity and response time) and projecting forward from a calibrated population snapshot.

## Scientific Goal

DDNS and culture differ in two ways that affect outbreak response:

- **Detection sensitivity**: probability that a paralytic case triggers a detected signal
- **Response time**: days from detection to first response SIA round

This experiment quantifies how much those differences translate into expected cases over a 5-year horizon, given Nigeria's current outbreak state.

## Workflow Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│  PRE-STEP: Extract best calibration parameters                          │
│                                                                         │
│  extract_best_calib_params.py ──► configs/snapshot_nigeria.yaml         │
│  (reads Optuna MySQL study)        (writes r0, pim_re_*, etc.)          │
│  Then: manually set seed in snapshot_nigeria.yaml                       │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  PHASE 1: Create snapshot (9-year calibrated run, fixed seed)           │
│                                                                         │
│  snapshot_nigeria.yaml ──► create_snapshot.py ──► snapshot.h5           │
│  (2017-01-01, n_days=3287)                        + timeseries.csv      │
│  (response_sia: false)                            + snapshot_metrics.csv│
│                                                                         │
│  Snapshot date: 2025-12-31                                              │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  PHASE 2: Sweep response scenarios (5-year forward projection)          │
│                                                                         │
│  snapshot.h5 + response_nigeria.yaml ──► run_from_snapshot.py           │
│  (2026-01-01, n_days=1826)                                              │
│                                                                         │
│  Sweep:                                                                 │
│    detection_sensitivity: 0.50–1.00 in 0.05 steps (11 values)          │
│    response_time:         40–120d  in 10d steps  ( 9 values)            │
│    reps:                  100 per parameter combination                 │
│    total jobs:            11 × 9 × 100 = 9,900                         │
│                                                                         │
│  Outputs per run:                                                       │
│    results/result_rep{}_rt{}_ds{}.csv                                   │
│    timeseries/timeseries_rep{}_rt{}_ds{}.csv                            │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  PHASE 3: Analysis — DDNS vs culture comparison                         │
│                                                                         │
│  LAB_METHODS in active_config.py defines which (sensitivity,            │
│  response_time) values belong to each method.                           │
│                                                                         │
│  plot_ddns_vs_culture.py  ──► violin plots, breakdowns by parameter     │
│  plot_pairwise_heatmap.py ──► pairwise sensitivity × time heatmap       │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Step-by-Step Instructions

### Pre-step: extract best calibration parameters

Run this once when the calibration study has enough trials. It connects to the Optuna MySQL DB via `kubectl port-forward`, reads the best trial, and writes its transmission parameters into `configs/snapshot_nigeria.yaml`.

```bash
# From repo root
python scripts/ddns_vs_culture_response_sias/extract_best_calib_params.py
```

The script writes transmission parameters **and** the trial's `rand_seed` into `configs/snapshot_nigeria.yaml` automatically. Review the updated config before proceeding.

### Phase 1: create the snapshot

**Local (dev/test):**

```bash
cd scripts/ddns_vs_culture_response_sias
python run_local_snapshot.py
```

Output will print the snapshot path:
```
Use this snapshot path for response runs:
  SNAPSHOT_PATH = "results/ddns_vs_culture_response_sias/snapshots/snapshot_nigeria/local_snapshot_20260701_120000/snapshot.h5"
```

**Cluster (production):**

```bash
# Build and push Docker image first (from repo root)
python scripts/ddns_vs_culture_response_sias/core/build_and_push.py

# Dry run to preview
python scripts/ddns_vs_culture_response_sias/submit_snapshot_jobs.py --dry-run

# Submit
python scripts/ddns_vs_culture_response_sias/submit_snapshot_jobs.py

# Monitor
kubectl get jobs -l component=ddns-vs-culture,phase=create-snapshot
kubectl logs -l component=ddns-vs-culture,phase=create-snapshot --tail=20
```

### Phase 2: sweep response scenarios

**Local (single run for testing):**

Edit `run_local_response.py` to set `SNAPSHOT_PATH`, `RESPONSE_TIME`, `DETECTION_SENSITIVITY`, and `REP`, then:

```bash
cd scripts/ddns_vs_culture_response_sias
python run_local_response.py
```

**Cluster (full sweep — 9,900 jobs):**

```bash
# Replace <RUN_ID> with the run ID printed during Phase 1
python scripts/ddns_vs_culture_response_sias/submit_response_jobs.py \
    --snapshot-dir /shared/snapshots/ddns_vs_culture/snapshot_nigeria/<RUN_ID>/ \
    --dry-run

python scripts/ddns_vs_culture_response_sias/submit_response_jobs.py \
    --snapshot-dir /shared/snapshots/ddns_vs_culture/snapshot_nigeria/<RUN_ID>/

# Monitor
kubectl get jobs -l component=ddns-vs-culture,phase=run-response | tail -5
```

You can also sweep a subset for testing:

```bash
python scripts/ddns_vs_culture_response_sias/submit_response_jobs.py \
    --snapshot-dir /shared/snapshots/ddns_vs_culture/snapshot_nigeria/<RUN_ID>/ \
    --n-reps 5 \
    --detection-sensitivities 0.6 0.8 1.0 \
    --response-times 40 80 120
```

### Download results

```bash
python scripts/ddns_vs_culture_response_sias/download_results.py

# Snapshot only (includes .h5)
python scripts/ddns_vs_culture_response_sias/download_results.py --snapshot-only

# Specific response run ID
python scripts/ddns_vs_culture_response_sias/download_results.py --response-run-id response_20260701_120000
```

### Phase 3: analysis and plots

```bash
cd scripts/ddns_vs_culture_response_sias

# Main DDNS vs culture comparison (violin plots, breakdowns)
python plot_ddns_vs_culture.py

# Pairwise heatmap of all sensitivity × response_time combinations
python plot_pairwise_heatmap.py

# Or point at a specific results directory
python plot_ddns_vs_culture.py --response-dir results/ddns_vs_culture_response_sias/responses/response_20260701_120000
```

---

## Configuration

### `active_config.py`

| Variable | Description |
|----------|-------------|
| `DOCKER_IMAGE` | Image used for AKS jobs |
| `SNAPSHOT_CONFIG` | Path to snapshot YAML (has fixed seed) |
| `RESPONSE_CONFIG` | Path to response YAML (seed set per rep) |
| `SNAPSHOT_DIR` | Snapshot output dir on PVC |
| `OUTPUT_DIR` | Response output dir on PVC |
| `DETECTION_SENSITIVITIES` | Full sweep range (used at run time) |
| `RESPONSE_TIMES` | Full sweep range (used at run time) |
| `N_RESPONSE_REPS` | Replicates per parameter combination |
| `LAB_METHODS` | Per-method parameter ranges (used at analysis time) |

### `LAB_METHODS` — updating method definitions

`LAB_METHODS` in `active_config.py` defines which (sensitivity, response_time) combinations are considered plausible for each method. These are **only used during analysis/plotting**, not during the simulation sweep. Update them from literature or expert elicitation without rerunning any jobs:

```python
LAB_METHODS = {
    "ddns": {
        "detection_sensitivities": [0.80, 0.85, 0.90, 0.95, 1.00],  # update from elicitation
        "response_times": [40, 50, 60, 70],                          # update from elicitation
    },
    "culture": {
        "detection_sensitivities": [0.50, 0.55, 0.60, 0.65, 0.70],
        "response_times": [80, 90, 100, 110, 120],
    },
}
```

All values must be present in `DETECTION_SENSITIVITIES` and `RESPONSE_TIMES`.

---

## Output Structure

### Snapshot phase
```
results/ddns_vs_culture_response_sias/snapshots/{config_name}/{run_id}/
├── snapshot.h5              # Population state (HDF5)
├── snapshot_metrics.csv     # Summary at snapshot date
└── timeseries.csv           # Daily SEIR timeseries, 2017–2025
```

### Response phase
```
results/ddns_vs_culture_response_sias/responses/{config_name}/{run_id}/
├── results/
│   └── result_rep{r}_rt{rt}_ds{ds}.csv     # Summary metrics per run
└── timeseries/
    └── timeseries_rep{r}_rt{rt}_ds{ds}.csv  # Daily timeseries per run
```

### Result CSV columns

| Column | Description |
|--------|-------------|
| `rep` | Replicate number |
| `response_time` | Days from detection to 1st SIA round |
| `detection_sensitivity` | Probability of detecting a paralytic case |
| `seed` | Random seed used |
| `n_response_sia_rounds` | Number of response SIA rounds triggered |
| `total_infections` | Total infections over 5y |
| `new_potentially_paralyzed` | New potentially paralyzed cases |
| `new_paralyzed` | New paralytic cases |
| `new_detected_paralyzed` | New detected paralytic cases |

---

## Seed Strategy

- **Snapshot**: fixed seed in `configs/snapshot_nigeria.yaml` → deterministic 9-year outbreak trajectory
- **Response runs**: each rep gets a unique seed via `hash("ddns-vs-culture-rep-{rep}")`, so the same rep number produces the same stochastic variation regardless of the (sensitivity, response_time) combination being tested

## File Structure

```
ddns_vs_culture_response_sias/
├── README.md
├── active_config.py                  # All tunable settings
├── extract_best_calib_params.py      # Pull best trial → update snapshot config
├── run_local_snapshot.py             # Local Phase 1 runner
├── run_local_response.py             # Local Phase 2 runner (single run)
├── submit_snapshot_jobs.py           # AKS Phase 1 submission
├── submit_response_jobs.py           # AKS Phase 2 submission (sweep)
├── download_results.py               # Download results from cluster
├── plot_ddns_vs_culture.py           # Main comparison plots
├── plot_pairwise_heatmap.py          # Pairwise sensitivity × time heatmap
├── configs/
│   ├── snapshot_nigeria.yaml         # 9y snapshot config (fixed seed, 2017–2025)
│   └── response_nigeria.yaml         # 5y response config (2026–2030)
├── core/
│   ├── create_snapshot.py            # CLI: run 9y sim → snapshot.h5
│   ├── run_from_snapshot.py          # CLI: load snapshot → 5y response run
│   └── build_and_push.py             # Build and push Docker image
├── docker/
│   └── Dockerfile
└── jobs/
    ├── job_template_snapshot.yaml    # AKS job template (Phase 1)
    └── job_template_response.yaml    # AKS job template (Phase 2)
```
