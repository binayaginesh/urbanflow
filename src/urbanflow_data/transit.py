"""
transit.py - Phase 3
Snap bus routes and metro stations onto the road graph.
Falls back to OSM public transport relations if GTFS is unavailable.
"""
from __future__ import annotations
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

def run(cfg: dict[str, Any], root: Path = Path("."), **kwargs) -> None:
    import osmnx as ox
    import pandas as pd
    import geopandas as gpd
    from shapely.geometry import Point

    interim_dir = root / cfg["paths"]["interim_dir"]
    sim_path    = interim_dir / "network_sim.graphml"
    if not sim_path.exists():
        raise FileNotFoundError(f"Simulation graph not found: {sim_path}. Run 'build-graph' first.")

    G = ox.load_graphml(str(sim_path))
    snap_dist = cfg["transit"]["max_snap_distance_m"]
    bbox_cfg  = cfg["study_area"]["bbox"]
    north, south, east, west = bbox_cfg["north"], bbox_cfg["south"], bbox_cfg["east"], bbox_cfg["west"]

    gtfs_path = cfg["transit"].get("gtfs_zip_path")

    if gtfs_path and Path(gtfs_path).exists():
        logger.info("Loading GTFS from %s", gtfs_path)
        bus_routes, bus_stops, bus_route_edges = _load_gtfs(
            Path(gtfs_path), G, snap_dist, north, south, east, west
        )
    else:
        logger.warning("GTFS zip not found (%s). Falling back to OSM public transport relations.", gtfs_path)
        _log_blocker(root, cfg)
        bus_routes, bus_stops, bus_route_edges = _load_osm_transit(
            G, north, south, east, west, snap_dist
        )

    # ── Metro stations (separate layer, not on road graph) ───────────────────
    metro_stations = _get_metro_stations(north, south, east, west)

    # ── Save ─────────────────────────────────────────────────────────────────
    bus_routes.to_parquet(interim_dir / "bus_routes.parquet", index=False)
    bus_stops.to_parquet(interim_dir / "bus_stops.parquet", index=False)
    bus_route_edges.to_parquet(interim_dir / "bus_route_edges.parquet", index=False)
    metro_stations.to_parquet(interim_dir / "metro_stations.parquet", index=False)

    logger.info("Transit layer: %d routes, %d stops, %d route-edges, %d metro stations",
                len(bus_routes), len(bus_stops), len(bus_route_edges), len(metro_stations))

    # Snap statistics
    if not bus_stops.empty and "snap_ok" in bus_stops.columns:
        ok = bus_stops["snap_ok"].sum()
        total = len(bus_stops)
        logger.info("Stop snapping: %d/%d within %dm", ok, total, snap_dist)


def _snap_stop(G, lat: float, lon: float, max_dist: float):
    """Return (node_id, dist_m) for nearest graph node; None if > max_dist."""
    import osmnx as ox
    import math
    node = ox.nearest_nodes(G, X=lon, Y=lat)
    ndata = G.nodes[node]
    # Great-circle approx
    dy = (lat - float(ndata["y"])) * 111320
    dx = (lon - float(ndata["x"])) * 111320 * math.cos(math.radians(lat))
    dist = math.sqrt(dx*dx + dy*dy)
    return node, dist


