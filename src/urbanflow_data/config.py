"""
config.py – Load and strictly validate config/config.yaml.

All other modules obtain the config via ``get_config()``.
The config is loaded once and cached; call ``load_config(path)`` only to
reload (e.g., in tests).
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

# ── Module-level cache ────────────────────────────────────────────────────────
_CONFIG: dict[str, Any] | None = None
_CONFIG_PATH: Path | None = None

# ── Required top-level keys that must exist in config.yaml ───────────────────
_REQUIRED_KEYS = [
    "study_area",
    "crs",
    "osm",
    "network_cleaning",
    "default_lanes",
    "default_speed_kmh",
    "free_flow_speed_cap_kmh",
    "free_flow_reduction_factor",
    "capacity_per_lane_pcu_hr",
    "capacity_reduction_factor",
    "pcu_equivalents",
    "time_slots",
    "bpr_defaults",
    "transit",
    "traffic_baseline",
    "api",
    "paths",
    "logging",
]

_REQUIRED_ROAD_CLASSES = [
    "motorway", "trunk", "primary", "secondary",
    "tertiary", "residential", "unclassified", "service",
]


def _validate(cfg: dict[str, Any], source: str) -> None:
    """Raise ValueError loudly if any required key or sub-key is missing."""
    missing = [k for k in _REQUIRED_KEYS if k not in cfg]
    if missing:
        raise ValueError(
            f"[config] Missing required top-level keys in {source}: {missing}"
        )

    # study_area must have bbox
    sa = cfg["study_area"]
    if sa.get("place_name") is None:
        bbox = sa.get("bbox", {})
        for coord in ("north", "south", "east", "west"):
            if coord not in bbox:
                raise ValueError(
                    f"[config] study_area.bbox.{coord} is missing in {source}"
                )

    # crs must have storage + metric
    for key in ("storage", "metric"):
        if key not in cfg["crs"]:
            raise ValueError(f"[config] crs.{key} is missing in {source}")

    # bpr_defaults
    for key in ("alpha", "beta"):
        if key not in cfg["bpr_defaults"]:
            raise ValueError(f"[config] bpr_defaults.{key} is missing in {source}")

    # road-class tables
    for table in ("default_lanes", "default_speed_kmh",
                  "free_flow_speed_cap_kmh", "capacity_per_lane_pcu_hr"):
        missing_cls = [rc for rc in _REQUIRED_ROAD_CLASSES if rc not in cfg[table]]
        if missing_cls:
            raise ValueError(
                f"[config] {table} is missing road class(es) {missing_cls} in {source}"
            )

    # pcu_equivalents
    for veh in ("car", "two_wheeler", "bus"):
        if veh not in cfg["pcu_equivalents"]:
            raise ValueError(
                f"[config] pcu_equivalents.{veh} is missing in {source}"
            )

    # time_slots must be a non-empty list with name/hour/minute
    slots = cfg["time_slots"]
    if not isinstance(slots, list) or len(slots) == 0:
        raise ValueError(f"[config] time_slots must be a non-empty list in {source}")
    for i, slot in enumerate(slots):
        for key in ("name", "label", "hour", "minute"):
            if key not in slot:
                raise ValueError(
                    f"[config] time_slots[{i}].{key} is missing in {source}"
                )


def load_config(
    path: str | Path | None = None,
    *,
    root: str | Path | None = None,
) -> dict[str, Any]:
    """
    Load, validate, and cache config.yaml.

    Parameters
    ----------
    path:
        Explicit path to config.yaml.  When omitted, searches for
        ``config/config.yaml`` relative to *root* or the repository root.
    root:
        Project root directory.  Defaults to the current working directory.
    """
    global _CONFIG, _CONFIG_PATH

    if path is not None:
        config_path = Path(path).expanduser().resolve()
    else:
        search_root = Path(root) if root else Path.cwd()
        config_path = search_root / "config" / "config.yaml"

    if not config_path.exists():
        raise FileNotFoundError(
            f"[config] config.yaml not found at expected location: {config_path}\n"
            "Run from the project root or pass the explicit path."
        )

    with config_path.open("r", encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)

    if cfg is None:
        raise ValueError(f"[config] config.yaml at {config_path} is empty.")

    _validate(cfg, str(config_path))

    _CONFIG = cfg
    _CONFIG_PATH = config_path
    logger.info("Config loaded and validated from %s", config_path)
    return cfg


def get_config(
    *,
    root: str | Path | None = None,
    reload: bool = False,
) -> dict[str, Any]:
    """
    Return the cached config, loading it on first call.

    Parameters
    ----------
    root:
        Project root (only used on first load).
    reload:
        Force re-read from disk even if already cached.
    """
    global _CONFIG
    if _CONFIG is None or reload:
        load_config(root=root)
    return _CONFIG  # type: ignore[return-value]


def get_bbox(cfg: dict[str, Any] | None = None) -> tuple[float, float, float, float]:
    """Return (north, south, east, west) from config."""
    cfg = cfg or get_config()
    bb = cfg["study_area"]["bbox"]
    return (bb["north"], bb["south"], bb["east"], bb["west"])


def get_small_bbox(cfg: dict[str, Any] | None = None) -> tuple[float, float, float, float]:
    """Return (north, south, east, west) of the small debug bbox."""
    cfg = cfg or get_config()
    bb = cfg["study_area"]["small_bbox"]
    return (bb["north"], bb["south"], bb["east"], bb["west"])


def get_time_slot_names(cfg: dict[str, Any] | None = None) -> list[str]:
    """Return list of time slot machine-names in config order."""
    cfg = cfg or get_config()
    return [slot["name"] for slot in cfg["time_slots"]]


def get_data_dir(
    explicit: str | Path | None = None,
    *,
    root: str | Path | None = None,
) -> Path:
    """
    Resolve the processed data directory.

    Resolution order:
    1. Explicit path if passed (unless it is a generic default 'data/processed'
       and URBANFLOW_DATA_DIR is set).
    2. URBANFLOW_DATA_DIR environment variable if defined.
    3. cfg["paths"]["processed_dir"] resolved against root / cwd.
    4. Fallback: <root>/data/processed.
    """
    env_dir = os.environ.get("URBANFLOW_DATA_DIR")

    if explicit is not None and str(explicit).strip():
        explicit_norm = str(explicit).replace("\\", "/").rstrip("/")
        # If caller passed default "data/processed" but env var is set, prefer env var
        if env_dir and explicit_norm.endswith("data/processed"):
            return Path(env_dir).expanduser().resolve()
        return Path(explicit).expanduser().resolve()

    if env_dir and env_dir.strip():
        return Path(env_dir).expanduser().resolve()

    base = Path(root) if root else Path.cwd()
    try:
        cfg = get_config(root=root)
        rel = cfg.get("paths", {}).get("processed_dir", "data/processed")
        return (base / rel).resolve()
    except Exception:
        return (base / "data" / "processed").resolve()
