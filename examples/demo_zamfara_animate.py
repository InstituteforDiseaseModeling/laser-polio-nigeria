import numpy as np
import sciris as sc

import laser_polio as lp
from laser_polio_nigeria.run_sim import build_nigeria_inputs
from laser_polio.utils import prep_actual_data_for_calibration

###################################
######### USER PARAMETERS #########

regions = ["ZAMFARA"]
start_year = 2018
n_days = 365
pop_scale = 1 / 1
init_region = "ANKA"
init_prev = 200
r0 = 14
migration_method = "radiation"
radiation_k_log10 = -0.3
max_migr_frac = 0.1
verbose = 1
vx_prob_ri = 0.0
missed_frac = 0.1
# seed_schedule = [
#     {"date": "2018-01-02", "dot_name": "AFRO:NIGERIA:ZAMFARA:BAKURA", "prevalence": 200},  # day 1
#     {"date": "2018-11-07", "dot_name": "AFRO:NIGERIA:ZAMFARA:GUMMI", "prevalence": 200},  # day 2
# ]
save_plots = False
animate_plots = False
save_data = False
plot_pars = False
seed = 1
# Diffs from demo_zamfara_load_init_pop.py
results_path = "results/demo_zamfara"
save_init_pop = False
init_pop_file = None


######### END OF USER PARS ########
###################################

actual_data = prep_actual_data_for_calibration(
    regions=regions,
    admin_level=None,
    start_year=start_year,
    n_days=n_days,
    pop_scale=pop_scale,
    results_path=results_path,
    save_csv=False,
)
# Sum actual data by month
actual_data_monthly = np.asarray(actual_data.groupby("month_start").sum("P").reset_index()["P"])
actual_data_monthly[[1, 5, 6]] = [1, 2, 3]
actual_data_monthly = np.insert(actual_data_monthly, 0, 0)

sim = lp.run_sim(
    build_inputs=build_nigeria_inputs,
    regions=regions,
    start_year=start_year,
    n_days=n_days,
    pop_scale=pop_scale,
    init_region=init_region,
    init_prev=init_prev,
    results_path=results_path,
    save_plots=save_plots,
    animate_plots=animate_plots,
    save_data=save_data,
    plot_pars=plot_pars,
    verbose=verbose,
    seed=seed,
    r0=r0,
    migration_method=migration_method,
    radiation_k_log10=radiation_k_log10,
    max_migr_frac=max_migr_frac,
    save_init_pop=save_init_pop,
    vx_prob_ri=vx_prob_ri,
    init_pop_file=init_pop_file,
    # seed_schedule=seed_schedule,
    missed_frac=missed_frac,
    use_pim_scalars=True,
)


lp.animate_maps_plus_series(
    incidence_TNK=sim.results.I_by_strain,  # shape (T, N, K) : infections by node & strain
    gdf=sim.pars.shp,  # GeoDataFrame length N, already ordered to match N
    actual_monthly=actual_data_monthly,
    pred_T=np.sum(sim.results.I_by_strain[:, :, 0], axis=1) / 2000,
    time_labels=sim.datevec,
    strain_names=sim.pars["strain_ids"].keys(),
    fps=10,
    dpi=160,
    cmap="viridis",
    log=False,
    fig_width_per_panel=4.0,
    fig_height=6.0,
    out_path=f"{results_path}/animated.mp4",
)

sc.printcyan("Done.")
