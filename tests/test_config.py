"""tests/test_config.py – Unit tests for config.py"""
from __future__ import annotations
import pytest
from pathlib import Path


def test_config_loads(cfg):
    """Config should load without error."""
    assert cfg is not None


def test_required_keys_present(cfg):
    required = [
        "study_area", "crs", "osm", "default_lanes", "default_speed_kmh",
        "free_flow_speed_cap_kmh", "capacity_per_lane_pcu_hr", "pcu_equivalents",
        "time_slots", "bpr_defaults", "paths",
    ]
    for k in required:
        assert k in cfg, f"Missing required key: {k}"


def test_bbox_values(cfg):
    bb = cfg["study_area"]["bbox"]
    assert bb["north"] > bb["south"], "north must be > south"
    assert bb["east"]  > bb["west"],  "east must be > west"


def test_small_bbox_within_main_bbox(cfg):
    bb  = cfg["study_area"]["bbox"]
    sb  = cfg["study_area"]["small_bbox"]
    assert sb["north"] <= bb["north"]
    assert sb["south"] >= bb["south"]
    assert sb["east"]  <= bb["east"]
    assert sb["west"]  >= bb["west"]


def test_crs_strings(cfg):
    assert cfg["crs"]["storage"].startswith("EPSG:")
    assert cfg["crs"]["metric"].startswith("EPSG:")


def test_bpr_alpha_beta_positive(cfg):
    assert cfg["bpr_defaults"]["alpha"] > 0
    assert cfg["bpr_defaults"]["beta"]  > 0


def test_capacity_reduction_factor(cfg):
    factor = cfg["capacity_reduction_factor"]
    assert 0 < factor <= 1.0


def test_time_slots_non_empty(cfg):
    slots = cfg["time_slots"]
    assert isinstance(slots, list) and len(slots) >= 1


def test_road_class_consistency(cfg):
    classes = set(cfg["default_lanes"].keys())
    for table in ("default_speed_kmh", "free_flow_speed_cap_kmh", "capacity_per_lane_pcu_hr"):
        assert set(cfg[table].keys()) == classes, \
            f"{table} road classes do not match default_lanes"


def test_get_config_cache(project_root):
    from urbanflow_data.config import load_config, get_config
    cfg1 = load_config(root=project_root)
    cfg2 = get_config()
    assert cfg1 is cfg2  # should be the same cached object


def test_missing_key_raises(tmp_path):
    import yaml
    bad_cfg = {"study_area": {"bbox": {"north":1,"south":0,"east":1,"west":0}}}
    p = tmp_path / "config" / "config.yaml"
    p.parent.mkdir()
    p.write_text(yaml.dump(bad_cfg), encoding="utf-8")
    from urbanflow_data.config import load_config
    with pytest.raises(ValueError, match="Missing required"):
        load_config(path=p)
