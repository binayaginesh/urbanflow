"""tests/test_c7_validation_and_ml.py - Stage C7 ML evaluation & VALIDATION.md tests."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from evaluate_ml import evaluate_ml_models
from urbanflow_data.config import get_data_dir, load_config
from urbanflow_data.network_bundle import load_network


def test_ml_evaluation_beats_baselines():
    cfg = load_config(root=ROOT)
    net = load_network(get_data_dir(ROOT / "data" / "processed"))
    rep = evaluate_ml_models(net, cfg)
    assert rep["predictor_available"] is True
    assert rep["beats_global_baseline"] is True
    assert rep["beats_class_baseline"] is True
    assert rep["keep_congestion_trend_predictor"] is True
    assert rep["anomaly_detector_available"] is True


def test_validation_and_limitations_docs_exist_and_honest():
    val_doc = (ROOT / "docs" / "VALIDATION.md").read_text(encoding="utf-8")
    lim_doc = (ROOT / "docs" / "LIMITATIONS.md").read_text(encoding="utf-8")
    cal_doc = (ROOT / "docs" / "calibration_report.md").read_text(encoding="utf-8")
    assert "70/30" in val_doc
    assert "imputed_class_avg" in val_doc
    assert "CongestionTrendPredictor" in val_doc
    assert "92.4%" in lim_doc
    assert len(cal_doc) > 100
