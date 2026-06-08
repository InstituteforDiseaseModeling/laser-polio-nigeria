"""Nigeria-specific LASER-POLIO modeling, scenarios, and analysis.

On import, load machine-specific settings (notably ``LASER_POLIO_DATA``) from
the repo's ``.env`` file so simulations work from any terminal without manual
exports. Real environment variables always take precedence, so this is a no-op
on AKS / in containers where the orchestrator sets ``LASER_POLIO_DATA`` directly.
"""

import os
from pathlib import Path


def _load_dotenv(path: Path) -> None:
    """Minimal ``KEY=VALUE`` .env loader (no dependencies).

    Existing environment variables win, so a value injected by the shell or by
    Kubernetes is never overridden by ``.env``.
    """
    if not path.exists():
        return
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):  # tolerate `export KEY=VALUE`
            line = line[len("export ") :].lstrip()
        key, sep, value = line.partition("=")
        if not sep:
            continue
        key = key.strip()
        # Strip an inline comment and surrounding quotes from the value.
        value = value.split(" #", 1)[0].strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


# Walk up from this file (src/laser_polio_nigeria/__init__.py) to the repo root.
_load_dotenv(Path(__file__).resolve().parents[2] / ".env")
