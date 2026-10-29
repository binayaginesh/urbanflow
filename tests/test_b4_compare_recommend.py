"""tests/test_b4_compare_recommend.py - Stage B4 tests for Compare & Recommend page and AI Suggests."""
from __future__ import annotations

import py_compile
from pathlib import Path
import pytest
import plotly.graph_objects as go
import pandas as pd

from urbanflow_data.config import get_data_dir, load_config
from urbanflow_data.network_bundle import load_network
from urbanflow_data.optimizer import suggest_top3
from urbanflow_data.dashboard_ui import (
    build_comparison_matrix,
    build_comparison_bar_chart,
    build_ai_suggest_card_html,
)


def test_build_comparison_matrix():
    mock_data = [
        {"name": "Base", "verdict": "BASELINE", "score": 0.5, "speed": 20.0, "delta_speed": 0.0,
         "congestion": 4.4, "delta_congestion": 0.0, "travel_time_min": 180.0, "delta_tt_min": 0.0,
         "cost_index": 0.0, "feasibility": 1.0},
        {"name": "Scenario 1", "verdict": "RECOMMENDED", "score": 0.75, "speed": 25.0, "delta_speed": 5.0,
         "congestion": 3.2, "delta_congestion": -1.2, "travel_time_min": 140.0, "delta_tt_min": -40.0,
         "cost_index": 0.2, "feasibility": 0.95},
    ]
    df = build_comparison_matrix(mock_data)
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 2
    assert "Scenario" in df.columns
    assert "Speed Δ" in df.columns
    assert df.loc[1, "Verdict"] == "RECOMMENDED"


def test_build_comparison_bar_chart():
    mock_data = [
        {"name": "Base", "verdict": "BASELINE", "speed": 20.0},
        {"name": "Scenario 1", "verdict": "RECOMMENDED", "speed": 25.0},
    ]
    fig = build_comparison_bar_chart(mock_data, metric="speed", title="Speed Comparison")
    assert isinstance(fig, go.Figure)
    assert len(fig.data) == 1
    assert fig.data[0].type == "bar"


def test_suggest_top3_integration():
    data_dir = get_data_dir()
    cfg = load_config()
    net = load_network(data_dir)

    top3 = suggest_top3(
        base_graph=net.graph,
        bpr_params=net.bpr_params,
        time_slot="morning_peak",
        cfg=cfg,
        bus_route_edges=net.bus_route_edges if not net.bus_route_edges.empty else None,
    )
    assert len(top3) > 0
    assert len(top3) <= 3
    for s in top3:
        assert s.topsis_score >= 0.0
        assert s.verdict_label in ("RECOMMENDED", "MODERATE", "NOT RECOMMENDED")
        card_html = build_ai_suggest_card_html(1, s)
        assert isinstance(card_html, str)
        assert s.name in card_html


def test_demo_app_compiles_b4():
    app_path = Path("demo/app.py").resolve()
    py_compile.compile(str(app_path), doraise=True)
