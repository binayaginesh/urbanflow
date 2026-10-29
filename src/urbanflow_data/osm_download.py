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

    # Avoid hanging on Overpass rate-limit pauses and use fast mirror fallback
    ox.settings.overpass_rate_limit = False
    ox.settings.requests_timeout = 90
    ox.settings.use_cache = True
    overpass_endpoints = [
        "https://overpass.kumi.systems/api/interpreter",
        "https://overpass-api.de/api/interpreter",
        "https://overpass.private.coffee/api/interpreter",
    ]

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
    G_raw = None
    last_err = None
    for ep in overpass_endpoints:
        try:
            ox.settings.overpass_url = ep
            G_raw = ox.graph_from_bbox(
                bbox=(west, south, east, north),
                network_type=cfg["osm"]["network_type"],
                simplify=False,
                retain_all=cfg["osm"].get("retain_all", False),
            )
            break
        except Exception as e:
            logger.warning("Overpass endpoint %s failed (%s), trying next...", ep, e)
            last_err = e
    if G_raw is None:
        raw_existing = raw_dir / "osm_drive_raw.graphml"
        if raw_existing.exists():
            logger.warning("All Overpass mirrors timed out; using cached raw graph at %s", raw_existing)
            _update_provenance(root, cfg)
            return
        raise RuntimeError(f"All Overpass endpoints failed: {last_err}")
    _save_and_log(G_raw, raw_dir, cfg, root)

    # ── Download extra OSM features (single combined Overpass query) ────────
    logger.info("Downloading extra OSM features (signals, bus stops, metro, POIs)...")
    combined_tags = {
        "highway": ["traffic_signals", "bus_stop"],
        "public_transport": ["platform"],
        "railway": ["station"],
        "leisure": ["stadium"],
        "shop": ["mall"],
        "amenity": ["hospital"],
    }

    try:
        import geopandas as gpd
        gdf_all = ox.features_from_bbox(
            bbox=(west, south, east, north), tags=combined_tags
        )
        if not gdf_all.empty:
            gpkg_path = raw_dir / "osm_features.gpkg"
            keep_cols = [c for c in gdf_all.columns if gdf_all[c].dtype == object or c == "geometry"]
            gdf_clean = gdf_all[keep_cols].reset_index(drop=True)
            for col in gdf_clean.columns:
                if col != "geometry":
                    gdf_clean[col] = gdf_clean[col].astype(str)
            gdf_clean.to_file(str(gpkg_path), layer="pois", driver="GPKG")
            logger.info("Saved %d extra features to %s", len(gdf_clean), gpkg_path)
    except Exception as e:
        logger.warning("Extra features download skipped (%s)", e)

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
