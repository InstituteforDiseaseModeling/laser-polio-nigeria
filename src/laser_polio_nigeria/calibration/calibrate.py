import argparse
from laser_polio_calibration.core.calibrate import main
from laser_polio_calibration.core.cli_args import add_common_calibration_args
from laser_polio_nigeria.calibration.build_inputs import build_calibrate_nigeria_inputs


def run():
    parser = argparse.ArgumentParser()
    add_common_calibration_args(parser)
    args = parser.parse_args()

    main(
        study_name=args.study_name,
        model_config=args.model_config,
        calib_config=args.calib_config,
        config_root=args.config_root,
        fit_function=args.fit_function,
        n_replicates=args.n_replicates,
        n_trials=args.n_trials,
        results_path=None,
        actual_data_file=None,
        dry_run=args.dry_run,
        build_inputs=build_calibrate_nigeria_inputs,
    )


if __name__ == "__main__":
    run()
