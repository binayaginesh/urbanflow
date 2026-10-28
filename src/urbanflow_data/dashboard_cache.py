"""
dashboard_cache.py - Offline Mode and Simulation Caching for UrbanFlow Dashboard.

Provides:
- Detection and control of Offline Mode (URBANFLOW_OFFLINE).
- Detection and control of Demo Cache Mode (URBANFLOW_CACHE_MODE).
- Disk & in-memory caching of scenario simulation results for instant UI updates.
- Offline map rendering configurations (rendering without tile server dependencies).
"""
from __future__ import annotations

import json
import logging
import os
import pickle
from pathlib import Path
from typing import Any, Callable

from urbanflow_data.config import get_data_dir

logger = logging.getLogger(__name__)

_FORCE_OFFLINE: bool | None = None
_FORCE_CACHE_MODE: bool | None = None


def is_offline_mode() -> bool:
    """
    Return True if offline mode is active.
    Can be set via URBANFLOW_OFFLINE env var ("1", "true", "yes").
    """
    global _FORCE_OFFLINE
    if _FORCE_OFFLINE is not None:
        return _FORCE_OFFLINE
    val = os.environ.get("URBANFLOW_OFFLINE", "").strip().lower()
    return val in ("1", "true", "yes", "on")


def set_offline_mode(enabled: bool | None) -> None:
    """Programmatically override offline mode."""
    global _FORCE_OFFLINE
    _FORCE_OFFLINE = enabled
    if enabled is not None:
        os.environ["URBANFLOW_OFFLINE"] = "1" if enabled else "0"


def is_cache_mode() -> bool:
    """
    Return True if demo cache mode is active.
    Enabled by default, or via URBANFLOW_CACHE_MODE ("1", "true", "yes").
    """
    global _FORCE_CACHE_MODE
    if _FORCE_CACHE_MODE is not None:
        return _FORCE_CACHE_MODE
    val = os.environ.get("URBANFLOW_CACHE_MODE", "1").strip().lower()
    return val in ("1", "true", "yes", "on")


def set_cache_mode(enabled: bool | None) -> None:
    """Programmatically override cache mode."""
    global _FORCE_CACHE_MODE
    _FORCE_CACHE_MODE = enabled
    if enabled is not None:
        os.environ["URBANFLOW_CACHE_MODE"] = "1" if enabled else "0"


def get_cache_dir(base_dir: str | Path | None = None) -> Path:
    """Return cache directory inside the current data directory."""
    data_dir = get_data_dir(base_dir)
    cache_dir = data_dir / ".cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def get_cached_simulation(
    cache_key: str,
    compute_fn: Callable[[], Any],
    force_recompute: bool = False,
    base_dir: str | Path | None = None,
) -> Any:
    """
    Retrieve simulation result from cache or compute and store it.
    Uses pickle for complex simulation objects (SimulationResult).
    """
    if not is_cache_mode() or force_recompute:
        return compute_fn()

    cdir = get_cache_dir(base_dir)
    safe_key = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in cache_key)
    cache_file = cdir / f"sim_{safe_key}.pkl"

    if cache_file.exists():
        try:
            with open(cache_file, "rb") as fh:
                logger.info("Loaded cached simulation: %s", cache_key)
                return pickle.load(fh)
        except Exception as exc:
            logger.warning("Failed to load cache %s: %s; recomputing", cache_file, exc)

    result = compute_fn()
    try:
        with open(cache_file, "wb") as fh:
            pickle.dump(result, fh)
            logger.info("Saved cached simulation: %s", cache_key)
    except Exception as exc:
        logger.warning("Failed to write cache %s: %s", cache_file, exc)

    return result


def clear_cache(base_dir: str | Path | None = None) -> int:
    """Clear all cached simulation files. Returns count of deleted files."""
    cdir = get_cache_dir(base_dir)
    count = 0
    for p in cdir.glob("sim_*.pkl"):
        try:
            p.unlink()
            count += 1
        except Exception:
            pass
    return count


def get_offline_map_theme() -> dict[str, Any]:
    """
    Return plotting styles and layout config for offline network rendering.
    Enables dark command-center aesthetic without loading online tiles.
    """
    return {
        "plot_bgcolor": "#0d0f1a",
        "paper_bgcolor": "#0d0f1a",
        "font_color": "#e0e6ed",
        "grid_color": "#1f293d",
        "node_color_normal": "#00e5ff",
        "node_color_closed": "#ff1744",
        "edge_color_free": "#00e676",
        "edge_color_moderate": "#ffd600",
        "edge_color_severe": "#ff1744",
        "tile_provider": "none" if is_offline_mode() else "carto-darkmatter",
    }
