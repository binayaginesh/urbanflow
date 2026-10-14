"""
build_graph.py - Phase 2
Add simulation-ready attributes to the cleaned graph.
Every edge gets: edge_id, free_flow_speed, free_flow_time, capacity,
bridge/signal flags. Scenario helpers are on NetworkBundle.
"""
from __future__ import annotations
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_HIGHWAY_ORDER = [
    "motorway","motorway_link","trunk","trunk_link",
    "primary","primary_link","secondary","secondary_link",
    "tertiary","tertiary_link","residential","living_street",
    "unclassified","service","road",
]

def run(cfg: dict[str, Any], root: Path = Path("."), **kwargs) -> None:
    import osmnx as ox
    import networkx as nx

    interim_dir  = root / cfg["paths"]["interim_dir"]
    clean_path   = interim_dir / "osm_drive_clean.graphml"
    if not clean_path.exists():
        raise FileNotFoundError(f"Clean graph not found: {clean_path}. Run 'clean' first.")

    logger.info("Loading clean graph from %s", clean_path)
    G = ox.load_graphml(str(clean_path))

    ff_caps  = cfg["free_flow_speed_cap_kmh"]
    ff_red   = float(cfg["free_flow_reduction_factor"])
    cap_lane = cfg["capacity_per_lane_pcu_hr"]
    cap_red  = float(cfg["capacity_reduction_factor"])

    # Build signal node set
    signal_nodes: set = set()
    for nid, ndata in G.nodes(data=True):
        if ndata.get("highway") == "traffic_signals":
            signal_nodes.add(nid)

    logger.info("Annotating edges with simulation attributes...")
    edge_id_counter = 0
    for u, v, k, data in G.edges(data=True, keys=True):
        hw = str(data.get("highway", "unclassified"))

        # Stable edge_id
        data["edge_id"] = edge_id_counter
        edge_id_counter += 1

        # Free-flow speed
        maxspeed  = float(data.get("maxspeed_kmh", cfg["default_speed_kmh"].get(hw, 30)))
        cap_speed = float(ff_caps.get(hw, ff_caps.get("unclassified", 28)))
        ff_speed  = min(maxspeed, cap_speed) * ff_red
        data["free_flow_speed_kmh"] = round(ff_speed, 2)

        # Free-flow travel time
        length_m = float(data.get("length", 1.0))
        data["length_m"] = length_m
        ff_time = length_m / (ff_speed / 3.6) if ff_speed > 0 else 9999.0
        data["free_flow_time_s"] = round(ff_time, 4)

        # Capacity
        lanes = int(data.get("lanes", cfg["default_lanes"].get(hw, 1)))
        cap_per_lane = float(cap_lane.get(hw, cap_lane.get("unclassified", 900)))
        data["capacity_pcu_per_hr"] = round(lanes * cap_per_lane * cap_red, 1)

        # Flags
        data["is_bridge"]  = bool(data.get("bridge", False))
        data["is_flyover"] = data["is_bridge"] and int(data.get("layer", 0) or 0) > 0
        data["has_signal_at_v"] = v in signal_nodes

    # Annotate nodes
    for nid, ndata in G.nodes(data=True):
        ndata["node_id"] = nid
        ndata["is_signalised"] = nid in signal_nodes
        ndata["degree"] = G.degree(nid)
        ndata["is_junction"] = G.degree(nid) >= 3

    n_edges = G.number_of_edges()
    n_nodes = G.number_of_nodes()
    logger.info("Graph annotated: %d nodes, %d edges, edge_ids 0..%d", n_nodes, n_edges, edge_id_counter-1)

    # Save
    out_path = interim_dir / "network_sim.graphml"
    ox.save_graphml(G, str(out_path))
    logger.info("Simulation graph saved to %s", out_path)

    # Quick validation
    zero_len = sum(1 for _, _, d in G.edges(data=True) if float(d.get("length_m", 1)) <= 0)
    if zero_len:
        logger.warning("Found %d edges with non-positive length!", zero_len)
    neg_cap = sum(1 for _, _, d in G.edges(data=True) if float(d.get("capacity_pcu_per_hr", 1)) <= 0)
    if neg_cap:
        logger.warning("Found %d edges with non-positive capacity!", neg_cap)
