"""
osm_download.py – Phase 1 Step 1
Download the OSM drive graph and extra features for the study area.

Run via CLI:
    python -m urbanflow_data.cli download [--small]
"""
from __future__ import annotations

import datetime
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def run(cfg: dict[str, Any], root: Path = Path("."), *, small: bool = False) -> None:
    import osmnx as ox
    from .config import get_bbox, get_small_bbox

    raw_dir = root / cfg["paths"]["raw_dir"]
    raw_dir.mkdir(parents=True, exist_ok=True)

    # ── Choose bbox ─────────────────────────────────────────────────────────
    if small:
        north, south, east, west = get_small_bbox(cfg)
        logger.info("Using SMALL bbox for debug run")
    elif cfg["study_area"].get("place_name"):
        place = cfg["study_area"]["place_name"]
        logger.info("Downloading by place_name: %s", place)
        G_raw = ox.graph_from_place(
            place,
            network_type=cfg["osm"]["network_type"],
            simplify=False,
            retain_all=cfg["osm"].get("retain_all", False),
        )
        _save_and_log(G_raw, raw_dir, cfg, root)
        return
    else:
        north, south, east, west = get_bbox(cfg)

    logger.info("Downloading OSM drive graph: N=%.4f S=%.4f E=%.4f W=%.4f", north, south, east, west)
    G_raw = ox.graph_from_bbox(
        bbox=(north, south, east, west),
        network_type=cfg["osm"]["network_type"],
        simplify=False,
        retain_all=cfg["osm"].get("retain_all", False),
    )
    _save_and_log(G_raw, raw_dir, cfg, root)

    # ── Download extra OSM features ─────────────────────────────────────────
    logger.info("Downloading extra OSM features (signals, bus stops, metro, POIs)...")
    tags_map = {
        "traffic_signals": {"highway": "traffic_signals"},
        "bus_stops":        {"highway": "bus_stop"},
        "transit_platform": {"public_transport": "platform"},
        "metro_stations":   {"railway": "station", "station": "subway"},
        "bridges":          {"bridge": True},
        "stadiums":         {"leisure": "stadium"},
        "malls":            {"shop": "mall"},
        "hospitals":        {"amenity": "hospital"},
        "tech_parks":       {"landuse": "commercial"},
    }

    try:
        import geopandas as gpd
        from shapely.geometry import box as shapely_box
        study_polygon = shapely_box(west, south, east, north)

        gdfs = {}
        for label, tags in tags_map.items():
            try:
                gdf = ox.features_from_bbox(
                    bbox=(north, south, east, west), tags=tags
                )
                if not gdf.empty:
                    gdfs[label] = gdf
                    logger.info("  %-20s: %d features", label, len(gdf))
            except Exception as e:
                logger.warning("  %-20s: skipped (%s)", label, e)

        if gdfs:
            import fiona
            gpkg_path = raw_dir / "osm_features.gpkg"
            for layer, gdf in gdfs.items():
                # Keep only geometry + key string columns
                keep_cols = [c for c in gdf.columns if gdf[c].dtype == object or c == "geometry"]
                gdf[keep_cols].to_file(str(gpkg_path), layer=layer, driver="GPKG")
            logger.info("Saved extra features to %s", gpkg_path)
    except Exception as e:
        logger.warning("Extra features download failed: %s", e)

    _update_provenance(root, cfg)


def _save_and_log(G_raw, raw_dir: Path, cfg: dict, root: Path) -> None:
    import osmnx as ox
    out_path = raw_dir / "osm_drive_raw.graphml"
    ox.save_graphml(G_raw, str(out_path))
    n = G_raw.number_of_nodes()
    e = G_raw.number_of_edges()
    logger.info("Raw graph saved: %d nodes, %d edges -> %s", n, e, out_path)


def _update_provenance(root: Path, cfg: dict) -> None:
    prov_path = root / cfg["paths"]["provenance"]
    today = datetime.date.today().isoformat()
    try:
        text = prov_path.read_text(encoding="utf-8")
        text = text.replace("*to be filled in by pipeline*", today, 1)
        text = text.replace("*to be filled in*", today)
        prov_path.write_text(text, encoding="utf-8")
        logger.info("Updated PROVENANCE.md with download date %s", today)
    except Exception as e:
        logger.warning("Could not update PROVENANCE.md: %s", e)
