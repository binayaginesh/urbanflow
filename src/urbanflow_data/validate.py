"""
validate.py - Phase 5b
Automated correctness checks on the processed bundle.
Returns True if all checks pass, False otherwise.
"""
from __future__ import annotations
import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)
PASS = "\u2713"; FAIL = "\u2717"


def run(cfg: dict[str, Any], root: Path = Path("."), **kwargs) -> bool:
    import osmnx as ox
    import networkx as nx
    import pandas as pd

    processed_dir = root / cfg["paths"]["processed_dir"]
    graphml_path  = processed_dir / "network.graphml"
    edges_path    = processed_dir / "edges.parquet"

    if not graphml_path.exists():
        logger.error("network.graphml not found – run export first.")
        return False

    G = ox.load_graphml(str(graphml_path))
    edges_df = pd.read_parquet(edges_path) if edges_path.exists() else None

    results: list[tuple[str, bool, str]] = []  # (check_name, passed, detail)

    # ── 1. Strongly connected ─────────────────────────────────────────────────
    is_scc = nx.is_strongly_connected(G)
    results.append(("Graph is strongly connected", is_scc,
                    f"Components: {nx.number_strongly_connected_components(G)}"))

    # ── 2. No zero/negative length edges ─────────────────────────────────────
    bad_len = [(u,v) for u,v,d in G.edges(data=True)
               if float(d.get("length", d.get("length_m", 1))) <= 0]
    results.append(("No zero/negative-length edges", len(bad_len) == 0,
                    f"{len(bad_len)} bad edges"))

    # ── 3. No duplicate edge_ids ──────────────────────────────────────────────
    if edges_df is not None and "edge_id" in edges_df.columns:
        dupes = edges_df["edge_id"].duplicated().sum()
        results.append(("No duplicate edge_ids", dupes == 0, f"{dupes} duplicates"))

    # ── 4. All edges have positive lanes, speed, capacity ────────────────────
    bad_attr = 0
    for u, v, d in G.edges(data=True):
        if (float(d.get("lanes", 1)) <= 0 or
            float(d.get("free_flow_speed_kmh", 1)) <= 0 or
            float(d.get("capacity_pcu_per_hr", 1)) <= 0 or
            float(d.get("free_flow_time_s", 1)) <= 0):
            bad_attr += 1
    results.append(("All edges have positive lanes/speed/capacity/ff_time",
                    bad_attr == 0, f"{bad_attr} bad edges"))

    # ── 5. Free-flow speed within posted limit + tolerance ───────────────────
    ff_violation = 0
    tolerance = 5.0  # km/h
    for u, v, d in G.edges(data=True):
        ff  = float(d.get("free_flow_speed_kmh", 0))
        sp  = float(d.get("maxspeed_kmh", 999))
        if ff > sp + tolerance:
            ff_violation += 1
    results.append(("Free-flow speed <= posted limit + tolerance",
                    ff_violation == 0, f"{ff_violation} violations"))

    # ── 6. Edge count target (2,000+ for full area) ──────────────────────────
    n_edges = G.number_of_edges()
    # For small bbox runs the threshold is relaxed
    target = 100  # minimum sane count (full run: should be 2000+)
    results.append((f"Edge count >= {target}", n_edges >= target,
                    f"Actual: {n_edges}"))

    # ── 7. Congestion ratio sanity ────────────────────────────────────────────
    speeds_path = processed_dir / "edge_speeds_by_slot.parquet"
    if speeds_path.exists():
        speeds = pd.read_parquet(speeds_path)
        out_of_range = ((speeds["congestion_ratio"] < 0.9) |
                        (speeds["congestion_ratio"] > 7.0)).sum()
        results.append(("Congestion ratios in range [0.9, 7.0]",
                        out_of_range == 0, f"{out_of_range} outliers"))

    # ── 8. BPR params exist ───────────────────────────────────────────────────
    bpr_path = processed_dir / "bpr_params.json"
    if bpr_path.exists():
        bpr = json.loads(bpr_path.read_text())
        valid_bpr = all("alpha" in v and "beta" in v for v in bpr.values())
        results.append(("BPR params have alpha+beta for all classes", valid_bpr, ""))
    else:
        results.append(("BPR params file exists", False, "bpr_params.json missing"))

    # ── 9. metadata.json exists ───────────────────────────────────────────────
    meta_path = processed_dir / "metadata.json"
    results.append(("metadata.json exists", meta_path.exists(), ""))

    # ── 10. Copy-on-modify does not mutate baseline ───────────────────────────
    try:
        from urbanflow_data.network_bundle import NetworkBundle
        import pandas as pd, geopandas as gpd
        G2 = G.copy()
        # Add a test edge
        test_u, test_v = list(G2.edges())[0][:2]
        nb = NetworkBundle(
            graph=G2, edges=gpd.GeoDataFrame(), nodes=gpd.GeoDataFrame(),
            bus_routes=pd.DataFrame(), bus_stops=pd.DataFrame(),
            bus_route_edges=pd.DataFrame(), metro_stations=None,
            edge_speeds=pd.DataFrame(), bpr_params={}, meta={}
        )
        orig_count = nb.graph.number_of_edges()
        nb2 = nb.close_node(test_u)
        copy_ok = (nb.graph.number_of_edges() == orig_count and
                   test_u not in nb2.graph)
        results.append(("Copy-on-modify does not mutate baseline", copy_ok, ""))
    except Exception as e:
        results.append(("Copy-on-modify does not mutate baseline", False, str(e)))

    # ── Print report ──────────────────────────────────────────────────────────
    all_passed = True
    logger.info("─── Validation Report ───")
    for name, passed, detail in results:
        mark = PASS if passed else FAIL
        msg  = f"{mark}  {name}"
        if detail:
            msg += f"  [{detail}]"
        if passed:
            logger.info(msg)
        else:
            logger.error(msg)
            all_passed = False

    logger.info("─── %s (%d/%d checks passed) ───",
                "ALL PASSED" if all_passed else "FAILURES FOUND",
                sum(1 for _, p, _ in results if p), len(results))
    return all_passed