def _load_gtfs(gtfs_zip: Path, G, snap_dist, north, south, east, west):
    """Load GTFS and clip to bbox."""
    import pandas as pd
    try:
        import gtfs_kit as gk
    except ImportError:
        logger.error("gtfs-kit not installed. Run: uv pip install gtfs-kit")
        return _empty_transit()

    feed = gk.read_feed(str(gtfs_zip), dist_units="km")

    # Clip stops to bbox
    stops = feed.stops.copy()
    stops["stop_lat"] = pd.to_numeric(stops["stop_lat"], errors="coerce")
    stops["stop_lon"] = pd.to_numeric(stops["stop_lon"], errors="coerce")
    stops = stops.dropna(subset=["stop_lat","stop_lon"])
    stops = stops[
        (stops["stop_lat"] >= south) & (stops["stop_lat"] <= north) &
        (stops["stop_lon"] >= west)  & (stops["stop_lon"] <= east)
    ].copy()

    # Snap stops
    rows = []
    for _, s in stops.iterrows():
        node, dist = _snap_stop(G, s["stop_lat"], s["stop_lon"], snap_dist)
        rows.append({
            "stop_id": s["stop_id"],
            "stop_name": s.get("stop_name",""),
            "lat": s["stop_lat"], "lon": s["stop_lon"],
            "snapped_node": node, "snap_distance_m": round(dist,1),
            "snap_ok": dist <= snap_dist,
        })
    bus_stops = pd.DataFrame(rows)

    routes = feed.routes[["route_id","route_short_name","route_long_name","agency_id"]].copy()
    routes.rename(columns={"agency_id":"agency"}, inplace=True)
    routes["peak_headway_min"] = None
    routes["offpeak_headway_min"] = None
    routes["source"] = "gtfs"

    # Build route_edges via stop sequence (simplified: direct edges between snapped nodes)
    stop_map = dict(zip(bus_stops["stop_id"], bus_stops["snapped_node"]))
    st = feed.stop_times.merge(feed.trips[["trip_id","route_id"]], on="trip_id")
    re_rows = []
    for route_id, grp in st.groupby("route_id"):
        trip = grp.sort_values("stop_sequence").drop_duplicates("stop_sequence")
        nodes_seq = [stop_map.get(sid) for sid in trip["stop_id"] if sid in stop_map]
        nodes_seq = [n for n in nodes_seq if n is not None]
        seq = 0
        for i in range(len(nodes_seq)-1):
            try:
                import networkx as nx
                path = nx.shortest_path(G, nodes_seq[i], nodes_seq[i+1], weight="length")
                for j in range(len(path)-1):
                    edge_data = G[path[j]][path[j+1]]
                    k = list(edge_data.keys())[0]
                    re_rows.append({"route_id": route_id, "seq": seq, "edge_id": edge_data[k].get("edge_id", -1)})
                    seq += 1
            except Exception:
                pass
    bus_route_edges = pd.DataFrame(re_rows)
    return routes, bus_stops, bus_route_edges


def _load_osm_transit(G, north, south, east, west, snap_dist):
    """Fallback: load bus routes from OSM public transport relations."""
    import osmnx as ox
    import pandas as pd
    logger.info("Fetching OSM bus route relations via Overpass...")
    try:
        gdf = ox.features_from_bbox(
            bbox=(west, south, east, north),
            tags={"route": "bus"}
        )
        if gdf.empty:
            logger.warning("No OSM bus relations found.")
            return _empty_transit()
    except Exception as e:
        logger.warning("OSM transit fetch failed: %s", e)
        return _empty_transit()

    # Build minimal route table from OSM relations
    routes = []
    stops_list = []
    seen_routes = set()
    for idx, row in gdf.iterrows():
        ref  = row.get("ref","")
        name = row.get("name","")
        rid  = str(ref) or str(idx)
        if rid not in seen_routes:
            seen_routes.add(rid)
            routes.append({"route_id": rid, "route_short_name": str(ref), "route_long_name": str(name),
                           "agency":"BMTC","peak_headway_min": None,"offpeak_headway_min": None,"source":"osm_relation"})

    bus_routes = pd.DataFrame(routes) if routes else _empty_transit()[0]
    bus_stops  = _empty_transit()[1]
    bus_route_edges = _empty_transit()[2]
    return bus_routes, bus_stops, bus_route_edges


def _get_metro_stations(north, south, east, west):
    import osmnx as ox
    import pandas as pd
    logger.info("Fetching Namma Metro stations...")
    try:
        gdf = ox.features_from_bbox(
            bbox=(west, south, east, north),
            tags={"railway": "station"}
        )
        if gdf.empty:
            return pd.DataFrame()
        gdf = gdf[["name","geometry"]].copy()
        gdf["lat"] = gdf.geometry.centroid.y
        gdf["lon"] = gdf.geometry.centroid.x
        return pd.DataFrame({"name": gdf["name"].values, "lat": gdf["lat"].values, "lon": gdf["lon"].values})
    except Exception as e:
        logger.warning("Metro station fetch failed: %s", e)
        return pd.DataFrame()


def _empty_transit():
    import pandas as pd
    return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()


def _log_blocker(root: Path, cfg: dict) -> None:
    blockers_path = root / cfg["paths"]["blockers"]
    try:
        text = blockers_path.read_text(encoding="utf-8")
        note = (
            "\n## BLOCKER: BMTC GTFS Feed\n"
            "- **Date detected:** auto-flagged by transit.py\n"
            "- **Description:** No GTFS zip found at the configured path.\n"
            "- **What is needed:** A valid BMTC GTFS zip. Check Mobility Database, "
            "OpenCity, DataMeet, or the BMTC website.\n"
            "- **Workaround applied:** Falling back to OSM public transport relations. "
            "Coverage and headway data will be limited.\n"
        )
        if "BMTC GTFS" not in text:
            blockers_path.write_text(text + note, encoding="utf-8")
    except Exception as e:
        logger.warning("Could not update BLOCKERS.md: %s", e)
