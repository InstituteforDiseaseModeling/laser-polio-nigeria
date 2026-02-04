from laser_polio_nigeria.run_sim import build_nigeria_inputs


def build_calibrate_nigeria_inputs(configs, verbose):
    """
    Calibration wrapper around Nigeria inputs.
    Applies calibration-only transforms.
    """
    inputs = build_nigeria_inputs(configs, verbose)

    # --- R0 scaling (Optuna-controlled) ---
    r0_scalar_multiplier = configs.pop("r0_scalar_multiplier", None)
    if r0_scalar_multiplier is not None:
        inputs["r0_scalars"] = inputs["r0_scalars"] * r0_scalar_multiplier

    # --- Immunity scaling (Optuna-controlled) ---
    init_immun_scalar = configs.pop("init_immun_scalar", None)
    if init_immun_scalar is not None:
        df = inputs["sus_by_age_node"].copy()
        total = df["n_susceptible"] + df["n_immune"]
        immune_frac = df["n_immune"] / total
        scaled = (immune_frac * init_immun_scalar).clip(0, 1)
        df["n_immune"] = (total * scaled).astype(int)
        df["n_susceptible"] = total - df["n_immune"]
        inputs["sus_by_age_node"] = df

    return inputs
