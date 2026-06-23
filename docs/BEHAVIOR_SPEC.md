# laser-polio-nigeria Behavior Specification (Test-Derived)

This document enumerates the expected behaviors of the `laser-polio-nigeria` simulation as
implicitly asserted by the test suite. It is intended as the seed for a formal requirements
specification: each bullet is a behavioral claim the tests rely on, with a citation back to
the test source.

Two categories of behavior are distinguished:

- **Unit-tested behaviors** (`tests/`): pass/fail correctness invariants enforced by CI.
  These are hard contracts.
- **Scientific behaviors** (`tests_scientific/`): qualitative or quantitative scientific
  properties exercised by sweep scripts. These scripts are not all pytest-asserted; some
  encode "things we believe about the model and verify by inspection of plots/outputs."
  They are listed because they represent expected behavior of the model, but they are not
  enforced by CI in the same way.

Citations use `path:line` form where helpful. All paths are relative to the repository root.

---

## 1. Environment & Data Setup

### Unit-tested
- The simulation reads its data inputs from a directory pointed to by the `LASER_POLIO_DATA`
  environment variable. When that variable is not explicitly set by the shell, the test
  harness defaults it to `<repo_root>/nigeria_polio_data` so tests can run unconfigured.
  (`tests/conftest.py:1-8`)
- The data-loading mechanism (`load_manifest()` in `laser_polio_nigeria.manifest`) reads
  `LASER_POLIO_DATA` from the environment each time it's called. The test harness sets the
  variable in `conftest.py` before any module-level loads run, so tests work whether they
  invoke the loader directly or indirectly. (`tests/conftest.py:4-8`)
- The loader supports three resolution paths for the data root:
  - **Rich manifest** (`manifest.py` defines every variable): the manifest's bindings win
    when the file each one points at exists; missing bindings fall through to synthesis.
  - **Thin manifest** (`manifest.py` declares only `DATA_ROOT`): all variables synthesized
    from `<DATA_ROOT>/<filename>` per the consumer's `EXPECTED_DATA_FILES` contract.
  - **Naked dir** (no `manifest.py` at all): same synthesis path. Lets a user with just a
    folder of data files run the model without `nigeria_polio` installed.
  (`src/laser_polio_nigeria/manifest.py`, `tests/test_manifest.py`)
- `LASER_POLIO_DATA` is authoritative — a manifest with a hardcoded `DATA_ROOT` pointing
  elsewhere does **not** redirect the loader. (`tests/test_manifest.py::test_load_ignores_manifest_data_root_override`)

---

## 2. Input Building (`build_nigeria_inputs`)

### 2.1 Output contract

The returned input bundle must expose, at minimum, the following keys:
`start_date`, `n_days`, `pop`, `sus_by_age_node`, `cbr`, `init_prevs`, `r0_scalars`, `shp`,
`node_lookup`, `ri`, `ri_ipv`, `sia_schedule`, `sia_prob`, `response_sia`.
(`tests/test_build_inputs.py:13-28`, `test_returns_required_keys`)

### 2.2 Region filtering and node consistency
- A region filter (e.g., `regions=["ZAMFARA"]`) yields a non-empty population vector; every
  node population must be strictly positive.
  (`test_population_nonzero`, `tests/test_build_inputs.py:52-55`)
- All per-node arrays returned by `build_nigeria_inputs` have the same length as the
  population vector: `cbr`, `init_prevs`, `r0_scalars`, `ri`, `ri_ipv`, `sia_prob`, `shp`,
  `node_lookup`. (`test_node_count_consistent`, `tests/test_build_inputs.py:58-68`)

### 2.3 Initial prevalence seeding
- When `init_region` is set (e.g., `"ANKA"`) and `init_prev > 0`, at least one node has a
  non-zero entry in the `init_prevs` vector. (`test_init_region_seeded`,
  `tests/test_build_inputs.py:71-74`)

### 2.4 Date handling
- `n_days` provided in configs flows through unchanged to the output bundle.
  (`test_n_days_passed_through`, `tests/test_build_inputs.py:77-79`)
- When only `start_year` is given, the output `start_date` is January 1 of that year
  (e.g., `start_year=2020` → `2020-01-01`). (`test_start_date_from_start_year`,
  `tests/test_build_inputs.py:112-115`)
