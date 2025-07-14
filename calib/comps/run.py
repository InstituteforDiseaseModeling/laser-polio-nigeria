import os
import sys

from idmtools.assets import AssetCollection
from idmtools.core.platform_factory import Platform
from idmtools.entities import CommandLine
from idmtools.entities.command_task import CommandTask
from idmtools.entities.experiment import Experiment

if __name__ == "__main__":
    here = os.path.dirname(__file__)

    # Create a platform to run the workitem
    platform = Platform("SLURM_Prod")

    # create commandline input for the task
    #command = CommandLine("singularity exec --home /app --pwd /app ./Assets/laser-polio_latest.sif python3 -m laser_polio.run_sim --model-config calib/model_configs/config_zamfara.yaml")
    #command = CommandLine("singularity exec --home /app --pwd /app ./Assets/laser-polio_latest.sif python3 -m laser_polio.run_sim --help")
    #command = CommandLine("singularity exec --home /app --pwd /app ./Assets/laser-polio_latest.sif ls -la")
    #command = CommandLine("singularity exec --home /app --pwd /app ./Assets/laser-polio_latest.sif pwd")
    #command = CommandLine("singularity exec --containall --no-home --no-mount /app Assets/laser-polio_latest.sif ls -la /app" )
    
    command = CommandLine(f"singularity exec --no-mount /app Assets/laser-polio_latest.sif python3 -m laser_polio.run_sim --model-config /app/calib/model_configs/config_zamfara.yaml --params-file Assets/overrides.json" )
    #command = CommandLine("singularity exec --home /app ./Assets/laser-polio_latest.sif bash -c 'cd /app && python3 -m laser_polio.run_sim --model-config calib/model_configs/config_zamfara.yaml'")
    task = CommandTask(command=command)
    # Add our image
    task.common_assets.add_assets(AssetCollection.from_id_file("laser.id"))
    task.common_assets.add_directory( "overrides" )

    experiment = Experiment.from_task(
        task,
        name=os.path.split(sys.argv[0])[1],
        tags=dict(type='singularity', description='laser')
    )
    experiment.run(wait_until_done=True)
    if experiment.succeeded:
        experiment.to_id_file("experiment.id")
