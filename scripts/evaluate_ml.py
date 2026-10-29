"""
scripts/evaluate_ml.py
======================
Stage C (C7): Evaluate UrbanFlow ML components (CongestionTrendPredictor & AnomalyDetector)
against naive baselines on the 70/30 hold-out split.

Rule (from docs/ANTIGRAVITY_PROMPTS.md):
  - Evaluate ML models on real bundle data; keep a model active only if it beats
    the naive baseline on the 30% hold-out split.

Usage:
    python scripts/evaluate_ml.py
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from urbanflow_data.config import get_data_dir, load_config
from urbanflow_data.ml_components import AnomalyDetector, CongestionTrendPredictor
from urbanflow_data.network_bundle import NetworkBundle, load_network
from urbanflow_data.optimizer import InterventionLibrary
from urbanflow_data.simulation_engine import TrafficSimulator
from urbanflow_data.validation_harness import error_metrics, holdout_split


def evaluate_ml_models(net: NetworkBundle, cfg: dict[str, Any]) -> dict[str, Any]:
    """
    Evaluate CongestionTrendPredictor (Ridge on time_slot + highway) against:
      1. Naive global-mean baseline (predicts training mean congestion_ratio)
      2. Naive road-class-only baseline (predicts training mean per highway class, ignoring time_slot)
    using a deterministic 70/30 edge-level hold-out split.
    Also evaluates AnomalyDetector on scenario library SimResults.
    """
    vcfg = cfg.get("validation", {}) or {}
    holdout_frac = float(vcfg.get("holdout_fraction", 0.30))
    seed = int(vcfg.get("holdout_seed", 42))

    hw_map = net.edges.set_index("edge_id")["highway"].astype(str).to_dict()
    df = net.edge_speeds.copy()
    df["highway"] = df["edge_id"].map(hw_map).fillna("unclassified")

    edge_ids = [str(e) for e in sorted(df["edge_id"].unique())]
    cal_eids, test_eids = holdout_split(edge_ids, holdout_frac, seed)
    cal_set = {int(e) for e in cal_eids}
    test_set = {int(e) for e in test_eids}

    train_df = df[df["edge_id"].isin(cal_set)].copy()
    test_df = df[df["edge_id"].isin(test_set)].copy()

    predictor = CongestionTrendPredictor(alpha=1.0).fit(train_df)

    # Predictions on hold-out test set
    y_true = test_df["congestion_ratio"].to_numpy(dtype=float)
    y_ml = np.array(
        [predictor.predict(str(r.time_slot), str(r.highway)) for r in test_df.itertuples()],
        dtype=float,
    )

    # Baseline 1: global training mean
    global_mean = float(train_df["congestion_ratio"].mean())
    y_base_global = np.full_like(y_true, global_mean)

    # Baseline 2: road-class mean (ignoring time_slot)
    class_means = train_df.groupby("highway")["congestion_ratio"].mean().to_dict()
    y_base_class = np.array(
        [float(class_means.get(str(r.highway), global_mean)) for r in test_df.itertuples()],
        dtype=float,
    )

    ml_metrics = error_metrics(y_true, y_ml)
    base_global_metrics = error_metrics(y_true, y_base_global)
    base_class_metrics = error_metrics(y_true, y_base_class)

    beats_global = (ml_metrics["rmse"] or 999.0) < (base_global_metrics["rmse"] or 999.0)
    beats_class = (ml_metrics["rmse"] or 999.0) < (base_class_metrics["rmse"] or 999.0)
    keep_predictor = bool(predictor.model_available and beats_global and beats_class)

    # Evaluate AnomalyDetector across scenario simulations
    sim = TrafficSimulator(
        net.graph,
        net.bpr_params,
        net.bus_route_edges if not net.bus_route_edges.empty else None,
    )
    lib = InterventionLibrary(cfg)
    sim_results = []
    for slot in ["night_offpeak", "morning_peak", "midday", "evening_peak"]:
        sim_results.append(sim.simulate(net.graph, slot, f"Baseline_{slot}"))
        for cand in lib.candidates()[:2]:
            G_scen = lib.apply(cand, net.graph)
            sim_results.append(sim.simulate(G_scen, slot, f"{cand['name']}_{slot}"))

    detector = AnomalyDetector(contamination=0.15).fit(sim_results)
    flagged = [r.scenario_name for r in sim_results if detector.is_anomaly(r)]

    return {
        "n_train_rows": int(len(train_df)),
        "n_test_rows": int(len(test_df)),
        "n_train_edges": len(cal_set),
        "n_test_edges": len(test_set),
        "predictor_available": predictor.model_available,
        "ml_ridge_metrics": ml_metrics,
        "baseline_global_mean_metrics": base_global_metrics,
        "baseline_class_mean_metrics": base_class_metrics,
        "beats_global_baseline": beats_global,
        "beats_class_baseline": beats_class,
        "keep_congestion_trend_predictor": keep_predictor,
        "anomaly_detector_available": detector.model_available,
        "anomaly_detector_n_samples": len(sim_results),
        "anomaly_flagged_scenarios": flagged,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate UrbanFlow ML components vs baselines")
    parser.add_argument("--data", default=None, help="Path to processed NetworkBundle")
    parser.add_argument(
        "--out",
        default=str(ROOT / "docs" / "ml_evaluation.json"),
        help="Output JSON path (default: docs/ml_evaluation.json)",
    )
    args = parser.parse_args()

    data_dir = get_data_dir(args.data) if args.data else get_data_dir(ROOT / "data" / "processed")
    cfg = load_config(root=ROOT)
    net = load_network(data_dir)

    report = evaluate_ml_models(net, cfg)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print("=" * 80)
    print("UrbanFlow ML Evaluation Report (70/30 Hold-Out Split)")
    print("=" * 80)
    print(f"Train edges: {report['n_train_edges']} ({report['n_train_rows']} rows)")
    print(f"Test edges:  {report['n_test_edges']} ({report['n_test_rows']} rows)")
    print(f"Ridge ML RMSE:            {report['ml_ridge_metrics']['rmse']:.4f} | MAE: {report['ml_ridge_metrics']['mae']:.4f} | MAPE: {report['ml_ridge_metrics']['mape_pct']:.2f}%")
    print(f"Class-Mean Baseline RMSE: {report['baseline_class_mean_metrics']['rmse']:.4f} | MAE: {report['baseline_class_mean_metrics']['mae']:.4f} | MAPE: {report['baseline_class_mean_metrics']['mape_pct']:.2f}%")
    print(f"Global-Mean Baseline RMSE:{report['baseline_global_mean_metrics']['rmse']:.4f} | MAE: {report['baseline_global_mean_metrics']['mae']:.4f} | MAPE: {report['baseline_global_mean_metrics']['mape_pct']:.2f}%")
    print(f"Keep CongestionTrendPredictor: {report['keep_congestion_trend_predictor']}")
    print(f"AnomalyDetector available:     {report['anomaly_detector_available']} ({report['anomaly_detector_n_samples']} runs, {len(report['anomaly_flagged_scenarios'])} flagged)")
    print("=" * 80)
    return 0


if __name__ == "__main__":
    sys.exit(main())
