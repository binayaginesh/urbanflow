"""
scripts/run_library.py
======================
Stage C (C6): Evaluate the full candidate intervention library from config.yaml
across all configured time slots on the active NetworkBundle (default: data/processed),
report metrics, composite scores, TOPSIS rankings, and 3-tier verdicts, and save
a structured summary to docs/library_results.json.

Usage:
    python scripts/run_library.py
    python scripts/run_library.py --data data/processed --out docs/library_results.json
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from urbanflow_data.config import get_data_dir, load_config
from urbanflow_data.decision_layer import (
    ScenarioMetrics,
    explain,
    score_scenario,
    topsis_rank,
    verdict,
)
from urbanflow_data.network_bundle import NetworkBundle, load_network
from urbanflow_data.optimizer import InterventionLibrary
from urbanflow_data.simulation_engine import TrafficSimulator


def evaluate_library(
    net: NetworkBundle,
    cfg: dict[str, Any],
    slots: list[str] | None = None,
) -> dict[str, Any]:
    """
    Evaluate all optimizer_candidates in *cfg* across *slots* on *net*.

    Returns a dictionary with baseline metrics per slot, candidate evaluations
    per slot, and overall verdict tier counts.
    """
    di = cfg.get("decision_intelligence", {})
    weights = di.get(
        "criteria_weights",
        {
            "congestion_ratio": 0.35,
            "speed_kmh": 0.30,
            "bus_delay_s": 0.20,
            "emissions_index": 0.15,
        },
    )
    thresholds = di.get("verdict_thresholds", {"recommended": 0.60, "moderate": 0.40})
    if slots is None:
        slots = [s["name"] for s in cfg.get("time_slots", [])]

    library = InterventionLibrary(cfg)
    candidates = library.candidates()
    bus_edges = net.bus_route_edges if not net.bus_route_edges.empty else None
    sim = TrafficSimulator(net.graph, net.bpr_params, bus_edges)

    by_slot: dict[str, Any] = {}
    tier_counts: Counter[str] = Counter()
    peak_tier_counts: Counter[str] = Counter()

    for slot in slots:
        base = sim.simulate(net.graph, slot, "Baseline")
        scen_metrics: list[ScenarioMetrics] = []
        comp_scores: dict[str, float] = {}
        cand_meta: dict[str, dict[str, Any]] = {}

        for cand in candidates:
            name = cand["name"]
            G_scen = library.apply(cand, net.graph)
            res = sim.simulate(G_scen, slot, name)
            sm = ScenarioMetrics(
                scenario_name=name,
                sim=res,
                baseline=base,
                cost_index=float(cand.get("cost_index", 0.0)),
                feasibility=float(cand.get("feasibility", 1.0)),
            )
            scen_metrics.append(sm)
            comp_scores[name] = score_scenario(sm, weights)
            cand_meta[name] = cand

        scored_pairs = [(sm, comp_scores[sm.scenario_name]) for sm in scen_metrics]
        ranked = topsis_rank(scored_pairs, weights) if scored_pairs else []
        topsis_map = {name: float(ts) for name, ts in ranked}

        rows = []
        for sm in scen_metrics:
            name = sm.scenario_name
            cscore = round(comp_scores[name], 4)
            tscore = round(topsis_map.get(name, 0.0), 4)
            vlabel = verdict(cscore, thresholds)
            tier_counts[vlabel] += 1
            if slot in ("morning_peak", "evening_peak"):
                peak_tier_counts[vlabel] += 1
            meta = cand_meta[name]
            rows.append(
                {
                    "name": name,
                    "type": meta.get("type"),
                    "time_slot": slot,
                    "mean_congestion_ratio": sm.sim.mean_congestion_ratio,
                    "delta_congestion": round(sm.delta_congestion, 4),
                    "mean_speed_kmh": sm.sim.mean_speed_kmh,
                    "delta_speed_kmh": round(sm.delta_speed, 3),
                    "bus_delay_s": sm.sim.bus_delay_s,
                    "delta_bus_delay_s": round(sm.delta_bus_delay, 2),
                    "emissions_index": sm.sim.emissions_index,
                    "delta_emissions": round(sm.delta_emissions, 4),
                    "cost_index": sm.cost_index,
                    "estimated_cost_inr_crore": meta.get("estimated_cost_inr_crore"),
                    "feasibility": sm.feasibility,
                    "composite_score": cscore,
                    "topsis_score": tscore,
                    "verdict": vlabel,
                    "explanation": explain(sm, cscore, vlabel),
                }
            )

        rows.sort(key=lambda r: r["topsis_score"], reverse=True)
        by_slot[slot] = {
            "baseline": {
                "mean_congestion_ratio": base.mean_congestion_ratio,
                "mean_speed_kmh": base.mean_speed_kmh,
                "bus_delay_s": base.bus_delay_s,
                "emissions_index": base.emissions_index,
                "total_travel_time_s": round(base.total_travel_time_s, 1),
            },
            "candidates": rows,
        }

    return {
        "network": {
            "nodes": net.graph.number_of_nodes(),
            "edges": net.graph.number_of_edges(),
            "bus_routes": int(len(net.bus_routes)),
            "version": net.meta.get("version", "0.1.0"),
        },
        "verdict_thresholds": thresholds,
        "criteria_weights": weights,
        "verdict_tier_counts_all_slots": dict(tier_counts),
        "verdict_tier_counts_peak_slots": dict(peak_tier_counts),
        "slots": by_slot,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run full UrbanFlow intervention library")
    parser.add_argument("--data", default=None, help="Path to processed NetworkBundle")
    parser.add_argument(
        "--out",
        default=str(ROOT / "docs" / "library_results.json"),
        help="Output JSON path (default: docs/library_results.json)",
    )
    args = parser.parse_args()

    data_dir = get_data_dir(args.data) if args.data else get_data_dir(ROOT / "data" / "processed")
    cfg = load_config(root=ROOT)
    net = load_network(data_dir)

    report = evaluate_library(net, cfg)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print("=" * 88)
    print(
        f"UrbanFlow Scenario Library Report | nodes={report['network']['nodes']} "
        f"edges={report['network']['edges']} | thresholds={report['verdict_thresholds']}"
    )
    print("=" * 88)
    for slot, sdata in report["slots"].items():
        b = sdata["baseline"]
        print(
            f"\n[{slot}] Baseline: Cong={b['mean_congestion_ratio']:.3f}x | "
            f"Speed={b['mean_speed_kmh']:.2f} km/h | BusDelay={b['bus_delay_s']:.1f}s | "
            f"Emis={b['emissions_index']:.3f}x"
        )
        print("-" * 88)
        for idx, c in enumerate(sdata["candidates"], 1):
            print(
                f"  #{idx} {c['name']:44s} | dCong={c['delta_congestion']:+.3f} | "
                f"dBus={c['delta_bus_delay_s']:+7.1f}s | Comp={c['composite_score']:.4f} | "
                f"TOPSIS={c['topsis_score']:.4f} | {c['verdict']}"
            )
    print("\n" + "=" * 88)
    print("Peak-slot verdict tier distribution:", report["verdict_tier_counts_peak_slots"])
    print("All-slot verdict tier distribution: ", report["verdict_tier_counts_all_slots"])
    print(f"Saved JSON report to: {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
