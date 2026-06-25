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

**Local development across all three repos** — if you want editable installs of `laser-polio`
and `laser-polio-calibration` alongside this repo (e.g., to make changes to the core engine or
calibration workflows), clone all three repos as siblings and install from source into the
`laser-polio-nigeria` venv:

```bash
# Clone the three repos as siblings (e.g., under ~/github/)
git clone https://github.com/InstituteforDiseaseModeling/laser-polio.git
git clone https://github.com/InstituteforDiseaseModeling/laser-polio-calibration.git
git clone https://github.com/InstituteforDiseaseModeling/laser-polio-nigeria.git

# Create and activate a venv inside laser-polio-nigeria
cd laser-polio-nigeria
uv venv
source .venv/bin/activate

# Install laser-polio editable
uv pip install -e ../laser-polio

# Build and install laser-polio-calibration from a local wheel
cd ../laser-polio-calibration
uv build
uv pip install dist/laser_polio_calibration-0.1.0-py3-none-any.whl

# Install laser-polio-nigeria editable
cd ../laser-polio-nigeria
uv pip install -e .
```

With `laser-polio` and `laser-polio-calibration` already installed, the final `uv pip install -e .`
resolves cleanly without needing the IDM extra-index-url.

## Data setup

### Why a manifest?

lpn needs several datasets to run — shapefiles, age pyramids, immunity estimates, SIA
schedules, and others. Rather than make every script remember file names and paths, lpn
exposes them through a **manifest**: a small object that maps a friendly name to each
file's path. Your code just says `manifest.age_pyramid` or `manifest.population`, and the
loader takes care of resolving where the file actually lives on disk.

The loader (`laser_polio_nigeria.manifest.load_manifest`) builds that manifest by
inspecting whatever directory the `LASER_POLIO_DATA` environment variable points at. It
can build a manifest from a generated `manifest.py` *or* directly from a directory of
correctly-named files — whichever you have.

### Required files

Eight files are expected in the data directory. The authoritative list lives in
`EXPECTED_DATA_FILES` in
[`src/laser_polio_nigeria/manifest.py`](src/laser_polio_nigeria/manifest.py); the table
below summarizes it for convenience.

| Variable | Filename | Purpose |
|---|---|---|
| `manifest.adjacency` | `adm01_adjacency.npz` | ADM1 adjacency graph |
| `manifest.age_pyramid` | `Nigeria_age_pyramid_2024.csv` | Nigeria age structure |
| `manifest.node_lookup` | `node_lookup.json` | Node metadata |
| `manifest.population` | `compiled_cbr_pop_ri_sia_underwt_africa.csv` | Combined demographic and vaccination dataset |
| `manifest.shapefile` | `shp_africa_low_res.gpkg` | Simplified Africa administrative boundaries |
| `manifest.sia_future` | `sia_scenario_1.csv` | Prospective SIA schedule |
| `manifest.sia_historic` | `sia_historic_schedule.csv` | Historical SIA schedules |
| `manifest.init_immunity` | `init_immunity_0.5coverage_january.h5` | Initial immunity at 0.5 coverage (default scenario) |

### How to get the files

Three options, depending on your access:

