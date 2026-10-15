"""
cli.py -- Command-line interface for the UrbanFlow data pipeline.

Entry point: ``python -m urbanflow_data.cli``
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

import click

from .config import load_config, get_config
from .logging_setup import setup_logging

logger = logging.getLogger(__name__)


# -- Shared options -------------------------------------------------------------
def _root_option(f):
    return click.option(
        "--root",
        default=".",
        show_default=True,
        help="Project root directory (where config/ and data/ live).",
        type=click.Path(exists=True, file_okay=False),
    )(f)


def _debug_option(f):
    return click.option(
        "--debug",
        is_flag=True,
        default=False,
        help="Enable DEBUG logging.",
    )(f)


def _small_option(f):
    return click.option(
        "--small",
        is_flag=True,
        default=False,
        help="Use small_bbox instead of full bbox (for fast pipeline testing).",
    )(f)


# -- Root group -----------------------------------------------------------------
@click.group()
@click.version_option(package_name="urbanflow-data", prog_name="urbanflow-data")
def cli() -> None:
    """UrbanFlow Data & Network Modeling pipeline (Module 1)."""


# -- config-check --------------------------------------------------------------
@cli.command("config-check")
@_root_option
@_debug_option
def config_check(root: str, debug: bool) -> None:
    """Load and validate config.yaml, print a summary."""
    cfg = load_config(root=root)
    setup_logging(cfg, level="DEBUG" if debug else None)
    click.echo(click.style("[OK] Config loaded and validated successfully.", fg="green"))
    sa = cfg["study_area"]
    if sa.get("place_name"):
        click.echo(f"  Study area: {sa['place_name']}")
    else:
        bb = sa["bbox"]
        click.echo(
            f"  Study area bbox: N={bb['north']} S={bb['south']} "
            f"E={bb['east']} W={bb['west']}"
        )
    click.echo(f"  Storage CRS : {cfg['crs']['storage']}")
    click.echo(f"  Metric CRS  : {cfg['crs']['metric']}")
    click.echo(f"  Time slots  : {[s['name'] for s in cfg['time_slots']]}")
    click.echo(f"  BPR alpha={cfg['bpr_defaults']['alpha']}  beta={cfg['bpr_defaults']['beta']}")


# -- download -------------------------------------------------------------------
@cli.command("download")
@_root_option
@_debug_option
@_small_option
def download(root: str, debug: bool, small: bool) -> None:
    """Phase 1 Step 1 -- Download OSM road network and extra features."""
    cfg = load_config(root=root)
    setup_logging(cfg, level="DEBUG" if debug else None)
    logger.info("Starting OSM download (small=%s)...", small)
    from .osm_download import run as _run
    _run(cfg, root=Path(root), small=small)
    click.echo(click.style("[OK] OSM download complete.", fg="green"))


# -- clean ----------------------------------------------------------------------
@cli.command("clean")
@_root_option
@_debug_option
def clean(root: str, debug: bool) -> None:
    """Phase 1 Step 2 -- Clean and simplify the raw OSM graph."""
    cfg = load_config(root=root)
    setup_logging(cfg, level="DEBUG" if debug else None)
    logger.info("Starting network cleaning...")
    from .clean_network import run as _run
    _run(cfg, root=Path(root))
    click.echo(click.style("[OK] Network cleaning complete.", fg="green"))


# -- build-graph ----------------------------------------------------------------
@cli.command("build-graph")
@_root_option
@_debug_option
def build_graph(root: str, debug: bool) -> None:
    """Phase 2 -- Build the simulation-ready graph with capacity attributes."""
    cfg = load_config(root=root)
    setup_logging(cfg, level="DEBUG" if debug else None)
    logger.info("Building simulation graph...")
    from .build_graph import run as _run
    _run(cfg, root=Path(root))
    click.echo(click.style("[OK] Graph build complete.", fg="green"))


# -- transit --------------------------------------------------------------------
@cli.command("transit")
@_root_option
@_debug_option
def transit(root: str, debug: bool) -> None:
    """Phase 3 -- Snap bus routes and metro stations onto the graph."""
    cfg = load_config(root=root)
    setup_logging(cfg, level="DEBUG" if debug else None)
    logger.info("Processing transit layer...")
    from .transit import run as _run
    _run(cfg, root=Path(root))
    click.echo(click.style("[OK] Transit layer complete.", fg="green"))


# -- baseline -------------------------------------------------------------------
@cli.command("baseline")
@_root_option
@_debug_option
def baseline(root: str, debug: bool) -> None:
    """Phase 4a -- Collect observed traffic speeds."""
    cfg = load_config(root=root)
    setup_logging(cfg, level="DEBUG" if debug else None)
    logger.info("Collecting traffic baseline...")
    from .traffic_baseline import run as _run
    _run(cfg, root=Path(root))
    click.echo(click.style("[OK] Baseline collection complete.", fg="green"))


# -- calibrate ------------------------------------------------------------------
@cli.command("calibrate")
@_root_option
@_debug_option
def calibrate(root: str, debug: bool) -> None:
    """Phase 4b -- Fit BPR parameters and distribute observed speeds to edges."""
    cfg = load_config(root=root)
    setup_logging(cfg, level="DEBUG" if debug else None)
    logger.info("Calibrating network...")
    from .calibrate import run as _run
    _run(cfg, root=Path(root))
    click.echo(click.style("[OK] Calibration complete.", fg="green"))


# -- export ---------------------------------------------------------------------
@cli.command("export")
@_root_option
@_debug_option
def export(root: str, debug: bool) -> None:
    """Phase 5a -- Export final bundle to data/processed/."""
    cfg = load_config(root=root)
    setup_logging(cfg, level="DEBUG" if debug else None)
    logger.info("Exporting final data bundle...")
    from .export import run as _run
    _run(cfg, root=Path(root))
    click.echo(click.style("[OK] Export complete.", fg="green"))


# -- validate -------------------------------------------------------------------
@cli.command("validate")
@_root_option
@_debug_option
def validate(root: str, debug: bool) -> None:
    """Phase 5b -- Run automated validation checks on the processed bundle."""
    cfg = load_config(root=root)
    setup_logging(cfg, level="DEBUG" if debug else None)
    logger.info("Running validation...")
    from .validate import run as _run
    passed = _run(cfg, root=Path(root))
    if passed:
        click.echo(click.style("[OK] All validation checks passed.", fg="green"))
    else:
        click.echo(click.style("[FAIL] Some validation checks FAILED. See above.", fg="red"))
        sys.exit(1)


# -- run-all --------------------------------------------------------------------
@cli.command("run-all")
@_root_option
@_debug_option
@_small_option
def run_all(root: str, debug: bool, small: bool) -> None:
    """Run the complete pipeline: download -> clean -> build -> transit -> baseline -> calibrate -> export -> validate."""
    cfg = load_config(root=root)
    setup_logging(cfg, level="DEBUG" if debug else None)
    root_path = Path(root)

    steps = [
        ("OSM Download",       "osm_download",     {"small": small}),
        ("Network Cleaning",   "clean_network",    {}),
        ("Build Graph",        "build_graph",      {}),
        ("Transit Layer",      "transit",          {}),
        ("Traffic Baseline",   "traffic_baseline", {}),
        ("Calibration",        "calibrate",        {}),
        ("Export",             "export",           {}),
        ("Validation",         "validate",         {}),
    ]

    for label, module_name, kwargs in steps:
        click.echo(click.style(f"\n--- {label} ---", bold=True))
        import importlib
        mod = importlib.import_module(f".{module_name}", package="urbanflow_data")
        result = mod.run(cfg, root=root_path, **kwargs)
        if result is False:
            click.echo(click.style(f"[FAIL] {label} reported failure. Aborting.", fg="red"))
            sys.exit(1)
        click.echo(click.style(f"[OK] {label} done.", fg="green"))

    click.echo(click.style("\n[OK][OK][OK]  Full pipeline complete!", fg="bright_green", bold=True))


# -- Module entry point ---------------------------------------------------------
if __name__ == "__main__":
    cli()
