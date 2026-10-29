"""tests/test_b7_validation_harness.py - Stage B7 tests for the validation harness."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import pytest

from urbanflow_data.config import get_data_dir, load_config
from urbanflow_data.network_bundle import load_network
from urbanflow_data.simulation_engine import TrafficSimulator
from urbanflow_data.validation_harness import (
    assign_time_slot,
    bundle_integrity_checks,
    compare_edge_speeds,
    corridor_validation,
    error_metrics,
    holdout_split,
    load_manual_observations,
    reference_label,
    run_validation,
    simulated_corridor_ratio,
)
from urbanflow_data.dashboard_ui import build_error_by_group_chart, build_validation_scatter

SLOTS = ["night_offpeak", "morning_peak", "midday", "evening_peak"]


@pytest.fixture(scope="module")
def ctx():
    cfg = load_config()
    net = load_network(get_data_dir())
    sim = TrafficSimulator(net.graph, net.bpr_params, bus_route_edges=net.bus_route_edges)
    sims = {s: sim.simulate(net.graph, s, "Baseline") for s in SLOTS}
    return cfg, net, sims


# ── metrics ──
def test_error_metrics_known_values():
    m = error_metrics([10, 20, 30], [12, 18, 33])
    assert m["n"] == 3
    assert m["mae"] == pytest.approx((2 + 2 + 3) / 3)
    assert m["rmse"] == pytest.approx(np.sqrt((4 + 4 + 9) / 3))
    assert m["bias"] == pytest.approx((2 - 2 + 3) / 3)
    assert m["mape_pct"] == pytest.approx((0.2 + 0.1 + 0.1) / 3 * 100)
    assert m["pearson_r"] is not None and m["pearson_r"] > 0.9


def test_error_metrics_empty_returns_none():
    m = error_metrics([], [])
    assert m["n"] == 0 and m["rmse"] is None and m["mape_pct"] is None


def test_reference_label():
    assert reference_label(pd.Series(["synthetic_demo"] * 3)) == "synthetic"
    assert reference_label(pd.Series(["observed", "manual"])) == "observed"
    assert reference_label(pd.Series(["observed", "imputed"])) == "mixed"


# ── split ──
def test_holdout_split_is_deterministic_and_disjoint():
    ids = [f"R{i:02d}" for i in range(1, 21)]
    a = holdout_split(ids, 0.3, 42)
    b = holdout_split(list(reversed(ids)), 0.3, 42)
    assert a == b
    cal, test = a
    assert len(test) == 6 and len(cal) == 14
    assert not set(cal) & set(test)
    assert holdout_split(ids, 0.3, 7) != a  # seed changes split


def test_holdout_split_small_sets_keep_both_sides():
    cal, test = holdout_split(["A", "B"], 0.3, 42)
    assert len(cal) == 1 and len(test) == 1


def test_assign_time_slot(ctx):
    cfg, *_ = ctx
    slots = cfg["time_slots"]
    assert assign_time_slot(pd.Timestamp("2026-10-20 08:45"), slots) == "morning_peak"
    assert assign_time_slot(pd.Timestamp("2026-10-20 18:10"), slots) == "evening_peak"
    assert assign_time_slot(pd.Timestamp("2026-10-20 00:30"), slots) == "night_offpeak"
    assert assign_time_slot(pd.Timestamp("2026-10-20 13:00"), slots) == "midday"


# ── edge speeds ──
def test_compare_edge_speeds(ctx):
    _, net, sims = ctx
    df = compare_edge_speeds(net, sims)
    assert not df.empty
    assert set(df["time_slot"]) <= set(SLOTS)
    assert np.allclose(df["error_kmh"], df["simulated_speed_kmh"] - df["observed_speed_kmh"])
    assert df["highway"].notna().all()


# ── manual observations + corridor hold-out ──
def _write_obs(tmp: Path) -> None:
    pd.DataFrame({
        "route_id": ["R01", "R01", "R02", "R03", "R04"],
        "datetime": ["2026-10-20 08:30", "2026-10-21 08:40", "2026-10-20 18:00", "2026-10-20 13:30", "2026-10-20 23:00"],
        "travel_time_s": [600, 660, 900, 400, 300],
        "free_flow_time_s": [240, 240, 300, 250, 280],
        "source": ["manual"] * 5,
    }).to_csv(tmp / "manual_observations_test.csv", index=False)
    # pipeline-schema file with an invalid row (zero time) that must be dropped
    pd.DataFrame({
        "route_id": ["R02", "R03"], "time_slot": ["morning_peak", None], "datetime": ["2026-10-22 09:00", "2026-10-22 19:00"],
        "free_flow_time_s": [300, 250], "observed_time_s": [750, 0], "source": ["manual", "manual"],
    }).to_csv(tmp / "manual_traffic.csv", index=False)


def test_load_manual_observations(tmp_path, ctx):
    cfg, *_ = ctx
    _write_obs(tmp_path)
    obs = load_manual_observations(tmp_path, cfg["time_slots"])
    assert len(obs) == 6  # 5 + 1 valid pipeline row
    assert obs["time_slot"].notna().all()
    assert (obs["congestion_ratio"] > 0).all()
    r01 = obs[obs["route_id"] == "R01"]
    assert set(r01["time_slot"]) == {"morning_peak"}
    assert load_manual_observations(tmp_path / "missing", cfg["time_slots"]).empty


def test_corridor_validation_and_ratio(tmp_path, ctx):
    cfg, net, sims = ctx
    _write_obs(tmp_path)
    obs = load_manual_observations(tmp_path, cfg["time_slots"])
    routes = pd.read_csv("config/sample_routes.csv")
    corr = corridor_validation(net, sims, obs, routes, 0.3, 42, 150)
    assert not corr.empty
    assert set(corr["split"]) <= {"calibration", "holdout"}
    assert "holdout" in set(corr["split"])
    ok = corr.dropna(subset=["simulated_ratio"])
    assert (ok["simulated_ratio"] >= 1.0 - 1e-9).all()  # BPR never faster than free flow
    # direct check of corridor ratio helper
    assert simulated_corridor_ratio(net.graph, sims["morning_peak"], 0, 0) is None


def test_bundle_integrity_checks(ctx):
    _, net, _ = ctx
    checks = bundle_integrity_checks(net, (0.9, 7.0))
    names = [c["check"] for c in checks]
    assert "Graph is strongly connected" in names
    assert "Copy-on-modify leaves baseline unchanged" in names
    copy_check = next(c for c in checks if c["check"].startswith("Copy-on-modify"))
    assert copy_check["passed"]


def test_run_validation_on_demo_bundle(ctx):
    cfg, net, sims = ctx
    rep = run_validation(net, sims, cfg, root=".")
    assert rep.reference_label == "synthetic"
    assert any("SYNTHETIC" in n for n in rep.notes)
    assert rep.edge_overall["n"] > 0
    # No accuracy target configured -> no pass/fail verdict is produced
    assert rep.mape_target_pct is None
    assert rep.holdout_meets_target is None


def test_run_validation_with_target(tmp_path, ctx):
    cfg, net, sims = ctx
    _write_obs(tmp_path / "data" / "raw" / "traffic") if (tmp_path / "data" / "raw" / "traffic").mkdir(parents=True) is None else None
    (tmp_path / "config").mkdir()
    pd.read_csv("config/sample_routes.csv").to_csv(tmp_path / "config" / "sample_routes.csv", index=False)
    cfg2 = {**cfg, "validation": {**cfg.get("validation", {}), "mape_target_pct": 1000.0}}
    rep = run_validation(net, sims, cfg2, root=tmp_path)
    assert rep.n_manual_obs == 6
    assert rep.holdout_metrics["n"] >= 1
    assert rep.holdout_meets_target is True


def test_validation_charts(ctx):
    cfg, net, sims = ctx
    rep = run_validation(net, sims, cfg, root=".")
    fig = build_validation_scatter(rep.edge_df, reference_label="synthetic reference")
    assert isinstance(fig, go.Figure)
    assert any(t.name == "parity (y = x)" for t in fig.data)
    bar = build_error_by_group_chart(rep.edge_by_slot, "time_slot", "Error by slot")
    assert len(bar.data) == 2

