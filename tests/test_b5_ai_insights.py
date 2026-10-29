"""tests/test_b5_ai_insights.py - Stage B5 tests for AI Insights, ML Trend Predictor, and Anomaly Detector."""
from __future__ import annotations

import py_compile
from pathlib import Path
import pytest
import plotly.graph_objects as go
import pandas as pd

from urbanflow_data.config import get_data_dir, load_config
from urbanflow_data.network_bundle import load_network
from urbanflow_data.simulation_engine import TrafficSimulator
from urbanflow_data.ml_components import CongestionTrendPredictor, AnomalyDetector
from urbanflow_data.dashboard_ui import (
    build_trend_prediction_chart,
    build_anomaly_gauge,
)


@pytest.fixture
def trained_models():
    data_dir = get_data_dir()
    net = load_network(data_dir)
    sim = TrafficSimulator(net.graph, net.bpr_params)

    # Train predictor
    df_hist = net.edge_speeds.merge(net.edges[["edge_id", "highway"]], on="edge_id", how="left")
    predictor = CongestionTrendPredictor()
    predictor.fit(df_hist)

    # Train detector
    ensemble = []
    for s in ["morning_peak", "evening_peak", "midday", "night_offpeak"]:
        ensemble.append(sim.simulate(net.graph, s, "Base"))
        ensemble.append(sim.simulate(net.close_node(0).graph, s, "Close 0"))
    detector = AnomalyDetector()
    detector.fit(ensemble)

    base_res = ensemble[0]
    return predictor, detector, base_res


def test_build_trend_prediction_chart(trained_models):
    predictor, _, _ = trained_models
    assert predictor.model_available
    fig = build_trend_prediction_chart(predictor, highway_class="primary")
    assert isinstance(fig, go.Figure)
    assert len(fig.data) == 1
    assert fig.data[0].type == "scatter"


def test_build_anomaly_gauge(trained_models):
    _, detector, base_res = trained_models
    assert detector.model_available
    score = detector.score(base_res)
    is_anom = detector.is_anomaly(base_res)

    fig = build_anomaly_gauge(score, is_anom)
    assert isinstance(fig, go.Figure)
    assert len(fig.data) == 1
    assert fig.data[0].type == "indicator"


def test_demo_app_compiles_b5():
    app_path = Path("demo/app.py").resolve()
    py_compile.compile(str(app_path), doraise=True)
