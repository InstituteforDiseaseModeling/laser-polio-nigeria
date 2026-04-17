# laser-polio-nigeria

Nigeria-specific inputs, examples, and calibration tools for [laser-polio](https://github.com/InstituteforDiseaseModeling/laser-polio).

The core contribution is `build_nigeria_inputs()` — a function that assembles all simulation inputs from the Nigeria data package and passes them to `lp.run_sim()`.

## Install

**Using the library in your own code** — pip install the package:

```bash
pip install --extra-index-url https://packages.idmod.org/api/pypi/pypi-production/simple laser-polio-nigeria
```

**Running scripts, examples, or calibrations** — clone the repo instead. The `examples/` scripts,
`config/` YAML files, and calibration entry point all require the repo to be present locally:

```bash
git clone https://github.com/InstituteforDiseaseModeling/laser-polio-nigeria.git
cd laser-polio-nigeria
pip install -e .
```

## Data setup

The simulation and calibration code reads data via a `manifest.py` file whose location is
set by the `LASER_POLIO_DATA` environment variable. Two data packages are available:

### Public Zamfara data (open access)

Covers Zamfara state only. Sufficient for running examples, tests, and the quick calibration test.

```bash
pip install --extra-index-url https://packages.idmod.org/api/pypi/pypi-production/simple \
    laser-polio-zamfara-data

# Extract data files and write manifest.py to ~/zamfara_data/
python -m laser_polio_zamfara --target ~/zamfara_data

export LASER_POLIO_DATA=~/zamfara_data
```

### Private Nigeria data (IDM access required)

Full Nigeria + West Africa dataset. Required for national-scale simulations and calibrations.

```bash
pip install --extra-index-url https://packages.idmod.org/api/pypi/idm-pypi-staging/simple \
    nigeria-polio

# Extract data files and write manifest.py to ~/nigeria_polio_data/
python -m nigeria_polio --target ~/nigeria_polio_data

export LASER_POLIO_DATA=~/nigeria_polio_data
```

## Quick start

```python
import laser_polio as lp
from laser_polio_nigeria.run_sim import build_nigeria_inputs

sim = lp.run_sim(
    build_inputs=build_nigeria_inputs,
    regions=["ZAMFARA"],
    start_year=2018,
    n_days=365,
    init_region="ANKA",
    init_prev=200,
    r0=14,
    save_plots=True,
    save_data=True,
)
```

Or run any of the scripts in `examples/`.

## Examples

| Script | Description |
|--------|-------------|
| `demo_zamfara.py` | Basic Zamfara 1-year run |
| `demo_zamfara_gravity.py` | Gravity migration model |
| `demo_zamfara_background_seeding.py` | Background seeding |
| `demo_zamfara_load_init_pop.py` | Load from saved population snapshot |
| `demo_zamfara_animate.py` | Animated map + time series (requires cartopy) |
| `demo_imperfect_diagnosis.py` | Imperfect paralysis detection sensitivity |
| `demo_response_sia.py` | Reactive SIA campaigns triggered by detected cases |
| `demo_nigeria.py` | Full Nigeria multi-year run |
| `demo_nigeria_best_calib.py` | Nigeria with best-fit calibrated parameters |
| `demo_west_africa.py` | Multi-country West Africa run |
| `demo_africa.py` | AFRO + EMRO regions |

## Tests

```bash
pytest tests/
```

Set `LASER_POLIO_DATA` before running if it isn't already in your environment (see [Data setup](#data-setup)).

- `tests/test_build_inputs.py` — unit tests for `build_nigeria_inputs`
- `tests/test_run_sim.py` — integration tests for `lp.run_sim` with Nigeria inputs

Slow tests (Nigeria-scale, multi-year) are skipped by default. Run `pytest -m slow` to include them.

## Repo layout

```
laser-polio-nigeria/
├── src/laser_polio_nigeria/
│   ├── run_sim.py              # build_nigeria_inputs() — main entry point
│   └── calibration/            # Calibration integration wrappers
├── examples/                   # 11 runnable demo scripts
├── tests/                      # pytest test suite
├── nigeria_polio_data/         # Data root after running 'python -m nigeria_polio' (not in version control)
├── config/                     # Model and calibration YAML configs
├── data_curation_scripts/      # ETL pipelines for curating raw data
└── scripts/                    # Response SIA sweeps and other analyses
```

## Calibration

Calibration uses [laser-polio-calibration](https://github.com/InstituteforDiseaseModeling/laser-polio-calibration)
as the engine and Optuna for hyperparameter optimization. The entry point in this repo is
`laser_polio_nigeria.calibration.calibrate`.

### Prerequisites

**1. Install `kaleido` for post-run report plots** (skip if you don't need static PNG output):

```bash
pip install "kaleido<1.0"   # pin <1.0 to avoid Chrome dependency on Linux servers
```

**2. Set up data:**

```bash
export LASER_POLIO_DATA=/path/to/nigeria_polio_data   # or zamfara_data for a quick test
```

**3. Configure Optuna storage:**

```bash
export STORAGE_URL=sqlite:///my_calib.db   # local SQLite file (created automatically)
# omit STORAGE_URL to default to MySQL (used in AKS/Docker deployments)
```

### Run a calibration

```bash
python -m laser_polio_nigeria.calibration.calibrate \
  --study-name my_study \
  --model-config nigeria_7y_2017_regions_r0_radk_mmf_ssn_nozi_pim_pop50.yaml \
  --calib-config r0_radk_pim.yaml \
  --config-root config \
  --n-trials 100 \
  --n-replicates 1
```

All `--model-config` and `--calib-config` paths are resolved relative to `--config-root`
under `model_configs/` and `calib_configs/` subdirectories respectively.

Results are written to `results/<study-name>/`.

### Quick local test (~30s, Zamfara only)

Validates the full pipeline end-to-end with a small population:

```bash
export STORAGE_URL=sqlite:///test_calib.db
export LASER_POLIO_DATA=/path/to/zamfara_data   # zamfara-data package is sufficient

python -m laser_polio_nigeria.calibration.calibrate \
  --study-name zamfara_test \
  --model-config zamfara_calib_test.yaml \
  --calib-config r0.yaml \
  --config-root config \
  --n-trials 3 \
  --n-replicates 1
```

### Config files

| Config | Location | Purpose |
|--------|----------|---------|
| `zamfara_calib_test.yaml` | `config/model_configs/` | Minimal Zamfara test (pop_scale=0.05, ~8s/trial) |
| `nigeria_7y_2017_regions_r0_radk_mmf_ssn_nozi_pim_pop50.yaml` | `config/model_configs/` | Full Nigeria at 50% pop |
| `nigeria_7y_2017_regions_r0_radk_mmf_ssn_nozi_pim_pop10.yaml` | `config/model_configs/` | Full Nigeria at 10% pop |
| `r0.yaml` | `config/calib_configs/` | Single-parameter: r0 only |
| `r0_radk_pim.yaml` | `config/calib_configs/` | r0 + radiation_k + PIM random effects |

### Inspect results

```python
import optuna
import os

study = optuna.load_study(
    study_name="my_study",
    storage=os.environ["STORAGE_URL"],
)
print(study.best_trial)
print(study.trials_dataframe()[["number", "value", "params_r0"]].head(10))
```

### Dry run (verify config without running)

```bash
python -m laser_polio_nigeria.calibration.calibrate \
  --study-name my_study \
  --model-config zamfara_calib_test.yaml \
  --calib-config r0.yaml \
  --config-root config \
  --dry-run
```