- When `start_date` is provided explicitly (e.g., `"2020-06-15"`), the output `start_date`
  matches it, overriding any year-based default. (`test_start_date_override`,
  `tests/test_build_inputs.py:118-121`)

### 2.5 Population scaling
- A `pop_scale` parameter linearly rescales the total population: `pop_scale=0.5` produces
  a population sum within 1% of half of the `pop_scale=1.0` total.
  (`test_pop_scale`, `tests/test_build_inputs.py:82-87`)

### 2.6 SIA schedule sourcing
- With the default SIA source (`sia_source="default"`), a one-year simulation window must
  contain at least one scheduled SIA event. The default synthetic schedule includes mOPV2
  campaigns in odd years (test uses `start_year=2019`).
  (`test_sia_schedule_default_not_empty`, `tests/test_build_inputs.py:90-95`)
- Setting `sia_schedule_source="none"` results in `sia_schedule` being `None` (i.e., no SIA
  events are scheduled). (`test_sia_schedule_none_source`,
  `tests/test_build_inputs.py:98-100`)

### 2.7 Config side-effect: age pyramid path injection
- `build_nigeria_inputs` mutates the passed `configs` dictionary to inject an
  `age_pyramid_path` key, so that `run_sim` can forward this to the model parameters.
  (`test_age_pyramid_path_injected`, `tests/test_build_inputs.py:103-109`)

---

## 3. Simulation Lifecycle (`lp.run_sim`)

### 3.1 Entrypoint and orchestration
- `lp.run_sim` accepts a `build_inputs` callable (here `build_nigeria_inputs`) plus
  region/date/initial-condition keyword arguments, and returns a `sim` object with
  `results`, `nodes`, and `people` attributes after a completed run.
  (All integration tests, `tests/test_run_sim.py:14-26`)
- `run=False` can be passed to perform initialization only (no time-stepping), used in
  conjunction with `save_init_pop=True` to produce a snapshot.
  (`test_zamfara_snapshot_roundtrip`, `tests/test_run_sim.py:132-142`)

### 3.2 Time grid
- The number of recorded timesteps `sim.nt` equals `n_days + 1` (i.e., the simulation
  records an initial state at t=0 plus one state per simulated day).
  (`_assert_valid_sim`, `tests/test_run_sim.py:29-37`; reinforced by
  `test_nigeria_full_year` which expects `sim.nt == 366` for `n_days=365`,
  `tests/test_run_sim.py:152-168`)

### 3.3 Results array shape
- `sim.results.I`, `sim.results.S`, and `sim.results.new_exposed` all have shape
  `(sim.nt, n_nodes)`. (`test_results_shape`, `tests/test_run_sim.py:81-87`;
  `_assert_valid_sim`, `tests/test_run_sim.py:33-37`)
- Total infections and total susceptibles summed over all space and time are non-negative.
  (`_assert_valid_sim`, `tests/test_run_sim.py:36-37`)

### 3.4 Snapshot save/load roundtrip
- With `save_init_pop=True` and a `results_path`, running with `run=False` writes a file
  named `init_pop.h5` into the results path.
  (`test_zamfara_snapshot_roundtrip`, `tests/test_run_sim.py:132-143`)
- A subsequent `lp.run_sim` call given `init_pop_file=<path to init_pop.h5>` must produce
  a valid completed simulation matching the standard shape contract.
  (`test_zamfara_snapshot_roundtrip`, `tests/test_run_sim.py:144-149`)

### 3.5 Full Nigeria scale runs
- The full Nigeria region (`regions=["NIGERIA"]`) can be simulated end-to-end for one year
  (`n_days=365`), producing the expected `sim.nt = 366` time axis and a positive node count.
  This is the "slow path" and is skipped by default in CI.
  (`test_nigeria_full_year`, `tests/test_run_sim.py:152-168`)

---

## 4. Demographic Dynamics

### Unit-tested
- A simulation can be configured with `cbr=np.array([0])` to disable births/deaths
  (a no-vital-rates regime), and runs to completion under that setting.
  (Used as a control assumption in scientific tests; tests assume this knob exists and
  behaves as documented: `tests_scientific/individual_heterogeneity.py:27`,
  `tests_scientific/outbreak_size.py:46`)

