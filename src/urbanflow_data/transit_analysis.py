"""
transit_analysis.py - Stage B6: bus route performance and metro interchange analysis.

All numbers are derived from the loaded NetworkBundle (edges, bus routes, metro
stations) and a SimResult. Nothing is invented: where the dataset lacks a value
(for example metro headways), the field is reported as missing (None).
"""
from __future__ import annotations

import math
from typing import Any

import pandas as pd

from urbanflow_data.network_bundle import NetworkBundle
from urbanflow_data.simulation_engine import SimResult

# Slots in which BMTC peak headways apply. Any other slot uses off-peak headway.
PEAK_SLOTS: frozenset[str] = frozenset({"morning_peak", "evening_peak"})

_EARTH_RADIUS_M = 6_371_000.0


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in metres between two WGS84 points."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * _EARTH_RADIUS_M * math.asin(math.sqrt(a))


def headway_for_slot(route_row: pd.Series | dict[str, Any], time_slot: str) -> float | None:
    """Return scheduled headway (minutes) for the slot, or None if not recorded."""
    key = "peak_headway_min" if time_slot in PEAK_SLOTS else "offpeak_headway_min"
    val = route_row.get(key) if hasattr(route_row, "get") else None
    if val is None or pd.isna(val) or float(val) <= 0:
        return None
    return float(val)


def compute_route_metrics(
    net: NetworkBundle,
    sim: SimResult,
    time_slot: str,
    scenario_graph=None,
) -> pd.DataFrame:
    """
    Per-route running time and delay for one simulation result.

    Parameters
    ----------
    net:
        Baseline bundle (provides route definitions and edge geometry/lengths).
    sim:
        Simulation result for the scenario being inspected.
    time_slot:
        Slot name (selects peak vs off-peak headway).
    scenario_graph:
        Graph the simulation ran on. Route edges absent from this graph are
        counted as ``edges_disrupted`` (the bus must divert; delay on those
        links is not modelled and is excluded from the running-time sums).

    Returns
    -------
    DataFrame with one row per route.
    """
    cols = [
        "route_id", "route_name", "n_edges", "edges_disrupted", "length_km",
        "ff_running_time_min", "sim_running_time_min", "delay_min", "delay_pct",
        "headway_min", "buses_per_hr", "bus_minutes_lost_per_hr", "source",
    ]
    if net.bus_routes is None or net.bus_routes.empty or net.bus_route_edges.empty:
        return pd.DataFrame(columns=cols)

    edges_idx = net.edges.set_index("edge_id")
    live_eids: set[int] | None = None
    if scenario_graph is not None:
        live_eids = {
            int(d["edge_id"]) for _, _, d in scenario_graph.edges(data=True)
            if d.get("edge_id") is not None
        }

    rows: list[dict[str, Any]] = []
    for _, route in net.bus_routes.iterrows():
        rid = route["route_id"]
        seq = (
            net.bus_route_edges[net.bus_route_edges["route_id"] == rid]
            .sort_values("seq")["edge_id"].astype(int).tolist()
        )
        length_m = ff_s = sim_s = 0.0
        disrupted = 0
        for eid in seq:
            if eid not in edges_idx.index:
                disrupted += 1
                continue
            if live_eids is not None and eid not in live_eids:
                disrupted += 1
                continue
            e = edges_idx.loc[eid]
            lm = float(e["length_m"])
            ff_spd = float(e["free_flow_speed_kmh"])
            spd = float(sim.edge_speeds.get(eid, ff_spd))
            length_m += lm
            ff_s += float(e.get("free_flow_time_s", lm / (ff_spd / 3.6)))
            sim_s += lm / (spd / 3.6) if spd > 0 else float("inf")

        delay_s = max(sim_s - ff_s, 0.0)
        headway = headway_for_slot(route, time_slot)
        buses_hr = 60.0 / headway if headway else None
        rows.append({
            "route_id": rid,
            "route_name": route.get("route_long_name", rid),
            "n_edges": len(seq),
            "edges_disrupted": disrupted,
            "length_km": round(length_m / 1000.0, 2),
            "ff_running_time_min": round(ff_s / 60.0, 2),
            "sim_running_time_min": round(sim_s / 60.0, 2),
            "delay_min": round(delay_s / 60.0, 2),
            "delay_pct": round(100.0 * delay_s / ff_s, 1) if ff_s > 0 else None,
            "headway_min": headway,
            "buses_per_hr": round(buses_hr, 2) if buses_hr else None,
            "bus_minutes_lost_per_hr": round(delay_s / 60.0 * buses_hr, 1) if buses_hr else None,
            "source": route.get("source", "unknown"),
        })
    return pd.DataFrame(rows, columns=cols)


def compare_route_metrics(base_df: pd.DataFrame, scen_df: pd.DataFrame) -> pd.DataFrame:
    """Join baseline and scenario route metrics and compute per-route deltas."""
    if base_df.empty or scen_df.empty:
        return pd.DataFrame()
    m = base_df[["route_id", "route_name", "sim_running_time_min", "delay_min"]].merge(
        scen_df[["route_id", "sim_running_time_min", "delay_min", "edges_disrupted"]],
        on="route_id", suffixes=("_base", "_scen"),
    )
    m["delta_running_time_min"] = (m["sim_running_time_min_scen"] - m["sim_running_time_min_base"]).round(2)
    m["delta_delay_min"] = (m["delay_min_scen"] - m["delay_min_base"]).round(2)
    return m


def metro_interchanges(
    net: NetworkBundle,
    walk_radius_m: float,
) -> pd.DataFrame:
    """
    For each metro station: nearest road junction, its distance, and the bus
    routes that pass through a junction within ``walk_radius_m``.

    Metro headway is not part of the processed dataset, so it is not reported.
    """
    cols = ["station", "line", "lat", "lon", "nearest_node", "nearest_junction",
            "distance_m", "bus_routes_within_radius", "is_interchange"]
    ms = net.metro_stations
    if ms is None or ms.empty:
        return pd.DataFrame(columns=cols)

    nodes = net.nodes[["node_id", "y", "x", "name"]].dropna(subset=["x", "y"])

    # node_id -> set(route_id) for every node touched by a route edge
    node_routes: dict[int, set[str]] = {}
    if not net.bus_route_edges.empty:
        e_uv = net.edges.set_index("edge_id")[["u", "v"]]
        for _, r in net.bus_route_edges.iterrows():
            eid = int(r["edge_id"])
            if eid in e_uv.index:
                for n in (int(e_uv.loc[eid, "u"]), int(e_uv.loc[eid, "v"])):
                    node_routes.setdefault(n, set()).add(str(r["route_id"]))

    rows = []
    for _, st in ms.iterrows():
        lat, lon = float(st["lat"]), float(st["lon"])
        dists = [
            (haversine_m(lat, lon, float(n["y"]), float(n["x"])), int(n["node_id"]), n["name"])
            for _, n in nodes.iterrows()
        ]
        if not dists:
            continue
        d_min, nid, nname = min(dists, key=lambda t: t[0])
        routes: set[str] = set()
        for d, n_id, _ in dists:
            if d <= walk_radius_m:
                routes |= node_routes.get(n_id, set())
        rows.append({
            "station": st["name"],
            "line": st.get("line", None),
            "lat": lat,
            "lon": lon,
            "nearest_node": nid,
            "nearest_junction": nname,
            "distance_m": round(d_min, 0),
            "bus_routes_within_radius": ", ".join(sorted(routes)) if routes else "",
            "is_interchange": bool(routes),
        })
    return pd.DataFrame(rows, columns=cols)

