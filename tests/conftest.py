import os
from pathlib import Path

# Set LASER_POLIO_DATA before any test imports, so load_manifest() works
# without requiring the env var to be set in the shell.
# Can be overridden by setting LASER_POLIO_DATA in the environment.
_repo_root = Path(__file__).parent.parent
os.environ.setdefault("LASER_POLIO_DATA", str(_repo_root / "nigeria_polio_data"))