### Scientific (not CI-enforced)
- The model supports a fully susceptible population via `init_immun_scalar=0.0`.
  (`tests_scientific/individual_heterogeneity.py:22`, `tests_scientific/outbreak_size.py:41`)
- An age pyramid (`age_pyramid_path` injected by input builder) shapes the initial age
  distribution; this is a precondition for `sus_by_age_node` to be meaningful.
  (Implied by `test_age_pyramid_path_injected`, `tests/test_build_inputs.py:103-109`)

---

## 5. Disease Dynamics

### 5.1 Strain tracking
- Results are reported per strain: `sim.results.I_by_strain`, `sim.results.E_by_strain`,
  and `sim.results.new_exposed_by_strain` are 3-D arrays indexed by
  `(time, node, strain)`, with strain index 0 corresponding to VDPV2.
  (`tests_scientific/individual_heterogeneity.py:90-93`,
  `tests_scientific/outbreak_size.py:121-123`,
  `tests_scientific/rand_seed.py:87-88`,
  `tests_scientific/sweep_seasonal_amp_doy_r0_nigeria_7y.py:100`)

### 5.2 SEIR structure and durations
- The model has an explicit Exposed compartment. Its duration can be set via
  `dur_exp=lp.constant(value=...)`. Setting `dur_exp=lp.constant(value=0)` collapses to
  effective SIR dynamics for benchmarking against the Kermack-McKendrick model.
  (`tests_scientific/outbreak_size.py:111`)
- The duration of infection (`dur_inf`) is similarly configurable
  (e.g., `lp.constant(value=25)` ensures infections expire within a 30-day run).
  (`tests_scientific/individual_heterogeneity.py:32`)

### 5.3 Seeded infection propagation (unit)
- With `init_prev > 0`, total `new_exposed` summed over the run is strictly positive
  (the seed must lead to at least one new exposure under default `r0=14`).
  (`test_seeded_infections_propagate`, `tests/test_run_sim.py:90-95`)
- Total `new_exposed` is monotonic non-decreasing in `init_prev`: a run with `init_prev=200`
  produces at least as many cumulative exposures as a run with `init_prev=1`
  (everything else equal). (`test_higher_seed_produces_more_infections`,
  `tests/test_run_sim.py:98-102`)

### 5.4 R0 produces the expected number of secondary infections (scientific)
- With heterogeneity ON, no immunity, flat spatial R0 scalars, no seasonality, no vital
  rates, no vaccination, single initial infection, long enough exposure (60 d) and finite
  infection duration (25 d) inside a 30-day window: the mean number of exposures at the
  end of the run is ~14 (within atol=7) when `r0=14`. This validates the per-infection
  reproduction number under heterogeneity.
  (`tests_scientific/individual_heterogeneity.py:103-108`)
- Under the same assumptions, the single seed infection clears within the run
  (`I_final == 0` for all reps), and there is exactly one initial infection
  (`I_init == 1` for all reps).
  (`tests_scientific/individual_heterogeneity.py:101-105`)

### 5.5 Outbreak size matches Kermack-McKendrick limit (scientific)
- With effective SIR dynamics (`dur_exp=0`), a fully susceptible population, no vital
  rates, no seasonality, no vaccination, a single node, and no heterogeneity, the
  fraction of the population ultimately infected as a function of `R0` follows the
  Kermack-McKendrick final-size equation
  `z = S0 * (1 - exp(-R0 * (z + I0)))`, including the threshold at `R0 * S0 = 1`.
  (`tests_scientific/outbreak_size.py:62-79`, sweep over
  `r0_values = np.linspace(1, 10, 15)`)
- This expectation is exercised both with and without `individual_heterogeneity`; both
  configurations are plotted against the analytic curve.
  (`tests_scientific/outbreak_size.py:34, 146-189`)

### 5.6 Individual heterogeneity
- When `individual_heterogeneity=True`, each agent carries a per-person acquisition risk
  multiplier (`sim.people.acq_risk_multiplier`) and a per-person daily infectivity
  (`sim.people.daily_infectivity`). These are sampled distributions.
  (`tests_scientific/individual_heterogeneity.py:96-99`)
