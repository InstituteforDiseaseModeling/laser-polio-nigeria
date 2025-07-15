from COMPS import Client
from COMPS.Data import Experiment, Simulation
import os
import sys

EXPERIMENT_ID = sys.argv[1]

Client.login("https://comps.idmod.org")

exp = Experiment.get(EXPERIMENT_ID)

for sim in exp.get_simulations():
    print(f"Downloading files for sim: {sim.id}")
    
    outdir = os.path.join(f"experiment_{EXPERIMENT_ID}", f"simulation_{sim.id}", "output")
    os.makedirs(outdir, exist_ok=True)

    Simulation.download_files(sim.id, "output/*", outdir, show_progress=True)
