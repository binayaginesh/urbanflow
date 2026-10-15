"""
simulation_engine.py – Member 2: BPR-based Traffic Flow Simulator
Runs scenario comparisons and returns congestion/travel-time metrics.
"""
from __future__ import annotations
import math
from dataclasses import dataclass, field
from typing import Any

import networkx as nx
import pandas as pd


# ── Output contract ───────────────────────────────────────────────────────────
@dataclass
class SimResult:
    scenario_name: str
    time_slot: str
    total_travel_time_s: float
    mean_congestion_ratio: float
    mean_speed_kmh: float
    bottleneck_edges: list[int]          # top-5 congested edge_ids
    bus_delay_s: float                    # extra delay on bus route edges
    emissions_index: float                # relative to free-flow (1.0 = no extra)
    edge_speeds: dict[int, float]         # edge_id -> simulated speed_kmh
    edge_volumes: dict[int, float]        # edge_id -> estimated PCU/hr
    metrics: dict[str, Any] = field(default_factory=dict)

    def summary(self) -> str:
        return (f"[{self.scenario_name}] slot={self.time_slot} | "
                f"TT={self.total_travel_time_s/60:.1f} min | "
                f"Cong={self.mean_congestion_ratio:.2f}x | "
                f"Speed={self.mean_speed_kmh:.1f} km/h | "
                f"Emissions={self.emissions_index:.2f}x")


# ── BPR helper ────────────────────────────────────────────────────────────────
def bpr_time(t0: float, volume: float, capacity: float,
             alpha: float = 0.15, beta: float = 4.0) -> float:
    return t0 * (1.0 + alpha * (volume / max(capacity, 1)) ** beta)


def bpr_speed(ff_speed: float, volume: float, capacity: float,
              alpha: float = 0.15, beta: float = 4.0) -> float:
    ratio = 1.0 + alpha * (volume / max(capacity, 1)) ** beta
    return ff_speed / ratio


# ── Volume estimation ─────────────────────────────────────────────────────────
SLOT_VOLUME_FACTOR = {
    "night_offpeak":  0.15,
    "morning_peak":   0.90,
    "midday":         0.55,
    "evening_peak":   0.95,
}

def estimate_volume(capacity: float, time_slot: str, hw: str) -> float:
    """Estimate PCU/hr volume from capacity and time slot."""
    base = SLOT_VOLUME_FACTOR.get(time_slot, 0.5)
    # Primary roads are more saturated during peak
    hw_factor = {"motorway":0.85,"trunk":0.80,"primary":0.88,
                 "secondary":0.75,"tertiary":0.60,"residential":0.35,
                 "unclassified":0.50,"service":0.25}
    return capacity * base * hw_factor.get(hw, 0.50)


# ── Main simulator ────────────────────────────────────────────────────────────
class TrafficSimulator:
    """
    BPR-based traffic flow simulator.
    Accepts a NetworkX MultiDiGraph + edge speeds baseline, runs scenarios.
    """

    def __init__(self, G: nx.MultiDiGraph, bpr_params: dict[str, Any],
                 bus_route_edges: pd.DataFrame | None = None):
        self.G_base   = G
        self.bpr_params = bpr_params
        self.bus_route_edges = bus_route_edges  # DataFrame: route_id, seq, edge_id

    def simulate(self, G: nx.MultiDiGraph, time_slot: str,
                 scenario_name: str = "Baseline") -> SimResult:
        """Run BPR simulation on graph G for given time_slot."""
        edge_speeds: dict[int, float] = {}
        edge_volumes: dict[int, float] = {}
        travel_times: list[float] = []
        cong_ratios:  list[float] = []

        alpha = 0.15; beta = 4.0

        for u, v, k, d in G.edges(data=True, keys=True):
            eid = int(d.get("edge_id", -1))
            hw  = str(d.get("highway","unclassified"))
            ff  = float(d.get("free_flow_speed_kmh", 30))
            fft = float(d.get("free_flow_time_s", 60))
            cap = float(d.get("capacity_pcu_per_hr", 1000))
            lm  = float(d.get("length_m", 500))

            bpr = self.bpr_params.get(hw, {"alpha":0.15,"beta":4.0})
            vol = estimate_volume(cap, time_slot, hw)

            sim_speed = bpr_speed(ff, vol, cap, bpr["alpha"], bpr["beta"])
            sim_tt    = lm / (sim_speed / 3.6) if sim_speed > 0 else 9999
            cong      = fft / sim_tt if sim_tt > 0 else 1.0
            # cong ratio = observed/ff (>1 = congested)
            cong_ratio = sim_tt / max(fft, 1)

            edge_speeds[eid]  = round(sim_speed, 2)
            edge_volumes[eid] = round(vol, 1)
            travel_times.append(sim_tt * lm / 1000)  # weighted by km
            cong_ratios.append(cong_ratio)

        if not travel_times:
            return SimResult(scenario_name, time_slot, 0, 1, 30, [], 0, 1, {}, {})

        total_tt = sum(travel_times)
        mean_cong = sum(cong_ratios) / len(cong_ratios)
        mean_spd  = sum(edge_speeds.values()) / max(len(edge_speeds), 1)

        # Bottleneck edges (top-5 by congestion)
        sorted_edges = sorted(cong_ratios, reverse=True)
        cong_threshold = sorted_edges[min(4, len(sorted_edges)-1)]
        bottlenecks = [eid for eid, spd in edge_speeds.items()
                       if spd < 10 or eid in list(edge_speeds.keys())[:5]][:5]

        # Bus delay: extra travel time on bus route edges
        bus_delay = 0.0
        if self.bus_route_edges is not None and not self.bus_route_edges.empty:
            bus_eids = set(self.bus_route_edges["edge_id"].tolist())
            for u2, v2, k2, d2 in G.edges(data=True, keys=True):
                eid2 = int(d2.get("edge_id",-1))
                if eid2 in bus_eids:
                    ff2 = float(d2.get("free_flow_time_s",60))
                    sim_spd = edge_speeds.get(eid2, float(d2.get("free_flow_speed_kmh",30)))
                    lm2 = float(d2.get("length_m",500))
                    sim_t2 = lm2 / (sim_spd / 3.6) if sim_spd > 0 else 9999
                    bus_delay += max(sim_t2 - ff2, 0)

        # Emissions index (simplified: inversely proportional to speed)
        mean_ff_spd = sum(float(d.get("free_flow_speed_kmh",30))
                         for _,_,d in G.edges(data=True)) / max(G.number_of_edges(),1)
        emissions = mean_ff_spd / max(mean_spd, 1)

        return SimResult(
            scenario_name=scenario_name,
            time_slot=time_slot,
            total_travel_time_s=total_tt,
            mean_congestion_ratio=round(mean_cong, 3),
            mean_speed_kmh=round(mean_spd, 2),
            bottleneck_edges=bottlenecks,
            bus_delay_s=round(bus_delay, 1),
            emissions_index=round(emissions, 3),
            edge_speeds=edge_speeds,
            edge_volumes=edge_volumes,
        )

    def compare_scenarios(self, scenarios: list[tuple[str, nx.MultiDiGraph]],
                          time_slot: str) -> list[SimResult]:
        """Run simulation for multiple scenarios and return results list."""
        return [self.simulate(G, time_slot, name) for name, G in scenarios]
