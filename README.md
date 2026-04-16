# laser-polio-nigeria

Nigeria-specific inputs, examples, and calibration tools for [laser-polio](https://github.com/InstituteforDiseaseModeling/laser-polio).

The core contribution is `build_nigeria_inputs()` — a function that assembles all simulation inputs from the Nigeria data package and passes them to `lp.run_sim()`.

## Install

```bash
pip install --extra-index-url https://packages.idmod.org/api/pypi/pypi-production/simple laser-polio-nigeria
```

## Data setup

This package requires the protected Nigeria data package. Point `LASER_POLIO_DATA` at the directory containing `manifest.py`:

```bash
export LASER_POLIO_DATA=/path/to/nigeria_polio_data
```

For development, `nigeria_polio_data/` in this repo is the data root (protected; not in version control).

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
LASER_POLIO_DATA=/path/to/nigeria_polio_data pytest tests/
```

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
├── nigeria_polio_data/         # Protected data (not in version control)
├── config/                     # Model and calibration YAML configs
├── data_curation_scripts/      # ETL pipelines for curating raw data
└── scripts/                    # Response SIA sweeps and other analyses
```

## Public synthetic data (CI / open development)

The [laser-polio-zamfara-data](https://github.com/InstituteforDiseaseModeling/laser-polio-zamfara-data)
package provides a synthetic Zamfara subset safe for open distribution:

```bash
pip install --extra-index-url https://packages.idmod.org/api/pypi/pypi-production/simple laser-polio-zamfara-data
python -m laser_polio_zamfara --target ~/zamfara_data
export LASER_POLIO_DATA=~/zamfara_data
```
