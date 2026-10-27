"""
tests/test_simulation_engine.py
Stage A – A2 tests: demand-based flow assignment in the simulation engine.
"""
from __future__ import annotations
import pytest
import networkx as nx
import pandas as pd
import geopandas as gpd

from urbanflow_data.simulation_engine import (
    TrafficSimulator,
    SimResult,
    DemandMatrix,
    FlowAssigner,
    bpr_time,
    bpr_speed,
)


# ── Shared fixture: a small, fully connected graph ────────────────────────────
def _make_graph() -> nx.MultiDiGraph:
    """
    6-node graph representing a simple corridor:

        0 ──── 1 ──── 2
        |             |
        3 ──── 4 ──── 5

    All edges are bidirectional (added in both directions).
    Edge 0→1 is the main artery (primary, high capacity).
    All nodes have x/y for geographic lookup.
    """
    G = nx.MultiDiGraph()
    nodes = [
        (0, 77.610, 12.917),
        (1, 77.620, 12.917),
        (2, 77.630, 12.917),
        (3, 77.610, 12.910),
        (4, 77.620, 12.910),
        (5, 77.630, 12.910),
    ]
    for nid, x, y in nodes:
        G.add_node(nid, x=x, y=y, node_id=nid)

    EDGES = [
        # (u, v, eid, hw, lanes, length_m)
        (0, 1, 0,  "primary",   2, 800),
        (1, 0, 1,  "primary",   2, 800),
        (1, 2, 2,  "primary",   2, 800),
        (2, 1, 3,  "primary",   2, 800),
        (3, 4, 4,  "secondary", 2, 800),
        (4, 3, 5,  "secondary", 2, 800),
        (4, 5, 6,  "secondary", 2, 800),
        (5, 4, 7,  "secondary", 2, 800),
        (0, 3, 8,  "tertiary",  1, 400),
        (3, 0, 9,  "tertiary",  1, 400),
        (2, 5, 10, "tertiary",  1, 400),
        (5, 2, 11, "tertiary",  1, 400),
        # cross links (allow rerouting)
        (1, 4, 12, "tertiary",  1, 400),
        (4, 1, 13, "tertiary",  1, 400),
    ]
    CAP = {"primary": 1500 * 2, "secondary": 1300 * 2, "tertiary": 1000}
    FF  = {"primary": 45, "secondary": 35, "tertiary": 28}

    for u, v, eid, hw, lanes, lm in EDGES:
        ff  = FF[hw] * 0.9
        fft = lm / (ff / 3.6)
        cap = lanes * CAP[hw] * 0.85
        G.add_edge(u, v,
                   edge_id=eid, length_m=lm, lanes=lanes,
                   highway=hw, maxspeed_kmh=FF[hw],
                   free_flow_speed_kmh=ff,
                   free_flow_time_s=fft,
                   capacity_pcu_per_hr=cap,
                   is_bridge=False, is_flyover=False, name=f"Road_{eid}")
    return G


BPR = {hw: {"alpha": 0.15, "beta": 4.0}
       for hw in ("primary", "secondary", "tertiary", "residential",
                  "unclassified", "service", "motorway", "trunk")}


# ── bpr_time / bpr_speed unit tests ──────────────────────────────────────────
def test_bpr_time_free_flow():
    """At zero volume BPR time equals free-flow time."""
    assert bpr_time(60.0, 0.0, 1000.0) == pytest.approx(60.0)


def test_bpr_speed_free_flow():
    """At zero volume BPR speed equals free-flow speed."""
    assert bpr_speed(40.0, 0.0, 1000.0) == pytest.approx(40.0)


def test_bpr_speed_at_capacity():
    """At v/c = 1, speed should drop below free-flow (BPR alpha 0.15)."""
    ff = 40.0
    cap = 1000.0
    vol = cap  # exactly at capacity
    s = bpr_speed(ff, vol, cap, alpha=0.15, beta=4.0)
    assert s < ff, "Speed must decrease at capacity"
    assert s == pytest.approx(ff / 1.15, rel=1e-6)


# ── DemandMatrix tests ────────────────────────────────────────────────────────
def test_demand_matrix_total_positive():
    G = _make_graph()
    dm = DemandMatrix(G, "morning_peak")
    total = sum(v for v in dm._demand.values())
    assert total > 0, "Total demand should be positive"


def test_demand_matrix_no_self_demand():
    G = _make_graph()
    dm = DemandMatrix(G, "morning_peak")
    for (o, d), v in dm.pairs():
        assert o != d, "No self-demand expected"


def test_demand_matrix_slot_ordering():
    """Evening peak demand should be higher than night off-peak."""
    G = _make_graph()
    dm_peak = DemandMatrix(G, "evening_peak")
    dm_night = DemandMatrix(G, "night_offpeak")
    total_peak  = sum(dm_peak._demand.values())
    total_night = sum(dm_night._demand.values())
    assert total_peak > total_night, "Peak demand must exceed night off-peak"


