"""tests/test_b2_dashboard_shell.py - Stage B2 tests for Dashboard Shell & Command Center."""
from __future__ import annotations

import py_compile
from pathlib import Path
import pytest
import plotly.graph_objects as go
import pandas as pd

from urbanflow_data.config import get_data_dir
from urbanflow_data.network_bundle import load_network
from urbanflow_data.simulation_engine import TrafficSimulator
from urbanflow_data.dashboard_ui import (
    get_custom_css,
    get_speed_color,
    build_network_map,
    build_highway_distribution_chart,
    build_speed_comparison_chart,
    build_bottleneck_table,
)


@pytest.fixture
def sample_network():
    data_dir = get_data_dir()
    return load_network(data_dir)


@pytest.fixture
def sample_sim_result(sample_network):
    net = sample_network
    sim = TrafficSimulator(
        G=net.graph,
        bpr_params=net.bpr_params,
        bus_route_edges=net.bus_route_edges if not net.bus_route_edges.empty else None,
    )
    return sim.simulate(net.graph, time_slot="morning_peak", scenario_name="Baseline")


def test_custom_css():
    css = get_custom_css()
    assert isinstance(css, str)
    assert "<style>" in css
    assert ".command-header" in css
    assert ".kpi-card" in css
    assert "#0B0F19" in css


def test_speed_color_scale():
    c_slow = get_speed_color(5.0)
    c_mid = get_speed_color(22.5)
    c_fast = get_speed_color(45.0)

    for c in (c_slow, c_mid, c_fast):
        assert c.startswith("rgb(")
        assert c.endswith(")")


def test_build_network_map_traces(sample_network, sample_sim_result):
    # Online mode map
    fig_online = build_network_map(sample_network, sim_result=sample_sim_result, offline=False)
    assert isinstance(fig_online, go.Figure)
    assert len(fig_online.data) > 0

    # Offline mode map
    fig_offline = build_network_map(sample_network, sim_result=sample_sim_result, offline=True)
    assert isinstance(fig_offline, go.Figure)
    assert len(fig_offline.data) > 0


def test_build_highway_distribution_chart(sample_network):
    fig = build_highway_distribution_chart(sample_network.edges)
    assert isinstance(fig, go.Figure)
    assert len(fig.data) == 1
    assert fig.data[0].type == "pie"


def test_build_speed_comparison_chart(sample_network, sample_sim_result):
    fig = build_speed_comparison_chart(sample_network.edges, sample_sim_result)
    assert isinstance(fig, go.Figure)
    assert len(fig.data) == 2
    assert fig.data[0].type == "bar"


def test_build_bottleneck_table(sample_network, sample_sim_result):
    df = build_bottleneck_table(sample_network.edges, sample_sim_result)
    assert isinstance(df, pd.DataFrame)
    if not df.empty:
        assert "Edge ID" in df.columns
        assert "Severity" in df.columns


def test_demo_app_syntax():
    """Ensure demo/app.py compiles without syntax errors."""
    app_path = Path("demo/app.py").resolve()
    assert app_path.exists()
    py_compile.compile(str(app_path), doraise=True)
