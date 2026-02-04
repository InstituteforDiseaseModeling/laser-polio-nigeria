from pathlib import Path
import click
import numpy as np
import pandas as pd
import sciris as sc
import yaml

import geopandas as gpd

import laser_polio as lp
from laser_polio.run_sim import run_sim
from laser_polio.manifest_loader import load_manifest

manifest = load_manifest()

def build_nigeria_inputs( configs, verbose ):
    # Extract simulation setup parameters with defaults or overrides
    regions = configs.pop("regions", ["ZAMFARA"])
    admin_level = configs.pop("admin_level", None)  # level to match region strings against: None: dot_name, 0: adm0, 1: adm1, 2: adm2
    start_year = configs.pop("start_year", 2018)
    n_days = configs.pop("n_days", 365)
    pop_scale = configs.pop("pop_scale", 1)
    init_region = configs.pop("init_region", "ANKA")
    init_prev = configs.pop("init_prev", 0.01)
    results_path = configs.pop("results_path", "results/demo")
    animate_plots = configs.pop("animate_plots", False)
    use_pim_scalars = configs.pop("use_pim_scalars", False)
    init_immun_scalar = configs.pop("init_immun_scalar", 1.0)
    pim_re_center = configs.pop("pim_re_center", 0.0)
    pim_re_scale = configs.pop("pim_re_scale", 1.0)
    r0_scalar_wt_slope = configs.pop("r0_scalar_wt_slope", 24)
    r0_scalar_wt_intercept = configs.pop("r0_scalar_wt_intercept", 0.2)
    r0_scalar_wt_center = configs.pop("r0_scalar_wt_center", 0.22)
    sia_re_center = configs.pop("sia_re_center", 0.5)
    sia_re_scale = configs.pop("sia_re_scale", 1.0)
    response_sia = configs.pop("response_sia", False)
    ipv_vx = configs.pop("ipv_vx", True)  # If True, backcalculate IPV protections

    # Setup results path
    if results_path is None:
        results_path = Path("results/default")  # Provide a default path
    Path(results_path).mkdir(parents=True, exist_ok=True)
    results_path = Path(results_path)

    # Geography
    dot_names = lp.find_matching_dot_names( regions, manifest.population, verbose=verbose, admin_level=admin_level)
    node_lookup = lp.get_node_lookup(manifest.node_lookup, dot_names)
    shp = gpd.read_file(filename=manifest.shapefile, layer="adm2")
    shp = shp[shp["dot_name"].isin(dot_names)]
    # Sort the GeoDataFrame by the order of dot_names
    shp.set_index("dot_name", inplace=True)
    shp = shp.loc[dot_names].reset_index()
    # Check that the ordering is correct
    node_lookup_dot_names = [node_lookup[i]["dot_name"] for i in sorted(node_lookup.keys())]
    assert np.all(node_lookup_dot_names == dot_names), "Node lookup dot names do not match dot names"
    shp_dot_names = shp["dot_name"].tolist()
    assert np.all(shp_dot_names == dot_names), "shp dot names do not match dot names"

    # Initial infection seeding
    init_prevs = np.zeros(len(dot_names))
    prev_indices = [i for i, dot_name in enumerate(dot_names) if init_region in dot_name]
    if not prev_indices:
        raise ValueError(f"No nodes found containing '{init_region}'")
    init_prevs[prev_indices] = init_prev
    # Make dtype match init_prev type
    if isinstance(init_prev, int):
        init_prevs = init_prevs.astype(int)
    if verbose >= 2:
        print(f"Seeding infection in {len(prev_indices)} nodes at {init_prev:.3f} prevalence.")

    # Demographics and risk
    df_comp = pd.read_csv(manifest.population)
    df_comp = df_comp[df_comp["year"] == start_year]
    pop = (df_comp.set_index("dot_name").loc[dot_names, "pop_total"].values * pop_scale).astype(int)
    cbr = df_comp.set_index("dot_name").loc[dot_names, "cbr"].values

    # ---Setup R0 spatial scalars

    if use_pim_scalars:
        # Scale PIM random effects
        def zscore(x, mu=0.154, sd=1.112):
            # Standardize the random effects
            # May not be necessary
            return (x - mu) / sd

        def transform_exp(x, a=0.0, b=0.446):
            """
            Exponential transformation of random effects
            Args:
                x: Random effects to transform
                a: Intercept. Set to 0 to center the transformation around 1.0
                b: Slope parameter. For a 1 SD increase in the random effect, the multiplier changes by a factor of
                exp(b). For example, if b=0.3, then moving 1 SD above the mean multiplies the scalar by exp(0.3)≈1.35.
            Returns:
                Exponential transformed values
            """
            z = zscore(x)
            return np.exp(a + b * z)

        pim_re = df_comp["reff_random_effect"].values  # get all values
        pim_scaled = transform_exp(pim_re, a=pim_re_center, b=pim_re_scale)
        df_comp.loc[:, "pim_scaled"] = pim_scaled
        r0_scalars = df_comp.set_index("dot_name").loc[dot_names, "pim_scaled"].values

        # pim_re = df_comp["reff_random_effect"].values  # get all values
        # # nig_min = -0.0786359245626656
        # # nig_max = 2.200145038240859
        # # pim_scaled = (pim_re - nig_min) / (nig_max - nig_min)
        # # pim_scaled = (pim_re - pim_re.min()) / (pim_re.max() - pim_re.min())  # Rescale to [0, 1]
        # df_comp.loc[:, "pim_scaled"] = pim_scaled
        # pim_scaled = df_comp.set_index("dot_name").loc[dot_names, "pim_scaled"].values
        # r0_scalars = pim_scaled * (r0_scalars_wt.max() - r0_scalars_wt.min()) + r0_scalars_wt.min()

    else:
        # Scale underweight proportions
        underwt = df_comp.set_index("dot_name").loc[dot_names, "prop_underwt"].values
        r0_scalars = (
            1 / (1 + np.exp(r0_scalar_wt_slope * (r0_scalar_wt_center - underwt)))
        ) + r0_scalar_wt_intercept  # The 0.22 is the mean of Nigeria underwt

    # --- Setup vaccination interventions ---

    # Routine immunization probabilities
    ri = df_comp.set_index("dot_name").loc[dot_names, "ri_eff"].values
    ri_ipv = df_comp.set_index("dot_name").loc[dot_names, "dpt3"].values
    # SIA probabilities
    sia_re = df_comp.set_index("dot_name").loc[dot_names, "sia_random_effect"].values
    sia_prob = lp.calc_sia_prob_from_rand_eff(sia_re, center=sia_re_center, scale=sia_re_scale)
    # SIA scheduled
    start_date = lp.date(f"{start_year}-01-01")
    # historic = pd.read_csv(lp.root / "data/sia_historic_schedule.csv")
    # future = pd.read_csv(lp.root / "data/sia_scenario_1.csv")
    # sia_schedule = lp.process_sia_schedule_polio(pd.concat([historic, future]), dot_names, start_date, n_days, filter_to_type2=True)

    # ---- SIA schedule options ----
    sia_source = configs.pop("sia_schedule_source", "default")  # "default" | "files" | "n_per_year" | "none"
    sia_files = configs.pop("sia_schedule_files", None)
    sia_n = int(configs.pop("sia_campaigns_per_year", 0) or 0)
    sia_months = configs.pop("sia_campaign_months", None)  # e.g., [3, 9]
    campaign_day = int(configs.pop("sia_campaign_day", 1))  # day-of-month for campaigns
    filter_to_type2 = bool(configs.pop("sia_filter_to_type2", True))
    age_range = configs.pop("sia_age_range", (0.0, 1825.0))
    vaccine_strain = configs.pop("vaccine_strain", "Sabin2")
    vaccinetype_after_2021 = configs.pop("vaccinetype_after_2021", "nOPV2")  # used when year > 2021

    def build_sia_schedule():
        # Default: keep current behavior
        if sia_source in ("default", "historic+scenario1"):
            historic = pd.read_csv(manifest.sia_historic)
            future = pd.read_csv(manifest.sia_future)
            sched = pd.concat([historic, future], ignore_index=True)
            return lp.process_sia_schedule_polio(sched, dot_names, start_date, n_days, filter_to_type2=filter_to_type2)

        # Load arbitrary calendar files
        if sia_source == "files":
            if not sia_files:
                raise ValueError("sia_schedule_source='files' requires sia_schedule_files=[...]")
            frames = [pd.read_csv(Path(f)) for f in sia_files]
            sched = pd.concat(frames, ignore_index=True)
            return lp.process_sia_schedule_polio(sched, dot_names, start_date, n_days, filter_to_type2=filter_to_type2)

        # Generate N uniform campaigns per year (e.g., 1x or 2x)
        if sia_source == "n_per_year":
            if sia_n <= 0:
                raise ValueError("Provide sia_campaigns_per_year (e.g., 1 or 2) when using 'n_per_year'.")
            # Default months: 1x → June; 2x → Mar & Sep; otherwise evenly spaced
            months = sia_months if sia_months is not None else []
            if not months:
                if sia_n == 1:
                    months = [6]
                elif sia_n == 2:
                    months = [3, 9]
                else:
                    step = 12 / sia_n
                    months = sorted({round(1 + i * step) for i in range(sia_n)})

            # Build date range boundaries as datetime.date
            start_ts = pd.Timestamp(start_date)
            end_ts = start_ts + pd.Timedelta(days=n_days)
            start_d, end_d = start_ts.date(), end_ts.date()

            # Generate datetime.date campaign dates
            dates = []
            year = start_d.year
            while dt_date(year, 1, 1) < end_d:
                for m in months:
                    # Clamp campaign_day to the last valid day of the month
                    dom = min(campaign_day, monthrange(year, m)[1])
                    d = dt_date(year, m, dom)
                    if start_d <= d < end_d:
                        dates.append(d)
                year += 1

            # Nodes index: [0, 1, ..., len(nodes)-1]
            nodes_index = list(range(len(dot_names)))

            # Build the list of dictionaries, one per date
            sia_schedule = []
            for d in dates:
                vt = "mOPV2" if d.year <= 2021 else vaccinetype_after_2021
                sia_schedule.append(
                    {
                        "date": d,  # datetime.date(YYYY, M, D)
                        "age_range": age_range,  # default (0.0, 1825.0)
                        "vaccinetype": vt,  # 'mOPV2' unless year > 2021
                        "nodes": nodes_index,  # [0 .. len(nodes)-1]
                        "vaccine_strain": vaccine_strain,  # 'Sabin2'
                    }
                )

            return sia_schedule

        if sia_source == "none":
            return None  # no campaigns

        raise ValueError(f"Unknown sia_schedule_source: {sia_source}")

    # Use the factory
    sia_schedule = build_sia_schedule()

    # --- Calculate the number of initial susceptible people ---

    # Load the age pyramid
    age_pyramid = lp.load_age_pyramid(manifest.age_pyramid)
    age_pyramid["age_min_months_pyramid"] = age_pyramid["age_min"] * 12  # Convert to months
    age_pyramid["age_max_months_pyramid"] = age_pyramid["age_max"] * 12  # Convert to months
    age_pyramid = age_pyramid.drop(columns=["age_min", "age_max"])
    age_pyramid = age_pyramid.rename(columns={"pop_frac": "pop_frac_pyramid"})

    # Immunity
    init_immun = pd.read_hdf(manifest.init_immunity, key="immunity")
    init_immun = init_immun.set_index("dot_name").loc[dot_names]
    init_immun = init_immun[init_immun["period"] == start_year]
    # Set immunity for 15+ to 1.0
    init_immun.loc[:, "immunity_180_1200"] = 1.0

    # Wide → Long
    init_immun_long = init_immun.reset_index().melt(
        id_vars="dot_name",
        value_vars=[col for col in init_immun.columns if col.startswith("immunity_")],
        var_name="age_bin",
        value_name="immune_frac",
    )
    # Parse age bins into min/max months
    init_immun_long[["age_min_months_immun", "age_max_months_immun"]] = init_immun_long["age_bin"].str.extract(r"immunity_(\d+)_(\d+)")
    init_immun_long[["age_min_months_immun", "age_max_months_immun"]] = init_immun_long[
        ["age_min_months_immun", "age_max_months_immun"]
    ].astype(int)
    init_immun_long["age_max_months_immun"] += 1  # Make age_max exclusive
    init_immun_long = init_immun_long.drop(columns=["age_bin"])
    # Perform a cross join and filter down to rows where the bins overlap
    # Add temporary join key for cross-join
    init_immun_long["key"] = 1
    age_pyramid["key"] = 1
    # Cross join: all age bins for all pyramid bins
    age_merged = pd.merge(init_immun_long, age_pyramid, on="key").drop("key", axis=1)
    # Filter to overlapping age bins (i.e., where any overlap exists)
    # This logic matches: (start1 < end2) & (start2 < end1)
    age_merged = age_merged[
        (age_merged["age_min_months_immun"] < age_merged["age_max_months_pyramid"])
        & (age_merged["age_max_months_immun"] > age_merged["age_min_months_pyramid"])
    ]
    # Compute the overlap width (in months)
    age_merged["overlap_months"] = (
        np.minimum(age_merged["age_max_months_immun"], age_merged["age_max_months_pyramid"])
        - np.maximum(age_merged["age_min_months_immun"], age_merged["age_min_months_pyramid"])
    ).clip(lower=0)
    # Calculate overlap weight as fraction of the pyramid bin
    age_merged["weight"] = age_merged["overlap_months"] / (age_merged["age_max_months_pyramid"] - age_merged["age_min_months_pyramid"])
    age_merged.drop(
        columns=["pop"], inplace=True
    )  # Drop the pop column since this is for all of Nigeria. We'll replace with node-level total pop below
    # Attach pop data and node id
    node_info = pd.DataFrame(
        {
            "node_id": sorted(node_lookup.keys()),
            "dot_name": dot_names,
            "pop_total": pop,
        }
    )
    age_merged = age_merged.merge(node_info, on="dot_name", how="left")
    # Adjust population count in that bin accordingly
    age_merged["pop_in_age_bin"] = age_merged["pop_total"] * age_merged["pop_frac_pyramid"] * age_merged["weight"]
    # Compute immune/susceptible counts
    age_merged["n_immune"] = age_merged["pop_in_age_bin"] * age_merged["immune_frac"]
    age_merged["n_susceptible"] = age_merged["pop_in_age_bin"] * (1 - age_merged["immune_frac"])
    # Group and summarize
    sus_by_age_node = (
        age_merged.groupby(["dot_name", "node_id", "age_min_months_immun", "age_max_months_immun"])[["n_susceptible", "n_immune"]]
        .sum()
        .round()
        .astype(int)
        .reset_index()
    )
    # Sum by dot_name
    immun_summary = sus_by_age_node.groupby("dot_name")[["n_immune", "n_susceptible"]].sum()
    # Account for rounding errors & handle them in the oldest age bin
    pop_diff = np.array(pop) - np.array(immun_summary["n_immune"].values) - np.array(immun_summary["n_susceptible"].values)
    sus_by_age_node.loc[sus_by_age_node["age_max_months_immun"] == 1201, "n_immune"] += pop_diff
    # Re-calculate the immune & susceptible counts
    immun_summary = sus_by_age_node.groupby("dot_name")[["n_immune", "n_susceptible"]].sum()
    # Convert age_min_months_immun to years
    sus_by_age_node["age_min_yr"] = sus_by_age_node["age_min_months_immun"] / 12
    # Convert age_max_months_immun to years
    sus_by_age_node["age_max_yr"] = sus_by_age_node["age_max_months_immun"] / 12
    # Drop age_min_months_immun and age_max_months_immun
    sus_by_age_node = sus_by_age_node.drop(columns=["age_min_months_immun", "age_max_months_immun"])
    sus_summary = sus_by_age_node.groupby("dot_name")["n_susceptible"].sum().astype(int)

    # Sanity checks
    assert np.all(age_merged["immune_frac"] <= 1.0), "Immunity fraction exceeds 1.0"
    assert np.all(age_merged["immune_frac"] >= 0.0), "Negative immunity fraction"
    assert np.all(age_merged["pop_in_age_bin"] >= 0.0), "Negative population in age bin"
    assert np.all(age_merged["n_immune"] >= 0.0), "Negative immune count"
    assert np.all(age_merged["n_susceptible"] >= 0.0), "Negative susceptible count"
    assert np.all(immun_summary["n_immune"] + immun_summary["n_susceptible"] <= pop), (
        "Immune + susceptible counts are greater than population counts"
    )
    assert np.all(sus_summary <= pop), "Susceptible counts are greater than population counts"
    assert np.all(sus_by_age_node["n_immune"] >= 0.0), "Negative immune count"
    assert np.all(sus_by_age_node["n_susceptible"] >= 0.0), "Negative susceptible count"

    # ---- Backcalculate RI IPV Protection ----

    # IPV prevents paralysis but does not block transmission.
    # Since IPV and OPV immunity groups are assumed to overlap, and OPV-protected individuals
    # were already marked as Recovered (i.e., immune to both transmission and paralysis),
    # we only need to assign IPV protection to those who are not already immune.
    # Therefore, IPV protection is only applied when IPV coverage exceeds OPV-derived immunity.
    # Initialize IPV protection column
    sus_by_age_node["n_ipv_protected"] = 0
    # Check if IPV parameters are available
    if ipv_vx and ri_ipv is not None and len(ri_ipv) > 0:
        # IPV eligibility threshold (must be born after ipv_start_year) + 98 days (roughly the timing of 2nd dose of RI IPV (+ 3rd dose of OPV))
        # Convert to years for comparison with age bins
        ipv_start_year = configs.get("ipv_start_year", 2015)  # Default IPV start year is 2015
        max_age_for_ipv_years = start_date.year - ipv_start_year + (98 / 365)
        # Create mapping from dot_name to ri_ipv coverage
        ipv_coverage_map = dict(zip(dot_names, ri_ipv, strict=False))
        # IPV minimum age threshold in years (98 days)
        ipv_min_age_years = 98 / 365
        # Calculate IPV protection for each row in sus_by_age_node
        for idx, row in sus_by_age_node.iterrows():
            dot_name = row["dot_name"]
            age_min_yr = row["age_min_yr"]
            age_max_yr = row["age_max_yr"]
            n_susceptible = row["n_susceptible"]
            n_immune = row["n_immune"]
            # Check if this age bin has any overlap with IPV eligibility
            if age_max_yr >= ipv_min_age_years and age_min_yr <= max_age_for_ipv_years:
                # Get IPV coverage for this node
                vx_prob_ipv = ipv_coverage_map.get(dot_name, 0)
                if vx_prob_ipv > 0:
                    # Calculate total population in this age bin
                    total_pop = n_susceptible + n_immune
                    if total_pop > 0:
                        # Calculate the proportion of this age bin that's eligible for IPV
                        # Eligible age range: [ipv_min_age_years, max_age_for_ipv_years]
                        # Age bin range: [age_min_yr, age_max_yr]

                        # Find the overlap between eligible age range and age bin
                        overlap_min = max(age_min_yr, ipv_min_age_years)
                        overlap_max = min(age_max_yr, max_age_for_ipv_years)

                        if overlap_max > overlap_min:
                            # Calculate eligible fraction within this age bin
                            age_bin_width = age_max_yr - age_min_yr
                            overlap_width = overlap_max - overlap_min
                            eligible_fraction = overlap_width / age_bin_width if age_bin_width > 0 else 0

                            # Current immune fraction in this age bin
                            immune_fraction = n_immune / total_pop

                            # IPV gap: additional protection beyond existing immunity
                            ipv_gap = max(0, vx_prob_ipv - immune_fraction)

                            # Apply IPV protection to eligible portion only
                            # IPV protects against paralysis but not transmission, so these remain susceptible for transmission
                            eligible_pop = total_pop * eligible_fraction
                            eligible_susceptible = n_susceptible * eligible_fraction
                            n_ipv_protected = min(eligible_susceptible, eligible_pop * ipv_gap)
                            sus_by_age_node.loc[idx, "n_ipv_protected"] = int(n_ipv_protected)
    # Sanity checks
    assert np.all(sus_by_age_node["n_ipv_protected"] >= 0.0), "Negative IPV protected count"

    # Validate all arrays match
    assert all(len(arr) == len(dot_names) for arr in [shp, node_lookup, init_prevs, pop, cbr, ri, ri_ipv, sia_prob, r0_scalars])

    return {
        "start_date": start_date,
        "n_days": n_days,
        "pop": pop,
        "sus_by_age_node": sus_by_age_node,
        "cbr": cbr,
        "init_prevs": init_prevs,
        "r0_scalars": r0_scalars,
        "shp": shp,
        "node_lookup": node_lookup,
        "ri": ri,
        "ri_ipv": ri_ipv,
        "sia_schedule": sia_schedule,
        "sia_prob": sia_prob,
        "response_sia": response_sia,
    }


run_sim(
    config={
        "regions": ["ZAMFARA"],
        "n_days": 365,
    },
    build_inputs=build_nigeria_inputs,
)
