"""
clean_network.py - Phase 1 Step 2
Clean and simplify the raw OSM drive graph.
"""
from __future__ import annotations
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Road class hierarchy (higher index = higher order)
_HIGHWAY_ORDER = [
    "motorway","motorway_link","trunk","trunk_link",
    "primary","primary_link","secondary","secondary_link",
    "tertiary","tertiary_link","residential","living_street",
    "unclassified","service","road",
]

def _parse_lanes(val, default: int) -> tuple[int, bool]:
    """Return (lanes_int, imputed). Handles str/list/None."""
    if val is None:
        return default, True
    if isinstance(val, list):
        nums = []
        for v in val:
            try: nums.append(int(str(v).strip()))
            except: pass
        return (max(nums) if nums else default), (not bool(nums))
    try:
        return int(str(val).strip()), False
    except:
        return default, True

def _parse_speed(val, default: float) -> tuple[float, bool]:
    """Return (speed_kmh_float, imputed). Strips 'km/h', handles lists/None."""
    if val is None:
        return default, True
    if isinstance(val, list):
        speeds = []
        for v in val:
            try:
                speeds.append(float(str(v).replace("km/h","").replace("mph","").strip()))
            except: pass
        return (max(speeds) if speeds else default), (not bool(speeds))
    try:
        return float(str(val).replace("km/h","").replace("mph","").strip()), False
    except:
        return default, True

def _best_highway(val) -> str:
    """If val is a list, return the highest-order highway class."""
    if isinstance(val, list):
        best = "unclassified"
        best_idx = -1
        for v in val:
            try:
                idx = _HIGHWAY_ORDER.index(v)
                if idx < best_idx or best_idx == -1:
                    best_idx = idx
                    best = v
            except ValueError:
                pass
        return best
    return str(val) if val else "unclassified"

def run(cfg: dict[str, Any], root: Path = Path("."), **kwargs) -> None:
    import osmnx as ox
    import networkx as nx

    raw_dir     = root / cfg["paths"]["raw_dir"]
    interim_dir = root / cfg["paths"]["interim_dir"]
    interim_dir.mkdir(parents=True, exist_ok=True)

    raw_path = raw_dir / "osm_drive_raw.graphml"
    if not raw_path.exists():
        raise FileNotFoundError(f"Raw graph not found: {raw_path}. Run 'download' first.")

    logger.info("Loading raw graph from %s", raw_path)
    G = ox.load_graphml(str(raw_path))
    logger.info("Raw graph: %d nodes, %d edges", G.number_of_nodes(), G.number_of_edges())

    # ── 1. Largest strongly connected component ──────────────────────────────
    scc = max(nx.strongly_connected_components(G), key=len)
    dropped_nodes = G.number_of_nodes() - len(scc)
    dropped_edges = G.number_of_edges() - G.subgraph(scc).number_of_edges()
    G = G.subgraph(scc).copy()
    logger.info("SCC: kept %d nodes, %d edges; dropped %d nodes, %d edges",
                G.number_of_nodes(), G.number_of_edges(), dropped_nodes, dropped_edges)

    # ── 2. Simplify topology ─────────────────────────────────────────────────
    logger.info("Simplifying graph topology...")
    G = ox.simplify_graph(G)

    # ── 3. Consolidate intersections ─────────────────────────────────────────
    tol = cfg["network_cleaning"]["consolidate_tolerance_m"]
    dead_ends = cfg["network_cleaning"].get("dead_ends", False)
    logger.info("Consolidating intersections (tolerance=%dm)...", tol)
    G_proj = ox.project_graph(G, to_crs=cfg["crs"]["metric"])
    G_proj = ox.consolidate_intersections(
        G_proj, tolerance=tol, rebuild_graph=True, dead_ends=dead_ends
    )
    G = ox.project_graph(G_proj, to_crs=cfg["crs"]["storage"])
    logger.info("After consolidation: %d nodes, %d edges", G.number_of_nodes(), G.number_of_edges())

    # ── 4. Parse and impute edge attributes ──────────────────────────────────
    default_lanes = cfg["default_lanes"]
    default_speed = cfg["default_speed_kmh"]

    lanes_imputed_count = 0
    speed_imputed_count = 0
    total_edges = G.number_of_edges()

    for u, v, k, data in G.edges(data=True, keys=True):
        hw = _best_highway(data.get("highway", "unclassified"))
        data["highway"] = hw

        dl = default_lanes.get(hw, default_lanes.get("unclassified", 1))
        lanes, imp = _parse_lanes(data.get("lanes"), dl)
        data["lanes"] = lanes
        data["lanes_imputed"] = imp
        if imp: lanes_imputed_count += 1

        ds = float(default_speed.get(hw, default_speed.get("unclassified", 30)))
        speed, simp = _parse_speed(data.get("maxspeed"), ds)
        data["maxspeed_kmh"] = speed
        data["speed_imputed"] = simp
        if simp: speed_imputed_count += 1

        # Normalize other fields
        data["oneway"]  = bool(data.get("oneway", False))
        data["bridge"]  = data.get("bridge", "no") not in (None, "no", False, "")
        data["tunnel"]  = data.get("tunnel", "no") not in (None, "no", False, "")
        data["name"]    = str(data.get("name", "")) if data.get("name") else ""

    pct_lanes = 100 * lanes_imputed_count / total_edges if total_edges else 0
    pct_speed = 100 * speed_imputed_count / total_edges if total_edges else 0
    logger.info("Imputation: lanes=%.1f%% (%d/%d)  speed=%.1f%% (%d/%d)",
                pct_lanes, lanes_imputed_count, total_edges,
                pct_speed, speed_imputed_count, total_edges)

    # Warn if imputation is very high
    if pct_lanes > 60:
        logger.warning("Lane imputation exceeds 60%% (%.1f%%). Flagged in LIMITATIONS.md", pct_lanes)
        _flag_limitation(root, cfg, pct_lanes)

    # ── 5. Print summary ─────────────────────────────────────────────────────
    nodes_gdf, edges_gdf = ox.graph_to_gdfs(G)
    total_km = edges_gdf["length"].sum() / 1000
    hw_dist  = edges_gdf["highway"].value_counts().to_dict()
    logger.info("Clean graph summary:")
    logger.info("  Nodes: %d", G.number_of_nodes())
    logger.info("  Edges: %d", G.number_of_edges())
    logger.info("  Total length: %.1f km", total_km)
    logger.info("  Highway distribution: %s", hw_dist)

    # ── 6. Save ──────────────────────────────────────────────────────────────
    out_path = interim_dir / "osm_drive_clean.graphml"
    ox.save_graphml(G, str(out_path))
    logger.info("Clean graph saved to %s", out_path)

def _flag_limitation(root: Path, cfg: dict, pct: float) -> None:
    lim_path = root / cfg["paths"]["limitations"]
    try:
        text = lim_path.read_text(encoding="utf-8")
        note = f"\n> **Auto-flagged:** Lane imputation is {pct:.1f}% (>60%). Capacity estimates for many edges rely entirely on config defaults.\n"
        if note.strip() not in text:
            lim_path.write_text(text + note, encoding="utf-8")
    except Exception as e:
        logger.warning("Could not update LIMITATIONS.md: %s", e)
