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
import os
import types
from pathlib import Path


class MissingDataError(RuntimeError):
    """Raised when the Nigeria data root is absent, incomplete, or unreadable."""


def get_data_root() -> Path:
    """Return the directory the loader should look in for Nigeria data files.

    Reads ``LASER_POLIO_DATA``; falls back to the current working directory.
    Defined locally so this module has no runtime dependency on laser_polio —
    a user with a naked data dir can run the manifest tooling without any
    other LASER packages installed.
    """
    return Path(os.environ.get("LASER_POLIO_DATA", Path.cwd())).resolve()

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

    Resolution rules:
      * ``LASER_POLIO_DATA`` (the env var; CWD if unset) is **authoritative**
        — it's where the user said the data lives, and the loader honors that.
      * If ``manifest.py`` exists in that directory, its variable bindings
        are used as overrides — but only when the file each one points at
        actually exists. A manifest whose hardcoded ``DATA_ROOT`` no longer
        matches reality (e.g., the dir was moved or copied elsewhere) is
        treated as informational, not authoritative.
      * For any expected variable not supplied by a working manifest
        binding, ``<LASER_POLIO_DATA>/<filename>`` is resolved directly.
      * If, after both passes, a required file is still missing, raise
        MissingDataError listing what's missing and reporting the
        ``LASER_POLIO_DATA`` location.
    """
    data_root = get_data_root()
    if not data_root.is_dir():
        # Surface the actual problem (typo'd LASER_POLIO_DATA, file instead of
        # dir) rather than letting it cascade into "all 8 files are missing",
        # which is true but unhelpful.
        env_var_set = bool(os.environ.get("LASER_POLIO_DATA"))
        source = (
            "LASER_POLIO_DATA points at" if env_var_set else "Falling back to CWD —"
        )
        kind = "a file" if data_root.exists() else "a path that does not exist"
        raise MissingDataError(
            f"LASER Polio (Nigeria) data directory not found.\n"
            f"{source} {data_root}, which is {kind}, not a directory.\n"
            "Point LASER_POLIO_DATA at an existing data directory."
        )

    manifest_path = data_root / "manifest.py"

    mod = types.SimpleNamespace()
    mod.DATA_ROOT = data_root

    # First (optional) pass: gather any usable bindings the manifest provides.
    # We deliberately do NOT let the manifest override `data_root` — the env
    # var wins. The manifest's variable bindings are kept only when the file
    # they point at actually exists; otherwise we ignore them and synthesize
    # against `data_root` below.
    manifest_data_root_hint = None
    manifest_bindings = {}
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
        try:
            spec.loader.exec_module(loaded)
        except Exception as exc:
            raise MissingDataError(
                f"Failed to execute {manifest_path}: {type(exc).__name__}: {exc}\n"
                "The manifest.py file in your data directory has a syntax error or "
                "raised an exception at import time. Edit it to fix the issue, or "
                "delete it to fall back to filename-based loading."
            ) from exc

        manifest_dir = manifest_path.parent.resolve()
        if hasattr(loaded, "DATA_ROOT"):
            raw = loaded.DATA_ROOT
            if isinstance(raw, Path):
                manifest_data_root_hint = (
                    raw if raw.is_absolute() else (manifest_dir / raw).resolve()
                )
            elif isinstance(raw, str):
                manifest_data_root_hint = (manifest_dir / raw).resolve()

        # Manifest variables: paths declared on attributes whose names match
        # EXPECTED_DATA_FILES. String paths resolve against the manifest's own
        # DATA_ROOT hint (or against `data_root` if it had none).
        bind_root = manifest_data_root_hint or data_root
        expected_vars = set(EXPECTED_DATA_FILES.values())
        for attr, value in vars(loaded).items():
            if attr.startswith("_") or attr == "DATA_ROOT" or attr not in expected_vars:
                continue
            if isinstance(value, Path):
                manifest_bindings[attr] = (
                    value if value.is_absolute() else (bind_root / value).resolve()
                )
            elif isinstance(value, str):
                manifest_bindings[attr] = (bind_root / value).resolve()

    # Resolve each expected file. Prefer a manifest binding when it points at
    # an existing file; otherwise look for the file in LASER_POLIO_DATA.
    missing = []
    for filename, var_name in EXPECTED_DATA_FILES.items():
        bound = manifest_bindings.get(var_name)
        if bound is not None and bound.exists():
            setattr(mod, var_name, bound)
            continue
        candidate = data_root / filename
        if candidate.exists():
            setattr(mod, var_name, candidate)
            continue
        missing.append(filename)

    if missing:
        bullet_list = "\n".join(f"  - {f}" for f in missing)
        env_var_set = bool(os.environ.get("LASER_POLIO_DATA"))
        location_caveat = (
            "(from LASER_POLIO_DATA)"
            if env_var_set
            else "(set LASER_POLIO_DATA to override)"
        )
        hint = ""
        if (
            manifest_data_root_hint is not None
            and manifest_data_root_hint != data_root
        ):
            hint = (
                f"\nNote: {manifest_path} declares DATA_ROOT={manifest_data_root_hint},\n"
                f"but LASER_POLIO_DATA pointed at {data_root}, so LASER_POLIO_DATA wins.\n"
                f"If you actually want to use the manifest's location, set\n"
                f"  export LASER_POLIO_DATA={manifest_data_root_hint}\n"
            )
        raise MissingDataError(
            f"\nLASER Polio (Nigeria) data not found.\n\n"
            f"Looked in: {data_root}\n"
            f"{location_caveat}\n\n"
            f"The following required files are missing:\n"
            f"{bullet_list}\n"
            f"{hint}\n"
            f"Either drop those files into {data_root}, or — if you have the\n"
            f"nigeria_polio package installed — run:\n"
            f"    python -m nigeria_polio.bootstrap --target {data_root}\n"
            f"to fetch and validate them.\n"
        )

    return mod


def write_manifest(data_root: Path, *, force: bool = False) -> Path:
    """Generate a portable manifest.py inside ``data_root`` by inspecting its contents.

    Walks EXPECTED_DATA_FILES and writes a manifest.py that binds each variable
    to its corresponding file under DATA_ROOT (resolved at import time relative
    to the manifest.py's own location). Raises MissingDataError if any expected
    file is missing — a manifest pointing at nonexistent files would fail at
    load time anyway, so surface the problem here.

    Refuses to overwrite an existing ``manifest.py`` unless ``force=True``. Rich
    user-maintained manifests are explicitly supported as overrides, so
    clobbering one silently would risk data loss. The CLI exposes this as
    ``--force``.

    Useful for: producing a shareable data dir (manifest + files) without
    requiring ``nigeria_polio`` installed on the recipient side.
    """
    data_root = data_root.resolve()
    if not data_root.is_dir():
        kind = "is a file" if data_root.exists() else "does not exist"
        raise MissingDataError(
            f"Cannot write manifest.py — {data_root} {kind}. "
            "Pass an existing data directory."
        )
    missing = [f for f in EXPECTED_DATA_FILES if not (data_root / f).exists()]
    if missing:
        raise MissingDataError(
            f"Cannot write manifest.py — {data_root} is missing required files: {missing}"
        )

    target = data_root / "manifest.py"
    if target.exists() and not force:
        raise MissingDataError(
            f"{target} already exists. Inspect its contents (it may contain custom "
            "variable overrides) and pass force=True (or --force on the CLI) to overwrite."
        )
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
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing manifest.py. Off by default to protect custom overrides.",
    )
    args = parser.parse_args(argv)
    target = write_manifest(args.data_root, force=args.force)
    print(f"Wrote {target}")


if __name__ == "__main__":
    _cli()
