# laser_polio_nigeria

Nigeria-specific simulation inputs and build logic for [laser-polio](https://github.com/InstituteforDiseaseModeling/laser-polio).

## Main entry point

`build_nigeria_inputs(configs, verbose)` in `run_sim.py` assembles all simulation inputs from the Nigeria data manifest and returns them to `lp.run_sim()`.

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
)
```

`build_nigeria_inputs` reads from the directory pointed to by `LASER_POLIO_DATA`. It builds population, RI, SIA schedule, initial immunity, epi data, and geographic inputs, then passes them back through `configs` to `lp.run_sim`.

## Modules

| Module | Description |
|--------|-------------|
| `run_sim.py` | `build_nigeria_inputs()` — assembles all inputs from the data manifest |
| `calibration/build_inputs.py` | Calibration-specific input builder wrapper |
| `calibration/calibrate.py` | Optuna calibration integration |
| `comps/run.py` | Legacy COMPS/idmtools job submission |
