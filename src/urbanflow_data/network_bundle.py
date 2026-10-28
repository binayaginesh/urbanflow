"""
network_bundle.py – The ``NetworkBundle`` dataclass: the contract between
Module 1 and Module 2 (Simulation Engine).

Member 2 imports this via::

    from urbanflow_data import load_network
    net = load_network()  # or load_network("data/processed")
"""
from __future__ import annotations

import json
import logging
from copy import deepcopy
from pathlib import Path
from typing import Any

import networkx as nx
import pandas as pd
import geopandas as gpd

logger = logging.getLogger(__name__)


class NetworkBundle:
    """
    Container for the complete network artefact handed to the simulator.

    Attributes
    ----------
    graph : networkx.MultiDiGraph
        Road network; edges carry all attributes from the output contract.
    edges : geopandas.GeoDataFrame
        Flat table of edges (one row per directed edge).
    nodes : geopandas.GeoDataFrame
        Flat table of nodes.
    bus_routes : pd.DataFrame
    bus_stops : pd.DataFrame
    bus_route_edges : pd.DataFrame
        Columns: route_id, seq, edge_id
    metro_stations : pd.DataFrame | None
    edge_speeds : pd.DataFrame
        Columns: edge_id, time_slot, speed_kmh, congestion_ratio, source
    bpr_params : dict
        Keys are road class strings; values are dicts with 'alpha' and 'beta'.
    meta : dict
        Build metadata (study area, dates, counts, config_hash, version).
    """

    def __init__(
        self,
        graph: nx.MultiDiGraph,
        edges: gpd.GeoDataFrame,
        nodes: gpd.GeoDataFrame,
        bus_routes: pd.DataFrame,
        bus_stops: pd.DataFrame,
        bus_route_edges: pd.DataFrame,
        metro_stations: pd.DataFrame | None,
        edge_speeds: pd.DataFrame,
        bpr_params: dict[str, Any],
        meta: dict[str, Any],
    ) -> None:
        self.graph = graph
        self.edges = edges
        self.nodes = nodes
        self.bus_routes = bus_routes
        self.bus_stops = bus_stops
        self.bus_route_edges = bus_route_edges
        self.metro_stations = metro_stations
        self.edge_speeds = edge_speeds
        self.bpr_params = bpr_params
        self.meta = meta

    # ── Scenario helpers (copy-on-modify; never mutate baseline) ──────────────

    def close_edge(self, edge_id: int) -> "NetworkBundle":
        """Return a copy of the bundle with the given edge removed from the graph."""
        nb = self._copy()
        edges_to_remove = [
            (u, v, k)
            for u, v, k, d in nb.graph.edges(data=True, keys=True)
            if d.get("edge_id") == edge_id
        ]
        if not edges_to_remove:
            logger.warning("close_edge: edge_id=%s not found in graph.", edge_id)
        nb.graph.remove_edges_from(edges_to_remove)
        return nb

    def close_node(self, node_id: int) -> "NetworkBundle":
        """Return a copy with the given node (and its incident edges) removed."""
        nb = self._copy()
        if node_id not in nb.graph:
            logger.warning("close_node: node_id=%s not found in graph.", node_id)
        else:
            nb.graph.remove_node(node_id)
        return nb

    def add_edge(self, u: int, v: int, **attrs: Any) -> "NetworkBundle":
        """Return a copy with a new edge added between nodes u and v."""
        nb = self._copy()
        nb.graph.add_edge(u, v, **attrs)
        return nb

    # ── Query helpers ──────────────────────────────────────────────────────────

    def edges_in_polygon(self, polygon) -> list[int]:  # polygon: shapely.geometry.Polygon
        """Return list of edge_ids whose geometry intersects *polygon*."""
        mask = self.edges.geometry.intersects(polygon)
        return self.edges.loc[mask, "edge_id"].tolist()

    def nearest_node(self, lat: float, lon: float) -> int:
        """Return the node_id of the nearest graph node to (lat, lon)."""
        import osmnx as ox
        return ox.nearest_nodes(self.graph, X=lon, Y=lat)

    def nearest_edge(self, lat: float, lon: float) -> int:
        """Return the edge_id of the nearest graph edge to (lat, lon)."""
        import osmnx as ox
        u, v, k = ox.nearest_edges(self.graph, X=lon, Y=lat)
        d = self.graph[u][v][k]
        return d["edge_id"]

    def get_edge(self, edge_id: int) -> dict[str, Any] | None:
        """Return attributes of edge with given edge_id, or None if not found."""
        for u, v, k, d in self.graph.edges(data=True, keys=True):
            if d.get("edge_id") == edge_id:
                return {"u": u, "v": v, "key": k, **d}
        return None

    def neighbors(self, node: int) -> list[int]:
        """Return list of successor node ids from *node*."""
        return list(self.graph.successors(node))

    def shortest_path(self, a: int, b: int, weight: str = "free_flow_time_s") -> list[int]:
        """Return shortest path (list of node ids) from a to b by *weight*."""
        return nx.shortest_path(self.graph, source=a, target=b, weight=weight)

    # ── Internal ───────────────────────────────────────────────────────────────

    def _copy(self) -> "NetworkBundle":
        """Return a deep copy (graph is deep-copied; DataFrames are copied)."""
        return NetworkBundle(
            graph=self.graph.copy(),
            edges=self.edges.copy(),
            nodes=self.nodes.copy(),
            bus_routes=self.bus_routes.copy(),
            bus_stops=self.bus_stops.copy(),
            bus_route_edges=self.bus_route_edges.copy(),
            metro_stations=self.metro_stations.copy() if self.metro_stations is not None else None,
            edge_speeds=self.edge_speeds.copy(),
            bpr_params=deepcopy(self.bpr_params),
            meta=deepcopy(self.meta),
        )

    def __repr__(self) -> str:
        n = self.graph.number_of_nodes()
        e = self.graph.number_of_edges()
        return (
            f"NetworkBundle("
            f"nodes={n}, edges={e}, "
            f"routes={len(self.bus_routes)}, "
            f"version={self.meta.get('version', 'unknown')})"
        )


