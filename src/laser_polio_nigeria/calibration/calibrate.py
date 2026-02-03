from laser_polio_calibration.core.calibrate import main
from laser_polio_nigeria.calibration.build_inputs import build_calibrate_nigeria_inputs

def run():
    main(
        study_name="calib_nigeria_test",
        model_config="nigeria_7y_2017_regions_gravity_ssn_nozi_pim.yaml",
        calib_config="r0.yaml",
        config_root="config",
        fit_function="log_likelihood",
        n_replicates=1,
        n_trials=1,
        results_path=None,
        actual_data_file=None,
        dry_run=False,
        build_inputs=build_calibrate_nigeria_inputs,  # 👈 the only wiring
    )

if __name__ == "__main__":
    run()
