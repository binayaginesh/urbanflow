"""
export.py - Phase 5a
Export the final processed bundle to data/processed/.
"""
from __future__ import annotations
import hashlib, json, logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def run(cfg: dict[str, Any], root: Path = Path("."), **kwargs) -> None:
    import osmnx as ox
    import geopandas as gpd
    import pandas as pd
    import networkx as nx

    interim_dir   = root / cfg["paths"]["interim_dir"]
    processed_dir = root / cfg["paths"]["processed_dir"]
    processed_dir.mkdir(parents=True, exist_ok=True)

    sim_path = interim_dir / "network_sim.graphml"
    if not sim_path.exists():
        raise FileNotFoundError(f"Simulation graph missing: {sim_path}")

    G = ox.load_graphml(str(sim_path))
    logger.info("Exporting: %d nodes, %d edges", G.number_of_nodes(), G.number_of_edges())

    # ── GraphML ──────────────────────────────────────────────────────────────
    ox.save_graphml(G, str(processed_dir / "network.graphml"))
    logger.info("Saved network.graphml")

    # ── Parquet edge + node tables ────────────────────────────────────────────
    nodes_gdf, edges_gdf = ox.graph_to_gdfs(G)
    edges_gdf = edges_gdf.reset_index()
    nodes_gdf = nodes_gdf.reset_index()

    # Ensure node_id, x, y, name, is_signalised exist on nodes_gdf
    if "node_id" not in nodes_gdf.columns and "osmid" in nodes_gdf.columns:
        nodes_gdf["node_id"] = nodes_gdf["osmid"].astype(int)
    else:
        nodes_gdf["node_id"] = pd.to_numeric(nodes_gdf["node_id"], errors="coerce").fillna(0).astype(int)
    nodes_gdf["x"] = pd.to_numeric(nodes_gdf["x"], errors="coerce")
    nodes_gdf["y"] = pd.to_numeric(nodes_gdf["y"], errors="coerce")
    if "name" not in nodes_gdf.columns:
        nodes_gdf["name"] = nodes_gdf["node_id"].apply(lambda nid: f"Junction {nid}")
    else:
        nodes_gdf["name"] = nodes_gdf["name"].fillna("").astype(str)
        empty_mask = nodes_gdf["name"].isin(["", "nan", "None"])
        nodes_gdf.loc[empty_mask, "name"] = nodes_gdf.loc[empty_mask, "node_id"].apply(lambda nid: f"Junction {nid}")
    if "is_signalised" in nodes_gdf.columns:
        nodes_gdf["is_signalised"] = nodes_gdf["is_signalised"].astype(str).str.lower().isin(["true", "1", "yes"])
    else:
        nodes_gdf["is_signalised"] = False

    # Ensure edge_id and numeric attributes exist on edges_gdf
    if "edge_id" not in edges_gdf.columns:
        edges_gdf["edge_id"] = range(len(edges_gdf))
    else:
        edges_gdf["edge_id"] = pd.to_numeric(edges_gdf["edge_id"], errors="coerce").fillna(0).astype(int)
    edges_gdf["u"] = pd.to_numeric(edges_gdf["u"], errors="coerce").fillna(0).astype(int)
    edges_gdf["v"] = pd.to_numeric(edges_gdf["v"], errors="coerce").fillna(0).astype(int)
    for num_col, default_val in [
        ("lanes", 1),
        ("length_m", 100.0),
        ("free_flow_speed_kmh", 30.0),
        ("free_flow_time_s", 12.0),
        ("capacity_pcu_per_hr", 1000.0),
    ]:
        if num_col in edges_gdf.columns:
            edges_gdf[num_col] = pd.to_numeric(edges_gdf[num_col], errors="coerce").fillna(default_val)
        else:
            edges_gdf[num_col] = default_val
    edges_gdf["lanes"] = edges_gdf["lanes"].astype(int)
    if "is_bridge" in edges_gdf.columns:
        edges_gdf["is_bridge"] = edges_gdf["is_bridge"].astype(str).str.lower().isin(["true", "1", "yes"])
    else:
        edges_gdf["is_bridge"] = False

    # Populate lat_u, lon_u, lat_v, lon_v from node coordinates for dashboard maps
    node_xy = nodes_gdf.set_index("node_id")[["x", "y"]]
    edges_gdf["lon_u"] = edges_gdf["u"].map(node_xy["x"])
    edges_gdf["lat_u"] = edges_gdf["u"].map(node_xy["y"])
    edges_gdf["lon_v"] = edges_gdf["v"].map(node_xy["x"])
    edges_gdf["lat_v"] = edges_gdf["v"].map(node_xy["y"])

    # Coerce geometry-incompatible types for parquet
    for col in edges_gdf.columns:
        if col == "geometry": continue
        if edges_gdf[col].dtype == object:
            edges_gdf[col] = edges_gdf[col].astype(str)
    for col in nodes_gdf.columns:
        if col == "geometry": continue
        if nodes_gdf[col].dtype == object:
            nodes_gdf[col] = nodes_gdf[col].astype(str)

    edges_gdf.to_parquet(processed_dir / "edges.parquet")
    nodes_gdf.to_parquet(processed_dir / "nodes.parquet")
    logger.info("Saved edges.parquet (%d rows), nodes.parquet (%d rows)",
                len(edges_gdf), len(nodes_gdf))

    # ── GeoPackage (GIS layer for dashboard) ─────────────────────────────────
    try:
        edges_gdf.to_file(str(processed_dir / "network.gpkg"), layer="edges", driver="GPKG")
        nodes_gdf.to_file(str(processed_dir / "network.gpkg"), layer="nodes", driver="GPKG")
        logger.info("Saved network.gpkg")
    except Exception as e:
        logger.warning("Could not write GeoPackage: %s", e)

    # ── Transit files ─────────────────────────────────────────────────────────
    for fname in ["bus_routes","bus_stops","bus_route_edges","metro_stations"]:
        src = interim_dir / f"{fname}.parquet"
        if src.exists():
            import shutil
            shutil.copy2(src, processed_dir / f"{fname}.parquet")
            logger.info("Copied %s.parquet", fname)

    # ── Edge speeds + BPR ────────────────────────────────────────────────────
    speeds_src = interim_dir / "edge_speeds_by_slot.parquet"
    if speeds_src.exists():
        import shutil
        shutil.copy2(speeds_src, processed_dir / "edge_speeds_by_slot.parquet")
        logger.info("Copied edge_speeds_by_slot.parquet")

    bpr_src = processed_dir / "bpr_params.json"  # already written by calibrate
    if not bpr_src.exists():
        default_bpr = {rc: {"alpha": cfg["bpr_defaults"]["alpha"], "beta": cfg["bpr_defaults"]["beta"]}
                       for rc in cfg["default_lanes"]}
        bpr_src.write_text(json.dumps(default_bpr, indent=2))

    # ── POIs GeoPackage ──────────────────────────────────────────────────────
    pois_src = root / cfg["paths"]["raw_dir"] / "osm_features.gpkg"
    if pois_src.exists():
        import shutil
        shutil.copy2(pois_src, processed_dir / "pois.gpkg")

    # ── metadata.json ────────────────────────────────────────────────────────
    config_yaml_path = root / "config" / "config.yaml"
    config_hash = ""
    if config_yaml_path.exists():
        config_hash = hashlib.sha256(config_yaml_path.read_bytes()).hexdigest()[:16]

    bb = cfg["study_area"]["bbox"]
    total_km = round(edges_gdf["length"].astype(float).sum() / 1000, 2) if "length" in edges_gdf.columns else None

    meta = {
        "version": "0.1.0",
        "build_date": datetime.now(timezone.utc).isoformat(),
        "osm_extract_date": _read_osm_date(root, cfg),
        "study_area": {"north": bb["north"], "south": bb["south"],
                        "east": bb["east"],  "west":  bb["west"]},
        "node_count": G.number_of_nodes(),
        "edge_count": G.number_of_edges(),
        "total_length_km": total_km,
        "config_hash": config_hash,
    }
    (processed_dir / "metadata.json").write_text(json.dumps(meta, indent=2))
    logger.info("Saved metadata.json  version=%s  edges=%d  %.1f km",
                meta["version"], meta["edge_count"], total_km or 0)


def _read_osm_date(root: Path, cfg: dict) -> str:
    prov = root / cfg["paths"]["provenance"]
    try:
        for line in prov.read_text(encoding="utf-8").splitlines():
            if "download date" in line.lower() and "pipeline" not in line.lower():
                parts = line.split("|")
                for p in parts:
                    p = p.strip()
                    if len(p) == 10 and p[4] == "-":
                        return p
    except Exception:
        pass
    return "unknown"
