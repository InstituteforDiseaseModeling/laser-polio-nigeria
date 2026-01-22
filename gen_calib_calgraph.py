from pyan import CallGraphVisitor, output_dot
import sys
import os

# List your input files explicitly
input_files = [
    "calib/calib_db.py",
    "calib/calibrate.py",
    "calib/find_n_nigeria_nodes.py",
    "calib/get_lp_module_versions.py",
    "calib/objective.py",
    "calib/report.py",
    "calib/run_calib_docker_local.py",
    "calib/scoring.py",
    "calib/targets.py",
    "calib/worker.py",
]

# Create the call graph visitor
visitor = CallGraphVisitor(
    input_files,
    log=None,
    root=None,
    defines=False,
    uses=True,
    colored=True,
    grouped=True
)

# Generate DOT output
with open("callgraph.dot", "w") as f:
    output_dot(visitor, f)
