import sciris as sc

import laser_polio as lp
from laser_polio_nigeria.run_sim import build_nigeria_inputs

###################################
######### USER PARAMETERS #########

config = {
    "regions": ["ZAMFARA"],
    "start_year": 2018,
    "n_days": 365,
    "pop_scale": 1 / 1,
    "init_region": "ANKA",
    "init_prev": 200,
    "r0": 14,
    "migration_method": "radiation",
    "radiation_k_log10": -0.3,
    "max_migr_frac": 0.1,
    "vx_prob_ri": 0.0,
    "missed_frac": 0.1,
    "p_paralysis": 1 / 20,
    "results_path": "results/demo_zamfara",
    "save_plots": True,
    "animate_plots": False,
    "save_data": True,
}
verbose = 0
plot_pars = True
use_pim_scalars = True

######### END OF USER PARS ########
###################################


sim = lp.run_sim(
    **config,
    build_inputs=build_nigeria_inputs,
    verbose=verbose,
    plot_pars=plot_pars,
    use_pim_scalars=use_pim_scalars,
)

sc.printcyan("Done.")
