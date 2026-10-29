"""tests/test_b9_report_generator.py - Stage B9 tests for PDF Planner Report Generator."""
from __future__ import annotations

import py_compile
from pathlib import Path
import pytest

from urbanflow_data.config import get_data_dir, load_config
from urbanflow_data.network_bundle import load_network
from urbanflow_data.simulation_engine import TrafficSimulator
from urbanflow_data.decision_layer import (
    ScenarioMetrics,
    score_scenario,
    verdict,
    explain,
)
from urbanflow_data.report_generator import generate_planner_pdf_report


def test_generate_pdf_report(tmp_path):
    cfg = load_config()
    net = load_network(get_data_dir())
    sim = TrafficSimulator(net.graph, net.bpr_params)

    base = sim.simulate(net.graph, "morning_peak", "Baseline")
    closed = net.close_node(0)
    scen = sim.simulate(closed.graph, "morning_peak", "Close Silk Board")

    sm = ScenarioMetrics("Close Silk Board", scen, base, cost_index=0.1, feasibility=0.9)
    weights = cfg["decision_intelligence"]["criteria_weights"]
    thresholds = cfg["decision_intelligence"]["verdict_thresholds"]

    score = score_scenario(sm, weights)
    label = verdict(score, thresholds)
    exp = explain(sm, score, label)

    pdf_file = tmp_path / "test_report.pdf"
    pdf_bytes = generate_planner_pdf_report(
        scenario_metrics=sm,
        score=score,
        verdict_label=label,
        confidence=0.85,
        explanation=exp,
        time_slot="morning_peak",
        output_path=pdf_file,
        weights=weights,
    )

    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 1000
    assert pdf_bytes.startswith(b"%PDF")
    assert pdf_file.exists()
    assert pdf_file.stat().st_size == len(pdf_bytes)


def test_demo_app_compiles_b9():
    py_compile.compile(str(Path("demo/app.py").resolve()), doraise=True)
