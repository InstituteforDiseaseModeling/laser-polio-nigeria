"""Nigeria-specific manifest loader.

Owns the filename->variable contract for this consumer: every data file we
need from ``nigeria_polio_data`` is declared here with the name our model
code references it by. Independent of the producer (``nigeria_polio``) so a
user with just a folder of files — no Artifactory credentials, no installed
``nigeria_polio`` package — can still run the model by setting
``LASER_POLIO_DATA``.

The generic ``laser_polio.manifest_loader.load_manifest`` only knows how to
exec a ``manifest.py``. This module adds the three-path resolution
(rich/thin/naked) plus a ``write_manifest`` helper and a CLI for producing a
shareable manifest from any compliant data dir.
"""
import importlib.util
import types
from pathlib import Path

from laser_polio.manifest_loader import MissingDataError, get_data_root

__all__ = [
    "EXPECTED_DATA_FILES",
    "MissingDataError",
    "load_manifest",
    "write_manifest",
]


# The contract: filename -> attribute name for every data file the Nigeria
# model references via ``manifest.<attr>``. lpn declares what IT needs;
# nigeria_polio (the producer) may ship a superset. If this list grows, the
# producer's FILENAMES set has to grow too — at publish time the wheel won't
# contain the missing files, and load_manifest() will raise loudly.
EXPECTED_DATA_FILES = {
    "adm01_adjacency.npz": "adjacency",
    "Nigeria_age_pyramid_2024.csv": "age_pyramid",
    "node_lookup.json": "node_lookup",
    "compiled_cbr_pop_ri_sia_underwt_africa.csv": "population",
    "shp_africa_low_res.gpkg": "shapefile",
    "sia_scenario_1.csv": "sia_future",
    "sia_historic_schedule.csv": "sia_historic",
    "init_immunity_0.5coverage_january.h5": "init_immunity",
}


def load_manifest():
    """Return a namespace with paths to every data file this model needs.

    Resolution strategy, in order:
      1. Run ``manifest.py`` from the data root if present, promoting any
         Path-valued attributes it defines. Supports both rich (old-style)
         manifests that bind every variable and thin (new-style) manifests
         that only set DATA_ROOT.
      2. For every EXPECTED_DATA_FILES entry not already supplied, resolve
         ``<DATA_ROOT>/<filename>`` directly from the data root.
      3. If any expected file is still missing, raise MissingDataError with a
         clear recovery path.
    """
    data_root = get_data_root()
    manifest_path = data_root / "manifest.py"

    mod = types.SimpleNamespace()
    mod.DATA_ROOT = data_root

    if manifest_path.exists():
        spec = importlib.util.spec_from_file_location(
            "laser_polio_nigeria_user_manifest", manifest_path
        )
        if spec is None or spec.loader is None:
            raise MissingDataError(
                f"Could not interpret {manifest_path} as a Python module. "
                "Check that it is a valid .py file."
            )
        loaded = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(loaded)

        # Promote only the known names (DATA_ROOT + EXPECTED_DATA_FILES variables).
        # Tolerate str-typed paths (common in hand-written manifests) by coercing to Path.
        expected_vars = set(EXPECTED_DATA_FILES.values())
        for attr, value in vars(loaded).items():
            if attr.startswith("_") or not isinstance(value, (Path, str)):
                continue
            if attr == "DATA_ROOT":
                data_root = Path(value)
                mod.DATA_ROOT = data_root
            elif attr in expected_vars:
                setattr(mod, attr, Path(value))

    missing = []
    for filename, var_name in EXPECTED_DATA_FILES.items():
        if hasattr(mod, var_name):
            # Rich manifest supplied this variable — verify the file exists, so we
            # don't silently hand the model a path to a missing file.
            bound = getattr(mod, var_name)
            if not bound.exists():
                missing.append(
                    f"{filename} (manifest binds {var_name!r} to {bound}, which does not exist)"
                )
            continue
        candidate = data_root / filename
        if not candidate.exists():
            missing.append(filename)
            continue
        setattr(mod, var_name, candidate)

    if missing:
        bullet_list = "\n".join(f"  - {f}" for f in missing)
        raise MissingDataError(
            f"\nLASER Polio (Nigeria) data not found.\n\n"
            f"Looked in: {data_root}\n"
            f"(set LASER_POLIO_DATA to override)\n\n"
            f"The following required files are missing:\n"
            f"{bullet_list}\n\n"
            f"Either drop those files into {data_root}, or — if you have the\n"
            f"nigeria_polio package installed — run:\n"
            f"    python -m nigeria_polio.bootstrap --target {data_root}\n"
            f"to fetch and validate them.\n"
        )

    return mod


def write_manifest(data_root: Path) -> Path:
    """Generate a portable manifest.py inside ``data_root`` by inspecting its contents.

    Walks EXPECTED_DATA_FILES and writes a manifest.py that binds each variable
    to its corresponding file under DATA_ROOT (resolved at import time relative
    to the manifest.py's own location). Raises MissingDataError if any expected
    file is missing — a manifest pointing at nonexistent files would fail at
    load time anyway, so surface the problem here.

    Useful for: producing a shareable data dir (manifest + files) without
    requiring ``nigeria_polio`` installed on the recipient side.
    """
    data_root = data_root.resolve()
    missing = [f for f in EXPECTED_DATA_FILES if not (data_root / f).exists()]
    if missing:
        raise MissingDataError(
            f"Cannot write manifest.py — {data_root} is missing required files: {missing}"
        )

    target = data_root / "manifest.py"
    lines = [
        "# Auto-generated by laser_polio_nigeria.manifest.write_manifest",
        "# DO NOT EDIT BY HAND",
        "from pathlib import Path",
        "",
        "DATA_ROOT = Path(__file__).resolve().parent",
        "",
    ]
    for filename, var_name in EXPECTED_DATA_FILES.items():
        lines.append(f"{var_name} = DATA_ROOT / {filename!r}")
    target.write_text("\n".join(lines) + "\n")
    return target


def _cli(argv=None):
    import argparse

    parser = argparse.ArgumentParser(
        prog="python -m laser_polio_nigeria.manifest",
        description=(
            "Generate a portable manifest.py inside a data directory by "
            "inspecting the files present and applying the Nigeria model's "
            "EXPECTED_DATA_FILES contract."
        ),
    )
    parser.add_argument(
        "data_root",
        type=Path,
        help="Directory containing the data files (and where manifest.py will be written).",
    )
    args = parser.parse_args(argv)
    target = write_manifest(args.data_root)
    print(f"Wrote {target}")


if __name__ == "__main__":
    _cli()
