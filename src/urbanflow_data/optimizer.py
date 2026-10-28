"""
optimizer.py – Stage A: Top-3 Intervention Optimizer
=====================================================

Reads candidate interventions from config.decision_intelligence.optimizer_candidates,
evaluates each one by running simulate() + score_scenario() on the scenario graph,
and returns the top-3 ranked by TOPSIS.

Design rules:
  - Candidate specs live entirely in config.yaml (never hard-coded here).
  - No LLM computes any number; all arithmetic is numpy/pure Python.
  - Returns at most 3 results (or fewer if fewer candidates).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import networkx as nx

from urbanflow_data.decision_layer import (
    ScenarioMetrics,
    score_scenario,
    verdict,
    explain,
    topsis_rank,
)
from urbanflow_data.simulation_engine import TrafficSimulator


# ── Output type ───────────────────────────────────────────────────────────────
@dataclass
class SuggestedIntervention:
    name: str
    verdict_label: str        # RECOMMENDED | MODERATE | NOT RECOMMENDED
    topsis_score: float       # TOPSIS closeness coefficient ∈ [0, 1]
    composite_score: float    # weighted multi-criteria score ∈ [0, 1]
    explanation: str
    cost_index: float
    feasibility: float


# ── Intervention library ──────────────────────────────────────────────────────
class InterventionLibrary:
    """
    Loads candidate interventions from config['decision_intelligence']['optimizer_candidates'].
    Each candidate is a dict:
      {name: str, type: close_node|close_edge|add_edge, params: {...},
       cost_index: float, feasibility: float}
    """

    def __init__(self, cfg: dict[str, Any]) -> None:
        di = cfg.get("decision_intelligence", {})
        self._candidates: list[dict[str, Any]] = di.get("optimizer_candidates", [])

    def candidates(self) -> list[dict[str, Any]]:
        return list(self._candidates)

    def apply(
        self,
        candidate: dict[str, Any],
        net_graph: nx.MultiDiGraph,
    ) -> nx.MultiDiGraph:
        """
        Apply an intervention to a copy of the graph and return the modified copy.
        Never mutates the input graph.
        """
        G = net_graph.copy()
        intervention_type = candidate["type"]
        params = candidate.get("params", {})

        if intervention_type == "close_node":
            node_id = params["node_id"]
            if node_id in G:
                G.remove_node(node_id)

        elif intervention_type == "close_edge":
            edge_id = params["edge_id"]
            edges_to_remove = [
                (u, v, k)
                for u, v, k, d in G.edges(data=True, keys=True)
                if d.get("edge_id") == edge_id
            ]
            G.remove_edges_from(edges_to_remove)

        elif intervention_type == "add_edge":
            u = params["u"]
            v = params["v"]
            attrs = dict(params.get("attrs", {}))
            G.add_edge(u, v, **attrs)

        else:
            raise ValueError(f"Unknown intervention type: {intervention_type!r}")

        return G


# ── Optimizer entry point ─────────────────────────────────────────────────────
def suggest_top3(
    base_graph: nx.MultiDiGraph,
    bpr_params: dict[str, Any],
    time_slot: str,
    cfg: dict[str, Any],
    bus_route_edges=None,
) -> list[SuggestedIntervention]:
    """
    Evaluate every candidate intervention and return the top-3 by TOPSIS.

    Parameters
    ----------
    base_graph      : NetworkX MultiDiGraph (baseline, unmodified)
    bpr_params      : BPR parameters dict (by road class)
    time_slot       : simulation time slot name
    cfg             : config dict (must contain decision_intelligence block)
    bus_route_edges : optional bus routes DataFrame

    Returns
    -------
    list of SuggestedIntervention (length ≤ 3), sorted by TOPSIS score descending.
    """
    di       = cfg.get("decision_intelligence", {})
    weights  = di.get("criteria_weights", {
        "congestion_ratio": 0.35, "speed_kmh": 0.30,
        "bus_delay_s": 0.20, "emissions_index": 0.15,
    })
    thresholds = di.get("verdict_thresholds", {"recommended": 0.60, "moderate": 0.40})

    library  = InterventionLibrary(cfg)
    sim      = TrafficSimulator(base_graph, bpr_params, bus_route_edges)
    baseline = sim.simulate(base_graph, time_slot, "Baseline")

    scored_scenarios: list[tuple[ScenarioMetrics, float]] = []
    candidate_map: dict[str, dict] = {}

    for candidate in library.candidates():
        name = candidate["name"]
        try:
            G_scen   = library.apply(candidate, base_graph)
            sim_res  = sim.simulate(G_scen, time_slot, name)

            sm = ScenarioMetrics(
                scenario_name=name,
                sim=sim_res,
                baseline=baseline,
                cost_index=float(candidate.get("cost_index", 0.0)),
                feasibility=float(candidate.get("feasibility", 1.0)),
            )
            comp_score = score_scenario(sm, weights)
            scored_scenarios.append((sm, comp_score))
            candidate_map[name] = candidate
        except Exception as exc:
            # Log and skip; never crash the optimizer for a bad candidate
            import logging
            logging.getLogger(__name__).warning(
                "Optimizer: skipping candidate %r due to error: %s", name, exc
            )

    if not scored_scenarios:
        return []

    # Rank by TOPSIS
    ranked = topsis_rank(scored_scenarios, weights)

    # Build top-3 output
    results: list[SuggestedIntervention] = []
    sm_by_name = {sm.scenario_name: (sm, cs) for sm, cs in scored_scenarios}

    for name, topsis_score in ranked[:3]:
        sm, comp_score = sm_by_name[name]
        v_label = verdict(comp_score, thresholds)
        expl    = explain(sm, comp_score, v_label)
        results.append(SuggestedIntervention(
            name=name,
            verdict_label=v_label,
            topsis_score=round(topsis_score, 4),
            composite_score=round(comp_score, 4),
            explanation=expl,
            cost_index=sm.cost_index,
            feasibility=sm.feasibility,
        ))

    return results
