"""tests/test_network_bundle.py – Unit tests for NetworkBundle copy-on-modify."""
from __future__ import annotations
import pytest
import networkx as nx
import pandas as pd
import geopandas as gpd


def _make_bundle():
    from urbanflow_data.network_bundle import NetworkBundle
    G = nx.MultiDiGraph()
    G.add_node(1, x=77.61, y=12.93)
    G.add_node(2, x=77.62, y=12.94)
    G.add_edge(1, 2, edge_id=100, length_m=500.0, free_flow_time_s=60.0)
    G.add_edge(2, 1, edge_id=101, length_m=500.0, free_flow_time_s=62.0)
    empty_gdf = gpd.GeoDataFrame()
    empty_df  = pd.DataFrame()
    return NetworkBundle(
        graph=G,
        edges=empty_gdf.copy(),
        nodes=empty_gdf.copy(),
        bus_routes=empty_df.copy(),
        bus_stops=empty_df.copy(),
        bus_route_edges=empty_df.copy(),
        metro_stations=None,
        edge_speeds=empty_df.copy(),
        bpr_params={"primary": {"alpha": 0.15, "beta": 4.0}},
        meta={"version": "test"},
    )


def test_close_edge_returns_copy():
    nb = _make_bundle()
    original_count = nb.graph.number_of_edges()
    nb2 = nb.close_edge(100)
    # copy has one fewer edge
    assert nb2.graph.number_of_edges() == original_count - 1
    # original is unchanged
    assert nb.graph.number_of_edges() == original_count


def test_close_node_returns_copy():
    nb = _make_bundle()
    nb2 = nb.close_node(1)
    assert 1 not in nb2.graph
    assert 1 in nb.graph


def test_add_edge_returns_copy():
    nb = _make_bundle()
    nb2 = nb.add_edge(1, 2, edge_id=999, length_m=100.0)
    assert nb2.graph.number_of_edges() > nb.graph.number_of_edges()
    assert nb.graph.number_of_edges() == 2  # original unchanged


def test_neighbors():
    nb = _make_bundle()
    assert 2 in nb.neighbors(1)


def test_shortest_path():
    nb = _make_bundle()
    path = nb.shortest_path(1, 2)
    assert path == [1, 2]
