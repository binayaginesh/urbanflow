"""tests/test_b6_transit_metro.py - Stage B6 tests for transit route metrics and metro interchange analysis."""
from __future__ import annotations

import py_compile
from pathlib import Path

import plotly.graph_objects as go
import pytest

from urbanflow_data.config import get_data_dir
from urbanflow_data.network_bundle import load_network
from urbanflow_data.simulation_engine import TrafficSimulator
from urbanflow_data.transit_analysis import (
    compare_route_metrics,
    compute_route_metrics,
    haversine_m,
    headway_for_slot,
    metro_interchanges,
)
from urbanflow_data.dashboard_ui import build_route_delay_chart, build_transit_map


@pytest.fixture(scope="module")
def transit_ctx():
    net = load_network(get_data_dir())
    sim = TrafficSimulator(net.graph, net.bpr_params, bus_route_edges=net.bus_route_edges)
    base = sim.simulate(net.graph, "morning_peak", "Baseline")
    closed = net.close_node(0)
    scen = sim.simulate(closed.graph, "morning_peak", "Close 0")
    return net, base, closed, scen


def test_haversine_known_distance():
    # ~1 degree latitude ≈ 111.2 km
    assert haversine_m(12.0, 77.0, 13.0, 77.0) == pytest.approx(111_195, rel=1e-3)
    assert haversine_m(12.9, 77.6, 12.9, 77.6) == 0.0


def test_headway_peak_vs_offpeak():
    row = {"peak_headway_min": 5, "offpeak_headway_min": 12}
    assert headway_for_slot(row, "morning_peak") == 5.0
    assert headway_for_slot(row, "evening_peak") == 5.0
    assert headway_for_slot(row, "midday") == 12.0
    assert headway_for_slot({"peak_headway_min": None}, "morning_peak") is None


def test_route_metrics_baseline(transit_ctx):
    net, base, _, _ = transit_ctx
    df = compute_route_metrics(net, base, "morning_peak", scenario_graph=net.graph)
    assert len(df) == len(net.bus_routes)
    assert (df["edges_disrupted"] == 0).all()
    assert (df["sim_running_time_min"] >= df["ff_running_time_min"] - 1e-9).all()
    assert (df["delay_min"] >= 0).all()
    # buses/hr is derived only from the recorded headway
    for _, r in df.iterrows():
        assert r["buses_per_hr"] == pytest.approx(60.0 / r["headway_min"], abs=0.01)


def test_route_metrics_closure_disrupts_routes(transit_ctx):
    net, base, closed, scen = transit_ctx
    base_df = compute_route_metrics(net, base, "morning_peak", scenario_graph=net.graph)
    scen_df = compute_route_metrics(net, scen, "morning_peak", scenario_graph=closed.graph)
    # Node 0 (Silk Board) touches at least one bus route edge in the demo data
    touching = net.edges[(net.edges["u"] == 0) | (net.edges["v"] == 0)]["edge_id"].tolist()
    route_eids = set(net.bus_route_edges["edge_id"].astype(int))
    if route_eids & set(touching):
        assert scen_df["edges_disrupted"].sum() > 0
    cmp_df = compare_route_metrics(base_df, scen_df)
    assert set(cmp_df["route_id"]) == set(base_df["route_id"])
    assert "delta_running_time_min" in cmp_df.columns


def test_metro_interchanges(transit_ctx):
    net, *_ = transit_ctx
    df = metro_interchanges(net, walk_radius_m=400)
    assert len(df) == len(net.metro_stations)
    assert (df["distance_m"] >= 0).all()
    # A zero radius can only match stations sitting exactly on a junction
    df0 = metro_interchanges(net, walk_radius_m=0)
    assert df0["is_interchange"].sum() <= df["is_interchange"].sum()


def test_transit_charts(transit_ctx):
    net, base, closed, scen = transit_ctx
    base_df = compute_route_metrics(net, base, "morning_peak", scenario_graph=net.graph)
    scen_df = compute_route_metrics(net, scen, "morning_peak", scenario_graph=closed.graph)
    inter = metro_interchanges(net, 400)
    fig = build_transit_map(net, scen_df, inter, scenario_graph=closed.graph)
    assert isinstance(fig, go.Figure)
    names = [t.name for t in fig.data]
    assert "Namma Metro station" in names
    assert any(n and n.startswith("Route ") for n in names)
    bar = build_route_delay_chart(compare_route_metrics(base_df, scen_df))
    assert len(bar.data) == 2


def test_demo_app_compiles_b6():
    py_compile.compile(str(Path("demo/app.py").resolve()), doraise=True)

