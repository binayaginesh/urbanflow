"""tests/test_c6_library_and_thresholds.py - Stage C6 scenario library & threshold calibration tests."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from calibrate_thresholds import analyze_thresholds
from run_library import evaluate_library
from urbanflow_data.config import get_data_dir, load_config
from urbanflow_data.decision_layer import (
    VERDICT_MODERATE,
    VERDICT_NOT_RECOMMENDED,
    VERDICT_RECOMMENDED,
)
from urbanflow_data.network_bundle import load_network


def test_config_has_events_vip_routes_and_demand_zones():
    cfg = load_config(root=ROOT)
    sz = cfg.get("scenarios_and_zones", {})
    assert len(sz.get("events", [])) >= 3
    assert len(sz.get("vip_routes", [])) >= 2
    assert len(sz.get("demand_zones", [])) >= 4
    # Costs must not be fabricated: unknown costs remain null (None)
    for cand in cfg["decision_intelligence"]["optimizer_candidates"]:
        assert "estimated_cost_inr_crore" in cand
        assert cand["estimated_cost_inr_crore"] is None


def test_evaluate_library_and_threshold_tiers():
    cfg = load_config(root=ROOT)
    net = load_network(get_data_dir(ROOT / "data" / "processed"))
    res = analyze_thresholds(net, cfg)
    assert res["all_three_tiers_present_in_peak"] is True
    peak_counts = res["peak_tier_counts"]
    assert peak_counts.get(VERDICT_RECOMMENDED, 0) >= 1
    assert peak_counts.get(VERDICT_MODERATE, 0) >= 1
    assert peak_counts.get(VERDICT_NOT_RECOMMENDED, 0) >= 1


def test_run_library_all_slots():
    cfg = load_config(root=ROOT)
    net = load_network(get_data_dir(ROOT / "data" / "processed"))
    rep = evaluate_library(net, cfg)
    assert set(rep["slots"].keys()) == {"night_offpeak", "morning_peak", "midday", "evening_peak"}
    for slot, sdata in rep["slots"].items():
        assert len(sdata["candidates"]) == len(cfg["decision_intelligence"]["optimizer_candidates"])
