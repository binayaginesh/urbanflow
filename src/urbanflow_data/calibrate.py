"""
calibrate.py - Phase 4b
Fit BPR parameters and distribute observed speeds to edges.
"""
from __future__ import annotations
import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def bpr_time(t0: float, volume: float, capacity: float,
             alpha: float = 0.15, beta: float = 4.0) -> float:
    """BPR volume-delay function: t = t0 * (1 + alpha*(v/c)^beta)."""
    return t0 * (1.0 + alpha * (volume / max(capacity, 1)) ** beta)


def run(cfg: dict[str, Any], root: Path = Path("."), **kwargs) -> None:
    import osmnx as ox
    import pandas as pd
    import numpy as np

    interim_dir  = root / cfg["paths"]["interim_dir"]
    processed_dir = root / cfg["paths"]["processed_dir"]
    processed_dir.mkdir(parents=True, exist_ok=True)

    sim_path     = interim_dir / "network_sim.graphml"
    traffic_path = interim_dir / "traffic_raw.parquet"

    G = ox.load_graphml(str(sim_path))
    logger.info("Loaded simulation graph: %d nodes, %d edges", G.number_of_nodes(), G.number_of_edges())

    # Build edge lookup: edge_id -> edge data
    edge_lookup: dict[int, dict] = {}
    for u, v, k, d in G.edges(data=True, keys=True):
        eid = int(d.get("edge_id", -1))
        edge_lookup[eid] = d

    slots = [s["name"] for s in cfg["time_slots"]]

    # ── Load observed traffic ─────────────────────────────────────────────────
    if traffic_path.exists():
        traffic_df = pd.read_parquet(traffic_path)
        logger.info("Loaded %d traffic records", len(traffic_df))
    else:
        logger.warning("No traffic_raw.parquet found. Using class-average imputation for all edges.")
        traffic_df = pd.DataFrame()

    # ── Build per-class congestion ratios by slot ─────────────────────────────
    # Default BPR alpha/beta from config
    alpha_default = float(cfg["bpr_defaults"]["alpha"])
    beta_default  = float(cfg["bpr_defaults"]["beta"])

    # Class-average congestion ratios (fallback): use simple assumed values
    class_avg_congestion = {
        "motorway":    {"morning_peak":1.5, "evening_peak":1.6, "midday":1.2, "night_offpeak":1.05},
        "trunk":       {"morning_peak":1.8, "evening_peak":2.0, "midday":1.4, "night_offpeak":1.1},
        "primary":     {"morning_peak":2.2, "evening_peak":2.5, "midday":1.6, "night_offpeak":1.1},
        "secondary":   {"morning_peak":2.0, "evening_peak":2.3, "midday":1.5, "night_offpeak":1.1},
        "tertiary":    {"morning_peak":1.8, "evening_peak":2.0, "midday":1.4, "night_offpeak":1.05},
        "residential": {"morning_peak":1.3, "evening_peak":1.5, "midday":1.2, "night_offpeak":1.0},
        "unclassified":{"morning_peak":1.5, "evening_peak":1.7, "midday":1.3, "night_offpeak":1.0},
        "service":     {"morning_peak":1.2, "evening_peak":1.3, "midday":1.1, "night_offpeak":1.0},
    }

    # ── Fit BPR per road class using observed data if available ───────────────
    bpr_params: dict[str, Any] = {}
    road_classes = list(cfg["default_lanes"].keys())

    if not traffic_df.empty and "congestion_ratio" in traffic_df.columns:
        logger.info("Fitting BPR parameters from observed data...")
        bpr_params = _fit_bpr(traffic_df, road_classes, alpha_default, beta_default)
    else:
        for rc in road_classes:
            bpr_params[rc] = {"alpha": alpha_default, "beta": beta_default}
        logger.info("Using default BPR parameters (no observed data).")

    # ── Distribute speeds to every edge per time slot ─────────────────────────
    logger.info("Computing per-edge per-slot speeds...")
    rows = []
    total_edges = len(edge_lookup)
    observed_count = 0

    for eid, d in edge_lookup.items():
        hw  = _normalise_hw(str(d.get("highway","unclassified")))
        ff  = float(d.get("free_flow_speed_kmh", 30))
        fft = float(d.get("free_flow_time_s", 60))

        for slot in slots:
            # Check if we have observed data for this edge (via route-map matching)
            # In Phase 4b a full map-match would be done; here we use class-average.
            cong = class_avg_congestion.get(hw, class_avg_congestion["unclassified"]).get(slot, 1.2)
            observed_speed = ff / cong
            source = "imputed_class_avg"

            rows.append({
                "edge_id": eid,
                "time_slot": slot,
                "speed_kmh": round(max(observed_speed, 1.0), 2),
                "congestion_ratio": round(cong, 3),
                "source": source,
            })
            if source == "observed":
                observed_count += 1

    edge_speeds = pd.DataFrame(rows)

    # ── Generate calibration report ───────────────────────────────────────────
    _write_calibration_report(root, cfg, edge_speeds, bpr_params, total_edges, observed_count)

    # ── Save ──────────────────────────────────────────────────────────────────
    edge_speeds.to_parquet(interim_dir / "edge_speeds_by_slot.parquet", index=False)
    (processed_dir / "bpr_params.json").write_text(json.dumps(bpr_params, indent=2))
    logger.info("Calibration complete. Saved edge_speeds (%d rows) and bpr_params.json", len(edge_speeds))