- The distributions are expected to span a meaningful range (plotted as histograms over
  3 reps' pooled values). (`tests_scientific/individual_heterogeneity.py:111-119`)
- A correlation between per-agent risk and per-agent infectivity is computed
  (Spearman); the test reports it but does not enforce a threshold. The intent is to
  observe whether risk and infectivity are independent or coupled.
  (`tests_scientific/individual_heterogeneity.py:122-128`)

### 5.7 Spatial R0 scalars
- Per-node R0 scalars can be flattened to 1.0 by setting `r0_scalar_wt_slope=0.0`
  and `r0_scalar_wt_intercept=0.5`. This is treated as a documented mechanism for
  obtaining a uniform R0 across nodes. (`tests_scientific/individual_heterogeneity.py:24-25`,
  `tests_scientific/outbreak_size.py:43-44`)
- A pre-immunity-multiplier ("PIM") scalar mode is also supported via
  `use_pim_scalars=True`. A simulation in this mode must run without error and yield
  valid result shapes. (`test_zamfara_pim_scalars`, `tests/test_run_sim.py:70-72`;
  `tests_scientific/individual_heterogeneity.py:52`,
  `tests_scientific/rand_seed.py:83`)

### 5.8 Detection / surveillance (paralysis)
- The simulation produces both a true paralyzed count and a detected paralyzed count,
  with the detection process governed by `paralysis_detection_sensitivity ∈ [0, 1]`.
  Results are accessible via `sim.results.paralyzed` and
  `sim.results.detected_paralyzed`. (`test_imperfect_diagnosis_runs`,
  `tests/test_run_sim.py:105-129`)
- Detected paralyzed cases must never exceed true paralyzed cases at any timestep,
  for either perfect (`paralysis_detection_sensitivity=1.0`) or imperfect
  (`paralysis_detection_sensitivity=0.8`) detection.
  (`tests/test_run_sim.py:127-129`)
- The model supports a configurable paralysis rate per infection via `p_paralysis`
  (e.g., `1/50`). (`tests/test_run_sim.py:116`)
- A "new potentially paralyzed" series `sim.results.new_potentially_paralyzed`
  is also produced (used as a metric in seasonality/SIA sweeps).
  (`tests_scientific/sweep_seasonal_amp_doy_r0_nigeria_7y.py:101`,
  `tests_scientific/sweep_seasonal_amp_sia_nga_7y.py:100`)

---

## 6. Seasonality

### Unit-tested
- The simulation accepts a `seasonal_amplitude` parameter; setting it to `0.0` disables
  seasonality entirely. (`tests_scientific/individual_heterogeneity.py:26`,
  `tests_scientific/outbreak_size.py:45`)

### Scientific (not CI-enforced)
- Transmission is modulated by a seasonal forcing curve with parameters
  `seasonal_amplitude` (relative amplitude) and `seasonal_peak_doy` (day of year at
  which seasonal transmission peaks).
  (`tests_scientific/sweep_seasonal_amp_doy_zamfara_1y.py:32-33`)
- The seasonality knob is expected to produce observable changes in infection
  time-series across a sweep of amplitudes `[0.1, 0.5, 0.9]` and peak days of year.
  Tested ranges:
  - Zamfara 1-yr sweep: `peak_doy ∈ {90, 180, 270}` (spring/summer/fall).
    (`tests_scientific/sweep_seasonal_amp_doy_zamfara_1y.py:33`)
  - Nigeria 7-yr sweep (subset of states): `peak_doy ∈ {120, 165, 210}` crossed with
    `r0 ∈ {5, 10, 15}` and `amplitude ∈ {0.1, 0.5, 0.9}`.
    (`tests_scientific/sweep_seasonal_amp_doy_r0_nigeria_7y.py:13-15`)
  - Nigeria 7-yr SIA × seasonality sweep: `amplitude ∈ {0.0, 0.1, 0.2}` with
    fixed `peak_doy=159`. (`tests_scientific/sweep_seasonal_amp_sia_nga_7y.py:13, 19`)
- Across these sweeps, the model is expected to produce distinct, plottable time-series
  per (amplitude, peak_doy) combination, with reproducibility across reps and
  qualitative differences across cells. No numeric tolerance is asserted; expected
  behavior is qualitative/visual.

---

## 7. Spatial Structure and Migration

### Unit-tested
- The simulation supports two migration models:
  - **Radiation**, parameterised by `migration_method="radiation"` and
    `radiation_k_log10` (e.g., `-0.3`). (`test_zamfara_radiation`,
    `tests/test_run_sim.py:40-42`)
  - **Gravity**, parameterised by `migration_method="gravity"`, `gravity_k`, and
    `gravity_k_exponent` (e.g., `gravity_k=1.0`, `gravity_k_exponent=-3.0`).
    (`test_zamfara_gravity`, `tests/test_run_sim.py:45-47`)
  Both must produce a valid simulation under the standard sanity checks.
- A `max_migr_frac` parameter caps per-step migration fraction (e.g., 0.1) and is
  expected by all spatial sweeps. (`tests_scientific/rand_seed.py:31`,
  `tests_scientific/individual_heterogeneity.py:45`,
  `tests_scientific/sweep_seasonal_amp_doy_zamfara_1y.py:22`)
- A `node_seeding_dispersion` parameter (e.g., `1.0`) controls dispersion in seeding
  across nodes. (`tests_scientific/sweep_seasonal_amp_doy_r0_nigeria_7y.py:33`,
  `tests_scientific/sweep_seasonal_amp_sia_nga_7y.py:33`)
- The simulation supports the multi-state regional filter
  `regions=["NIGERIA:JIGAWA", "NIGERIA:ZAMFARA", "NIGERIA:NIGER"]`, exercising spatial
  coupling across non-contiguous state-level subsets.
  (`tests_scientific/sweep_seasonal_amp_doy_r0_nigeria_7y.py:19`,
  `tests_scientific/sweep_seasonal_amp_sia_nga_7y.py:20`)
- A finer-grained region filter (e.g., `regions=["ZAMFARA:ANKA"]`) restricts the
  simulation to a single LGA-level node. (`tests_scientific/outbreak_size.py:35`)

---

## 8. Background Seeding & Seed Schedules

### Unit-tested
- A background seeding mechanism is supported, configured by:
  - `background_seeding=True`
  - `background_seeding_freq` (e.g., 10 days)
  - `background_seeding_node_frac` (e.g., 0.3 of nodes per event)
  - `background_seeding_prev` (prevalence injected per event)
  The simulation must complete and produce valid result shapes under this mode.
  (`test_zamfara_background_seeding`, `tests/test_run_sim.py:50-59`)
- A dated `seed_schedule` is supported. Each entry is a dict with keys `date` (ISO
  string), `dot_name` (admin path, e.g., `"AFRO:NIGERIA:ZAMFARA:BAKURA"`), and
  `prevalence` (integer count). The simulation must run successfully when given such
  a schedule. (`test_zamfara_seed_schedule`, `tests/test_run_sim.py:62-67`)

### Scientific
- Multi-event `seed_schedule` entries spanning multiple years and multiple admin
  locations are supported (e.g., four entries dated 2017-10-01, 2017-10-01,
  2020-07-01, 2020-10-01 across four LGAs in JIGAWA, ZAMFARA, NIGER).
  (`tests_scientific/sweep_seasonal_amp_doy_r0_nigeria_7y.py:25-30`,
  `tests_scientific/sweep_seasonal_amp_sia_nga_7y.py:26-31`)

---

## 9. Vaccination & Interventions

### 9.1 Routine immunization (RI)
- The model supports a routine immunization component, configured via `vx_prob_ri`.
  Setting `vx_prob_ri=None` skips the RI component entirely without errors.
  (`test_zamfara_vx_prob_ri_none`, `tests/test_run_sim.py:75-78`)
- Setting `vx_prob_ri=0.0` is also supported as an explicit "RI disabled" configuration.
  (`tests_scientific/rand_seed.py:33`,
  `tests_scientific/sweep_seasonal_amp_doy_zamfara_1y.py:23`,
  `tests_scientific/sweep_seasonal_amp_doy_r0_nigeria_7y.py:35`)
- IPV routine immunization is independently toggleable via `ipv_vx` (boolean).
  (`tests_scientific/individual_heterogeneity.py:30`,
  `tests_scientific/outbreak_size.py:42`)
- Build inputs return `ri` (OPV coverage per node) and `ri_ipv` (IPV coverage per node)
  arrays, each of length `n_nodes`. (`test_node_count_consistent`,
  `tests/test_build_inputs.py:64-65`)

### 9.2 SIAs (Supplemental Immunization Activities)
- Build inputs return a `sia_schedule` (list/object) and a per-node `sia_prob` vector,
  plus a `response_sia` structure for outbreak-response campaigns.
  (`REQUIRED_OUTPUT_KEYS`, `tests/test_build_inputs.py:13-28`)
- `vx_prob_sia=None` is a valid configuration meaning "no SIA vaccination."
  (`tests_scientific/individual_heterogeneity.py:29`,
  `tests_scientific/outbreak_size.py:48`)
- An effective-SIA-coverage parameter `sia_re_center` is supported. A value of
  `1e-10` is treated as "no SIA"; a value of `0.5` is treated as "medium-coverage SIA."
  (`tests_scientific/sweep_seasonal_amp_sia_nga_7y.py:14, 178`)
- A `missed_frac` parameter (e.g., 0.1) configures the fraction of agents missed by SIA
  campaigns. (`tests_scientific/rand_seed.py:34`,
  `tests_scientific/sweep_seasonal_amp_doy_zamfara_1y.py:24`)

### Scientific (not CI-enforced)
- The model is expected to show distinct outbreak dynamics across (seasonal_amplitude,
  sia_re_center) combinations. No tolerance is asserted; the comparison is by visual
  inspection of plotted infected / new-potentially-paralyzed time series.
  (`tests_scientific/sweep_seasonal_amp_sia_nga_7y.py:198-228`)

---

## 10. Determinism, Seeds, and Reproducibility

### Unit-tested
- The `seed` parameter is honored by `run_sim` and defaults to a fixed value (1) in
  the Zamfara test fixtures. Re-running with the same seed and config is expected to
  yield identical results (this is the basis for all fast tests asserting fixed
  shapes/counts). (`tests/test_run_sim.py:25`)

### Scientific (not CI-enforced)
- Different seeds must produce different outbreak realisations. The seed sweep runs
  100 reps (`n_reps=100`) over `seed ∈ range(100)` with all other parameters fixed
  (Zamfara, 1 yr, `r0=10`, `init_prev=200`, `missed_frac=0.1`, etc.), and produces a
  histogram of total `new_exposed` values whose spread is expected to be non-trivial.
  (`tests_scientific/rand_seed.py:19-44, 90-96`)
- The expectation is qualitative: outbreak size should vary across seeds (no numeric
  threshold is asserted). (`tests_scientific/rand_seed.py:12`)

---

## 11. Outputs and Reporting

### Unit-tested
- The `sim.results` object exposes (at minimum): `I`, `S`, `new_exposed`,
  `I_by_strain`, `E_by_strain`, `new_exposed_by_strain`, `paralyzed`,
  `detected_paralyzed`, `new_potentially_paralyzed`.
  (`tests/test_run_sim.py:81-87, 105-129`;
  `tests_scientific/individual_heterogeneity.py:90-93`;
  `tests_scientific/sweep_seasonal_amp_doy_r0_nigeria_7y.py:100-101`)
- `sim.nodes` exposes the per-node entities used to derive `n_nodes` for shape checks.
  (`tests/test_run_sim.py:31, 84`)
- `sim.people` exposes per-agent arrays (`acq_risk_multiplier`, `daily_infectivity`)
  when heterogeneity is enabled. (`tests_scientific/individual_heterogeneity.py:96-99`)

### Output files
- When `save_init_pop=True` and a `results_path` is given, an `init_pop.h5` file is
  written in `results_path`. (`tests/test_run_sim.py:140-142`)
- `save_plots` and `save_data` are independent boolean toggles for plot and data
  output. All fast tests set both to `False` for performance.
  (`tests/test_run_sim.py:14-26`)

### Verbosity
- `verbose=0` is a supported quiet mode used by all tests.
  (`tests/test_run_sim.py:22`, `tests_scientific/*`)

---

## 12. Configuration Surface (Aggregate)

The tests collectively assert that the following keyword arguments are accepted by
`lp.run_sim` (and, where noted, by `build_nigeria_inputs` via `configs`):

| Argument | Type/Example | Source |
|---|---|---|
| `build_inputs` | callable, e.g., `build_nigeria_inputs` | `test_run_sim.py:15` |
| `regions` | list of admin strings | many |
| `start_year` | int | many |
| `start_date` | str, ISO date | `test_build_inputs.py:118-121` |
| `n_days` | int | many |
| `init_region` | str | many |
| `init_prev` | int / float | many |
| `init_pop` | float (e.g., 1e6) | `outbreak_size.py:104` |
| `pop_scale` | float | many |
| `r0` | float | many |
| `seed` | int | many |
| `verbose` | int | many |
| `save_plots`, `save_data`, `plot_pars` | bool | many |
| `save_init_pop` | bool | `test_run_sim.py:138` |
| `init_pop_file` | str | `test_run_sim.py:147` |
| `results_path` | str / Path | many |
| `run` | bool (defaults True) | `test_run_sim.py:138` |
| `migration_method` | "radiation" \| "gravity" | `test_run_sim.py:41, 46` |
| `radiation_k_log10` | float | `test_run_sim.py:41` |
| `gravity_k`, `gravity_k_exponent` | float, float | `test_run_sim.py:46` |
| `max_migr_frac` | float | `rand_seed.py:31`, others |
| `node_seeding_dispersion` | float | `sweep_seasonal_amp_doy_r0_nigeria_7y.py:33` |
| `background_seeding` | bool | `test_run_sim.py:54` |
| `background_seeding_freq` | int (days) | `test_run_sim.py:56` |
| `background_seeding_node_frac` | float | `test_run_sim.py:57` |
| `background_seeding_prev` | int | `test_run_sim.py:58` |
| `seed_schedule` | list[dict] or None | `test_run_sim.py:63-66`, many |
| `individual_heterogeneity` | bool | `individual_heterogeneity.py:23` |
| `init_immun_scalar` | float | `individual_heterogeneity.py:22` |
| `r0_scalar_wt_slope`, `r0_scalar_wt_intercept` | float, float | `individual_heterogeneity.py:24-25` |
| `use_pim_scalars` | bool | `test_run_sim.py:71` |
| `seasonal_amplitude` | float | seasonality sweeps |
| `seasonal_peak_doy` | int | seasonality sweeps |
| `cbr` | np.array | `individual_heterogeneity.py:27` |
| `vx_prob_ri` | float or None | `test_run_sim.py:75-78` |
| `vx_prob_sia` | float or None | `individual_heterogeneity.py:29` |
| `ipv_vx` | bool | `individual_heterogeneity.py:30` |
| `missed_frac` | float | `rand_seed.py:34` |
| `sia_re_center` | float | `sweep_seasonal_amp_sia_nga_7y.py:75` |
| `dur_exp`, `dur_inf` | `lp.constant(...)` | `individual_heterogeneity.py:32-33` |
| `paralysis_detection_sensitivity` | float ∈ [0, 1] | `test_run_sim.py:121-122` |
| `p_paralysis` | float | `test_run_sim.py:116` |
| `sia_schedule_source` | "default" \| "none" \| ... | `test_build_inputs.py:99` |

---

## 13. Tested Scenarios as Discrete Requirements

A concise checklist of end-to-end scenarios known to be expected to work:

1. Zamfara, 30 days, radiation migration, default seed, with PIM scalars OR without.
2. Zamfara, 30 days, gravity migration.
3. Zamfara, 30 days, background seeding ON.
4. Zamfara, 30 days, explicit seed_schedule.
5. Zamfara, 30 days, RI disabled (`vx_prob_ri=None`).
6. Zamfara, 30 days, init_pop snapshot save → reload → run.
7. Zamfara, 30 days, perfect and imperfect (0.8) paralysis detection.
8. Nigeria (full), 365 days (slow path).
9. Zamfara, 365 days, seed sweep (100 reps).
10. Zamfara:Anka, 2 years, single-node SIR-equivalent vs Kermack-McKendrick analytic.
11. Zamfara, 30 days, individual-heterogeneity / R0 fidelity test.
12. Three-state Nigeria subset (JIGAWA + ZAMFARA + NIGER), 2 years, full seasonality
    × r0 sweep.
13. Three-state Nigeria subset, 2 years, seasonality × SIA effectiveness sweep.
14. Zamfara, 365 days, seasonality (amplitude × peak DoY) sweep.

---

## 14. Gaps and Open Questions

Behaviors that the tests *suggest* but do not actually verify, or that the test suite
appears to omit:

1. **No explicit determinism test.** No test asserts that two `lp.run_sim` calls with
   the same seed produce identical results (it is *assumed* by the use of fixed
   `seed=1` in `ZAMFARA_BASE`, but never explicitly checked). A `sim_a == sim_b`
   regression test for given seed would harden the reproducibility claim.
2. **R0 ↔ outbreak-size scaling.** The Kermack-McKendrick check
   (`tests_scientific/outbreak_size.py`) is a script with no `assert`; the comparison
   is by inspection of saved plots. No CI signal will catch a regression in final-size
   accuracy.
3. **Heterogeneity R0 fidelity (atol=7).** The single hard assertion in
   `individual_heterogeneity.py` (`np.isclose(np.mean(E_final), 14, atol=7)`) is very
   loose; values in [7, 21] all pass. Whether this matches the intended precision is
   worth confirming.
4. **Seasonality is never quantitatively asserted.** All seasonality sweep scripts
   produce plots; none enforce that the simulated peak shifts with `seasonal_peak_doy`,
   or that amplitude scales the trough/peak ratio. The "scientific" expectations
   (e.g., "peak time should shift with `seasonal_peak_doy`", "outbreak size should
   change monotonically with amplitude at fixed R0") are only implicitly inspected.
5. **SIA efficacy is never quantitatively asserted.** The SIA × seasonality sweep
   does not assert that `sia_re_center=0.5` reduces cumulative infections vs
   `sia_re_center=1e-10`; it merely plots both.
6. **`background_seeding_node_frac` semantics not verified.** The test calls the
   API with this argument but does not check that the expected fraction of nodes are
   actually re-seeded over time.
7. **Detection sensitivity is only checked at the final timestep.**
   `test_imperfect_diagnosis_runs` compares `detected_paralyzed[-1].sum() <=
   paralyzed[-1].sum()`, but does not verify that the *ratio* of detected-to-true
   tracks the configured sensitivity, nor that the inequality holds at every
   intermediate timestep.
8. **`use_pim_scalars=True` runs but is not compared to `False`.**
   `test_zamfara_pim_scalars` only verifies that the run completes. There is no
   regression check that the two modes produce numerically different (and
   appropriately different) results.
9. **`gravity_k` and `radiation_k_log10` are tested at single hard-coded values.**
   No test sweeps these to verify expected monotonic behavior (e.g., higher migration
   → faster spatial spread).
10. **`init_pop_file` correctness.** The snapshot roundtrip test verifies that the
    loaded sim *runs*, but does not verify that the loaded population matches the
    saved population, nor that subsequent dynamics are equivalent to a same-seed run
    without snapshot. This means a corruption-on-save bug could go undetected.
11. **`age_pyramid_path` injection side effect.** The test verifies the key is
    injected into `configs` but does not verify that downstream `run_sim` honors it
    or that the resulting age distribution matches the pyramid file.
12. **No test for `start_date` invariants when both `start_year` and `start_date` are
    given.** Only one or the other is tested in isolation. Conflict-resolution rules
    are unspecified.
13. **No test for the default SIA schedule's content.** `test_sia_schedule_default_not_empty`
    only checks `len > 0`; the comment notes that "synthetic schedule has mOPV2
    campaigns in odd years only", but no test verifies that property directly.
14. **No coverage of `response_sia`.** It is in `REQUIRED_OUTPUT_KEYS` but no test
    exercises its semantics.
15. **No coverage of `sus_by_age_node`.** Same: required output key, no behavioral
    assertion.
16. **Strain index 0 = VDPV2 is a convention** used by many scientific scripts but
    is never asserted or enforced by the unit tests. A reordering of strains in the
    underlying library would silently break analysis scripts.
17. **No regression test on Nigeria-scale full-year results.** `test_nigeria_full_year`
    only checks shape (`sim.nt == 366`, `n_nodes > 0`). Total infections, peak timing,
    or any qualitative property is unchecked.
18. **`p_paralysis` is only tested indirectly.** It is passed in the imperfect-diagnosis
    test but no assertion checks that the paralysis rate among infections matches it.
19. **No explicit test of `dur_exp` / `dur_inf` distribution semantics.** They are
    used with `lp.constant(...)` only; whether non-constant distributions (e.g.,
    exponential or gamma) are supported and produce the expected mean durations is
    not covered.