# ── Loader ────────────────────────────────────────────────────────────────────

def load_network(processed_dir: str | Path | None = None) -> NetworkBundle:
    """
    Load the processed bundle from *processed_dir* or URBANFLOW_DATA_DIR and return a NetworkBundle.

    Example
    -------
    >>> from urbanflow_data import load_network
    >>> net = load_network()          # reads from URBANFLOW_DATA_DIR or data/processed
    >>> net.graph                     # networkx.MultiDiGraph
    >>> net.close_edge(42)            # returns modified copy
    """
    from urbanflow_data.config import get_data_dir

    p = get_data_dir(processed_dir)

    graph = nx.read_graphml(p / "network.graphml")
    # Restore integer node ids
    mapping = {n: int(n) for n in graph.nodes() if str(n).isdigit()}
    graph = nx.relabel_nodes(graph, mapping)

    try:
        edges = gpd.read_parquet(p / "edges.parquet")
    except Exception:
        edges = pd.read_parquet(p / "edges.parquet")

    try:
        nodes = gpd.read_parquet(p / "nodes.parquet")
    except Exception:
        nodes = pd.read_parquet(p / "nodes.parquet")

    bus_routes      = pd.read_parquet(p / "bus_routes.parquet")      if (p / "bus_routes.parquet").exists()      else pd.DataFrame()
    bus_stops       = pd.read_parquet(p / "bus_stops.parquet")       if (p / "bus_stops.parquet").exists()       else pd.DataFrame()
    bus_route_edges = pd.read_parquet(p / "bus_route_edges.parquet") if (p / "bus_route_edges.parquet").exists() else pd.DataFrame()
    metro_stations  = pd.read_parquet(p / "metro_stations.parquet")  if (p / "metro_stations.parquet").exists()  else None
    edge_speeds     = pd.read_parquet(p / "edge_speeds_by_slot.parquet") if (p / "edge_speeds_by_slot.parquet").exists() else pd.DataFrame()

    with open(p / "bpr_params.json", encoding="utf-8") as fh:
        bpr_params = json.load(fh)
    with open(p / "metadata.json", encoding="utf-8") as fh:
        meta = json.load(fh)

    return NetworkBundle(
        graph=graph,
        edges=edges,
        nodes=nodes,
        bus_routes=bus_routes,
        bus_stops=bus_stops,
        bus_route_edges=bus_route_edges,
        metro_stations=metro_stations,
        edge_speeds=edge_speeds,
        bpr_params=bpr_params,
        meta=meta,
    )