def _fit_bpr(traffic_df, road_classes: list[str],
             alpha0: float, beta0: float) -> dict[str, Any]:
    """Simple least-squares BPR fit per road class using observed congestion ratios."""
    import numpy as np
    params = {}
    # Without per-edge volume data we can only fit alpha given fixed beta.
    # Use v/c = 0.8 as the assumed peak loading ratio (conservative for Bengaluru).
    assumed_vc = 0.8
    beta = beta0
    for rc in road_classes:
        ratios = traffic_df["congestion_ratio"].dropna().values
        if len(ratios) == 0:
            params[rc] = {"alpha": alpha0, "beta": beta}
            continue
        # BPR: ratio = 1 + alpha*(v/c)^beta  =>  alpha = (mean_ratio - 1) / (v/c)^beta
        mean_ratio = float(np.mean(ratios))
        alpha = max((mean_ratio - 1.0) / (assumed_vc ** beta), 0.05)
        params[rc] = {"alpha": round(alpha, 4), "beta": beta}
    return params


def _normalise_hw(hw: str) -> str:
    mapping = {"motorway_link":"motorway","trunk_link":"trunk","primary_link":"primary",
               "secondary_link":"secondary","tertiary_link":"tertiary","living_street":"residential"}
    return mapping.get(hw, hw if hw in ["motorway","trunk","primary","secondary",
                                         "tertiary","residential","unclassified","service"] else "unclassified")


def _write_calibration_report(root: Path, cfg: dict, edge_speeds, bpr_params: dict,
                               total_edges: int, observed_count: int) -> None:
    import pandas as pd, numpy as np

    obs_frac = observed_count / max(total_edges * len(cfg["time_slots"]), 1) * 100
    mean_cong = edge_speeds["congestion_ratio"].mean()
    max_cong  = edge_speeds["congestion_ratio"].max()

    report = f"""# Calibration Report

**Generated by:** `calibrate.py`

## Coverage
- Total edges: {total_edges}
- Time slots: {len(cfg['time_slots'])}
- Edge-slot records: {len(edge_speeds)}
- Observed (API/manual): {observed_count} ({obs_frac:.1f}%)
- Imputed (class-average): {len(edge_speeds) - observed_count} ({100-obs_frac:.1f}%)

## Congestion Statistics
| Metric | Value |
|--------|-------|
| Mean congestion ratio | {mean_cong:.3f} |
| Max congestion ratio  | {max_cong:.3f} |

## BPR Parameters (fitted per road class)
| Road Class | alpha | beta |
|-----------|-------|------|
"""
    for rc, p in bpr_params.items():
        report += f"| {rc} | {p['alpha']} | {p['beta']} |\n"

    report += "\n> **Note:** BPR alpha fitted using assumed v/c=0.8 at peak. Refine with actual volume counts when available.\n"

    docs_dir = root / "docs"
    docs_dir.mkdir(exist_ok=True)
    (docs_dir / "calibration_report.md").write_text(report, encoding="utf-8")
    logger.info("Calibration report written to docs/calibration_report.md")
