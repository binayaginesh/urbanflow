"""tests/test_b3_scenario_lab.py - Stage B3 tests for Scenario Lab visualizations and verdict cards."""
from __future__ import annotations

import py_compile
from pathlib import Path
import pytest
import plotly.graph_objects as go

from urbanflow_data.config import get_data_dir, load_config
from urbanflow_data.network_bundle import load_network
from urbanflow_data.simulation_engine import TrafficSimulator
from urbanflow_data.decision_layer import (
    ScenarioMetrics,
    score_scenario,
    verdict,
    explain,
    monte_carlo_confidence,
)
from urbanflow_data.dashboard_ui import (
    build_change_delta_map,
    build_flow_animation_and_heatmap,
    build_verdict_card_html,
    build_waterfall_chart,
)


@pytest.fixture
def sim_setup():
    data_dir = get_data_dir()
    cfg = load_config()
    net = load_network(data_dir)
    sim = TrafficSimulator(
        G=net.graph,
        bpr_params=net.bpr_params,
        bus_route_edges=net.bus_route_edges if not net.bus_route_edges.empty else None,
    )
    base_res = sim.simulate(net.graph, time_slot="morning_peak", scenario_name="Baseline")
    scen_net = net.close_node(0)
    scen_res = sim.simulate(scen_net.graph, time_slot="morning_peak", scenario_name="Close Silk Board")
    return cfg, net, sim, base_res, scen_net, scen_res


def test_build_change_delta_map(sim_setup):
    cfg, net, sim, base_res, scen_net, scen_res = sim_setup
    fig = build_change_delta_map(net, base_res, scen_res, offline=True)
    assert isinstance(fig, go.Figure)
    assert len(fig.data) > 0


def test_build_flow_animation_and_heatmap(sim_setup):
    cfg, net, sim, base_res, scen_net, scen_res = sim_setup
    fig = build_flow_animation_and_heatmap(scen_net, scen_res, offline=True)
    assert isinstance(fig, go.Figure)
    assert len(fig.data) > 0


def test_build_verdict_card_html(sim_setup):
    cfg, net, sim, base_res, scen_net, scen_res = sim_setup
    sm = ScenarioMetrics("Close Silk Board", scen_res, base_res, cost_index=0.1, feasibility=0.9)
    weights = cfg["decision_intelligence"]["criteria_weights"]
    thresholds = cfg["decision_intelligence"]["verdict_thresholds"]

    score = score_scenario(sm, weights)
    label = verdict(score, thresholds)
    exp = explain(sm, score, label)
    conf = 0.95

    html = build_verdict_card_html(score, label, conf, exp, sm)
    assert isinstance(html, str)
    assert label in html
    assert f"{score:.3f}" in html
    assert "95.0%" in html
    assert "Analytical Justification" in html


def test_build_waterfall_chart(sim_setup):
    cfg, net, sim, base_res, scen_net, scen_res = sim_setup
    sm = ScenarioMetrics("Close Silk Board", scen_res, base_res, cost_index=0.1, feasibility=0.9)
    weights = cfg["decision_intelligence"]["criteria_weights"]
    score = score_scenario(sm, weights)

    fig = build_waterfall_chart(sm, score, weights)
    assert isinstance(fig, go.Figure)
    assert len(fig.data) == 1
    assert fig.data[0].type == "waterfall"


def test_demo_app_compiles():
    app_path = Path("demo/app.py").resolve()
    py_compile.compile(str(app_path), doraise=True)
