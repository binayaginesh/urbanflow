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

    # Ensure edge_id column exists
    if "edge_id" not in edges_gdf.columns:
        edges_gdf["edge_id"] = range(len(edges_gdf))

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