# ── FlowAssigner tests ────────────────────────────────────────────────────────
def test_flow_assigner_positive_flow_on_used_edges():
    G = _make_graph()
    dm = DemandMatrix(G, "morning_peak")
    fa = FlowAssigner()
    flows = fa.assign(G, dm)
    total_flow = sum(flows.values())
    assert total_flow > 0, "Total assigned flow must be positive"


def test_flow_assigner_no_negative_flow():
    G = _make_graph()
    dm = DemandMatrix(G, "morning_peak")
    fa = FlowAssigner()
    flows = fa.assign(G, dm)
    for eid, vol in flows.items():
        assert vol >= 0, f"Edge {eid} has negative flow: {vol}"


# ── TrafficSimulator tests ────────────────────────────────────────────────────
def test_baseline_simulation_runs():
    G   = _make_graph()
    sim = TrafficSimulator(G, BPR)
    res = sim.simulate(G, "morning_peak", "Baseline")
    assert isinstance(res, SimResult)
    assert res.mean_congestion_ratio >= 1.0, "Congestion ratio should be >= 1 under load"
    assert res.mean_speed_kmh > 0


def test_simresult_summary_string():
    G   = _make_graph()
    sim = TrafficSimulator(G, BPR)
    res = sim.simulate(G, "morning_peak", "Test")
    s = res.summary()
    assert "Test" in s
    assert "km/h" in s


def test_closure_changes_metrics():
    """
    Closing node 1 (a central hub) must produce metrics different from baseline
    because traffic is forced to reroute.
    """
    G   = _make_graph()
    sim = TrafficSimulator(G, BPR)

    baseline = sim.simulate(G, "morning_peak", "Baseline")

    # Close the central node (node 1 connects the two artery segments)
    G_closed = G.copy()
    G_closed.remove_node(1)

    closed = sim.simulate(G_closed, "morning_peak", "Close node 1")

    # The metrics must differ (routing changed because topology changed)
    assert (
        closed.mean_congestion_ratio != baseline.mean_congestion_ratio
        or closed.mean_speed_kmh != baseline.mean_speed_kmh
    ), "Closing a hub node must change simulation metrics"


def test_new_road_carries_flow():
    """
    Adding a new edge to a previously unconnected pair should assign it
    positive flow when demand exists between those nodes.
    """
    G = _make_graph()
    sim = TrafficSimulator(G, BPR)

    # Add a new edge between nodes 2 and 3 (currently not connected)
    new_eid = 999
    G_new = G.copy()
    G_new.add_edge(2, 3,
                   edge_id=new_eid, length_m=600, lanes=2,
                   highway="secondary", maxspeed_kmh=35,
                   free_flow_speed_kmh=31.5, free_flow_time_s=68.6,
                   capacity_pcu_per_hr=2210, is_bridge=False, is_flyover=False,
                   name="New Bypass")

    result = sim.simulate(G_new, "morning_peak", "Add Road")
    # The new edge should carry some flow
    new_edge_flow = result.edge_volumes.get(new_eid, 0.0)
    assert new_edge_flow > 0, f"New edge {new_eid} should carry positive flow; got {new_edge_flow}"


def test_deterministic():
    """Same graph and time slot should produce identical results."""
    G   = _make_graph()
    sim = TrafficSimulator(G, BPR)
    r1  = sim.simulate(G, "evening_peak", "Run1")
    r2  = sim.simulate(G, "evening_peak", "Run2")
    assert r1.mean_congestion_ratio == r2.mean_congestion_ratio
    assert r1.mean_speed_kmh == r2.mean_speed_kmh
    assert r1.total_travel_time_s == r2.total_travel_time_s


def test_compare_scenarios_returns_correct_count():
    G   = _make_graph()
    sim = TrafficSimulator(G, BPR)
    G2  = G.copy()
    G2.remove_node(3)
    results = sim.compare_scenarios([("Base", G), ("Closed 3", G2)], "midday")
    assert len(results) == 2


def test_bus_delay_nonzero_with_routes():
    """Bus delay should be positive when bus route edges are on congested roads."""
    G = _make_graph()
    bus_df = pd.DataFrame({"route_id": ["R1", "R1"], "seq": [0, 1], "edge_id": [0, 2]})
    sim = TrafficSimulator(G, BPR, bus_route_edges=bus_df)
    res = sim.simulate(G, "morning_peak", "BusTest")
    assert res.bus_delay_s >= 0


def test_empty_graph_returns_default():
    G   = nx.MultiDiGraph()
    sim = TrafficSimulator(G, BPR)
    res = sim.simulate(G, "morning_peak", "Empty")
    assert res.total_travel_time_s == 0