| Option | When to use | Auth required |
|---|---|---|
| **[Public Zamfara data](#public-zamfara-data-open-access)** | Examples, tests, quick calibration | None |
| **[Private Nigeria data](#private-nigeria-data-idm-access-required)** | National-scale simulations | IDM Artifactory account |
| **[Bring your own files](#bring-your-own-files)** | Colleague's tarball, internal share, etc. | None |

Whichever option you pick, point `LASER_POLIO_DATA` at the resulting directory. The
simplest way is a `.env` file in the repo root (gitignored):

```
LASER_POLIO_DATA=/absolute/path/to/repo/data_local/nigeria_polio_data
```

Use an absolute path — `~` is not expanded. The package loads `.env` automatically on
import, so no per-terminal `export` is needed.

### Public Zamfara data (open access)

Covers Zamfara state only. Sufficient for running examples, tests, and the quick calibration test.

```bash
pip install --extra-index-url https://packages.idmod.org/api/pypi/pypi-production/simple \
    laser-polio-zamfara-data

# Extract data files and write manifest.py to data_local/zamfara_data/
python -m laser_polio_zamfara --target data_local/zamfara_data

# Then update LASER_POLIO_DATA in your .env to point here.
```

### Private Nigeria data (IDM access required)

Full Nigeria + West Africa dataset. Required for national-scale simulations and calibrations.

#### Authentication

The `nigeria-polio` package lives on a private IDM index. You need a JFrog/Artifactory account with read access to `idm-pypi-staging` — the same credentials you'd use to log into the JFrog web UI at `packages.idmod.org`. Without auth, `pip`/`uv` will report a `403 Forbidden`.

Configure credentials once via `.netrc` and both `pip` and `uv` pick them up automatically:

**Linux / macOS**

```bash
cat >> ~/.netrc <<'EOF'
machine packages.idmod.org
  login YOUR_USERNAME
  password YOUR_PASSWORD
EOF
chmod 600 ~/.netrc
```

**Windows (PowerShell)**

```powershell
@"
machine packages.idmod.org
  login YOUR_USERNAME
  password YOUR_PASSWORD
"@ | Add-Content -Path "$env:USERPROFILE\.netrc"
```

The file lives at `%USERPROFILE%\.netrc` (typically `C:\Users\<you>\.netrc`). If a tool can't find it, try renaming to `_netrc` — some legacy tools follow the older curl convention — or set `NETRC=%USERPROFILE%\.netrc` explicitly.

> Your IDM account password works directly. If you'd rather not store it in a plaintext file, you can generate a scoped **API token** from the JFrog web UI (*Edit Profile → Identity Tokens*) and use that as the `password` value instead.

**Troubleshooting.** If `pip install` still returns `403 Forbidden`, verify `.netrc` is being read:

```bash
curl -n -I https://packages.idmod.org/api/pypi/idm-pypi-staging/simple/nigeria-polio/
```

`HTTP/1.1 200 OK` means auth is working — re-run the install. `401`/`403` means the file isn't being picked up or the credentials are wrong. Common causes:

- File permissions too open on Linux/macOS (`chmod 600 ~/.netrc`).
- Wrong filename or location on Windows — try `_netrc`, or set `NETRC=%USERPROFILE%\.netrc`.
- Credential is wrong, or your account lacks read access to `idm-pypi-staging` (verify by logging into the JFrog UI). If using a token, confirm it hasn't expired.
- Stale credentials cached by a corporate proxy — try from outside the VPN, or with `--no-cache-dir`.

#### Install

```bash
pip install --extra-index-url https://packages.idmod.org/api/pypi/idm-pypi-staging/simple \
    nigeria-polio

# Extract data files and write manifest.py to data_local/nigeria_polio_data/
python -m nigeria_polio --target data_local/nigeria_polio_data

# Then update LASER_POLIO_DATA in your .env to point here.
```

### Bring your own files

If you already have the data files from somewhere other than the `nigeria-polio` wheel —
a colleague's tarball, an internal share, a USB drive — you can use them directly without
installing `nigeria-polio` or setting up Artifactory credentials. The only requirement is
that the file names match what the loader expects (see `EXPECTED_DATA_FILES` in
[`src/laser_polio_nigeria/manifest.py`](src/laser_polio_nigeria/manifest.py)).

> **Trust note.** If the bundle includes a `manifest.py`, the loader executes it as
> Python code at load time. Only use bundles from sources you trust, the same way you'd
> only `pip install` packages from a trusted index. If you've received a data dir from an
> untrusted source and want to use it anyway, delete its `manifest.py` first — the loader
> will fall back to filename-based binding and won't execute any code from the bundle.

Drop the files in any directory and point `LASER_POLIO_DATA` at it:

```bash
# No manifest.py needed — the loader synthesizes the bindings from the filenames.
LASER_POLIO_DATA=/absolute/path/to/data laser-polio-nigeria-run-sim
```

If you'd rather have a shareable `manifest.py` written into the directory (useful when
packaging a tarball for someone else), generate one with:

```bash
python -m laser_polio_nigeria.manifest /absolute/path/to/data
```

That writes a portable manifest whose `DATA_ROOT` resolves relative to its own location,
so the directory can be `tar`'d / `rsync`'d / moved anywhere without breaking.

The command refuses to overwrite an existing `manifest.py` so you don't accidentally
clobber custom user bindings; pass `--force` if you really do want to replace it.

## Quick start

```python
import laser_polio as lp
from laser_polio_nigeria.run_sim import build_nigeria_inputs

sim = lp.run_sim(
    build_inputs=build_nigeria_inputs,
    regions=["ZAMFARA"],
    start_year=2019,
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

Make sure `LASER_POLIO_DATA` is set in your `.env` (see [Data setup](#data-setup)) — `pytest` picks it up automatically on import.

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

**2. Set up data and Optuna storage in your `.env`:**

The `.env` loader picks up every `KEY=VALUE`, so both vars live there (see [Data setup](#data-setup)) —
no `export` needed:

```bash
LASER_POLIO_DATA=/path/to/repo/data_local/nigeria_polio_data   # or data_local/zamfara_data for a quick test
STORAGE_URL=sqlite:///my_calib.db              # local SQLite file (created automatically)
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
export LASER_POLIO_DATA=/path/to/repo/data_local/zamfara_data   # zamfara-data package is sufficient

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

