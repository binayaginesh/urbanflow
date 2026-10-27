"""
decision_layer.py – Stage A: Decision Intelligence / AI Layer
==============================================================

Implements:
  - ScenarioMetrics: wraps SimResult + cost/feasibility metadata
  - score_scenario():  weighted multi-criteria composite score ∈ [0, 1]
  - verdict():         3-tier label from config thresholds (never hard-coded)
  - explain():         plain-English justification from metric deltas
  - topsis_rank():     TOPSIS multi-criteria ranking of a set of scenarios
  - monte_carlo_confidence(): fraction of demand perturbation runs that agree with original verdict

Design rules (from TEAM_PLAN.md):
  - All weights and thresholds come from config.yaml (decision_intelligence block).
  - No LLM computes or changes any number.
  - No verdict is hard-coded; it is derived from the score.
  - numpy / scipy do all arithmetic.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import numpy as np

if TYPE_CHECKING:
    from urbanflow_data.simulation_engine import SimResult, TrafficSimulator
    import networkx as nx

# ── ScenarioMetrics ────────────────────────────────────────────────────────────
@dataclass
class ScenarioMetrics:
    """Wraps a SimResult with cost and feasibility metadata for MCDA."""
    scenario_name: str
    sim: "SimResult"            # scenario simulation result
    baseline: "SimResult"       # no-change baseline for same slot
    cost_index: float = 0.0     # 0–1, from config; 0=free, 1=very expensive
    feasibility: float = 1.0    # 0–1, from config; 1=fully feasible

    # Derived delta metrics (populated by score_scenario, read by explain)
    _delta: dict[str, float] = field(default_factory=dict, repr=False)

    @property
    def delta_congestion(self) -> float:
        """Scenario congestion ratio minus baseline (negative = improvement)."""
        return self.sim.mean_congestion_ratio - self.baseline.mean_congestion_ratio

    @property
    def delta_speed(self) -> float:
        """Scenario mean speed minus baseline (positive = improvement)."""
        return self.sim.mean_speed_kmh - self.baseline.mean_speed_kmh

    @property
    def delta_bus_delay(self) -> float:
        """Scenario bus delay minus baseline in seconds (negative = improvement)."""
        return self.sim.bus_delay_s - self.baseline.bus_delay_s

    @property
    def delta_emissions(self) -> float:
        """Scenario emissions index minus baseline (negative = improvement)."""
        return self.sim.emissions_index - self.baseline.emissions_index


# ── Scoring ────────────────────────────────────────────────────────────────────
def _sigmoid(x: float, scale: float = 3.0) -> float:
    """Squash a delta value into (0, 1) via sigmoid.
    Positive x → improvement → score > 0.5.
    """
    return 1.0 / (1.0 + math.exp(-scale * x))


def score_scenario(
    sm: ScenarioMetrics,
    weights: dict[str, float],
) -> float:
    """
    Compute a composite improvement score ∈ [0, 1].

    Parameters
    ----------
    sm : ScenarioMetrics
    weights : dict with keys congestion_ratio, speed_kmh, bus_delay_s,
              emissions_index — must sum to ≈ 1.0.

    Returns
    -------
    float in [0, 1]; higher = better scenario.

    Notes
    -----
    - Each metric delta is normalised by a reference magnitude so that
      different units are comparable.
    - Normalisation references (per metric):
        congestion_ratio : 1.0  (ratio)
        speed_kmh        : 10.0 km/h
        bus_delay_s      : 120 s (2 min)
        emissions_index  : 1.0  (ratio)
    - Then passed through sigmoid so the final score is bounded.
    """
    NORM = {
        "congestion_ratio": 1.0,
        "speed_kmh":        10.0,
        "bus_delay_s":      120.0,
        "emissions_index":  1.0,
    }

    # For congestion, bus_delay, emissions: negative delta is good → flip sign
    # For speed: positive delta is good → keep sign
    signed_deltas = {
        "congestion_ratio": -sm.delta_congestion / NORM["congestion_ratio"],
        "speed_kmh":         sm.delta_speed      / NORM["speed_kmh"],
        "bus_delay_s":      -sm.delta_bus_delay  / NORM["bus_delay_s"],
        "emissions_index":  -sm.delta_emissions  / NORM["emissions_index"],
    }

    w_cong  = weights.get("congestion_ratio", 0.35)
    w_spd   = weights.get("speed_kmh",        0.30)
    w_bus   = weights.get("bus_delay_s",       0.20)
    w_emis  = weights.get("emissions_index",   0.15)

    # Weighted linear combination of sigmoid-mapped deltas
    raw_score = (
        w_cong * _sigmoid(signed_deltas["congestion_ratio"])
        + w_spd  * _sigmoid(signed_deltas["speed_kmh"])
        + w_bus  * _sigmoid(signed_deltas["bus_delay_s"])
        + w_emis * _sigmoid(signed_deltas["emissions_index"])
    )

    # Apply feasibility penalty (feasibility 1.0 = no penalty)
    penalised = raw_score * sm.feasibility

    # Clamp to [0, 1]
    return max(0.0, min(1.0, penalised))


# ── Verdict ────────────────────────────────────────────────────────────────────
VERDICT_RECOMMENDED     = "RECOMMENDED"
VERDICT_MODERATE        = "MODERATE"
VERDICT_NOT_RECOMMENDED = "NOT RECOMMENDED"


def verdict(score: float, thresholds: dict[str, float]) -> str:
    """
    Map composite score to a 3-tier verdict label.

    Parameters
    ----------
    score : float in [0, 1]
    thresholds : dict with keys 'recommended' and 'moderate' (from config).
                 Threshold values come from config.yaml, not from this function.

    Returns
    -------
    One of: 'RECOMMENDED', 'MODERATE', 'NOT RECOMMENDED'
    """
    if score >= thresholds["recommended"]:
        return VERDICT_RECOMMENDED
    if score >= thresholds["moderate"]:
        return VERDICT_MODERATE
    return VERDICT_NOT_RECOMMENDED


# ── Explanation ────────────────────────────────────────────────────────────────
def explain(sm: ScenarioMetrics, score: float, verdict_label: str) -> str:
    """
    Generate a plain-English explanation for the verdict.

    Rules:
    - Never fabricates numbers; all values come from metric deltas.
    - No LLM writes or changes any text here; it is deterministic template logic.
    - Reports the three metrics with the largest absolute delta first.
    """
    metrics = [
        ("congestion", sm.delta_congestion,   "congestion ratio",  "x",   True),
        ("speed",      sm.delta_speed,        "average speed",     "km/h", False),
        ("bus_delay",  sm.delta_bus_delay,    "bus delay",         "s",   True),
        ("emissions",  sm.delta_emissions,    "emissions index",   "x",   True),
    ]
    # Sort by absolute delta (descending)
    metrics.sort(key=lambda m: abs(m[1]), reverse=True)

    parts = []
    for _, delta, label, unit, lower_is_better in metrics[:3]:
        direction = ""
        if lower_is_better:
            direction = "improves by" if delta < 0 else "worsens by"
            val = abs(delta)
        else:
            direction = "increases by" if delta > 0 else "decreases by"
            val = abs(delta)
        parts.append(f"{label} {direction} {val:.2f} {unit}")

    metrics_text = "; ".join(parts)
    cost_note = (
        f" Cost index: {sm.cost_index:.0%}."
        if sm.cost_index > 0.5
        else ""
    )
    return (
        f"Verdict: {verdict_label} (score {score:.2f}). "
        f"{metrics_text}.{cost_note} "
        f"Feasibility: {sm.feasibility:.0%}."
    )


# ── TOPSIS ranking ─────────────────────────────────────────────────────────────
def topsis_rank(
    scenarios: list[tuple[ScenarioMetrics, float]],
    weights: dict[str, float],
    *,
    higher_is_better: dict[str, bool] | None = None,
) -> list[tuple[str, float]]:
    """
    Rank scenarios by TOPSIS (Technique for Order of Preference by Similarity
    to Ideal Solution).

    Parameters
    ----------
    scenarios : list of (ScenarioMetrics, composite_score) tuples.
    weights   : criteria weights dict (same as used for score_scenario).
    higher_is_better : optional override; defaults to
        {congestion_ratio: False, speed_kmh: True,
         bus_delay_s: False, emissions_index: False}.

    Returns
    -------
    list of (scenario_name, topsis_score) sorted descending.
    """
    if not scenarios:
        return []

    if higher_is_better is None:
        higher_is_better = {
            "congestion_ratio": False,
            "speed_kmh":        True,
            "bus_delay_s":      False,
            "emissions_index":  False,
        }

    criteria = ["congestion_ratio", "speed_kmh", "bus_delay_s", "emissions_index"]
    w_vec = np.array([weights.get(c, 0.25) for c in criteria])

    # Build decision matrix: rows = scenarios, cols = criteria
    matrix_rows = []
    names = []
    for sm, _ in scenarios:
        row = [
            sm.sim.mean_congestion_ratio,
            sm.sim.mean_speed_kmh,
            sm.sim.bus_delay_s,
            sm.sim.emissions_index,
        ]
        matrix_rows.append(row)
        names.append(sm.scenario_name)

    mat = np.array(matrix_rows, dtype=float)  # (n_scenarios, n_criteria)

    # Step 1: Normalise (vector normalisation)
    col_norms = np.linalg.norm(mat, axis=0)
    col_norms[col_norms == 0] = 1.0        # avoid division by zero
    norm_mat = mat / col_norms

    # Step 2: Apply weights
    weighted = norm_mat * w_vec

    # Step 3: Ideal and anti-ideal
    ideal      = np.where(
        [higher_is_better[c] for c in criteria],
        weighted.max(axis=0),
        weighted.min(axis=0),
    )
    anti_ideal = np.where(
        [higher_is_better[c] for c in criteria],
        weighted.min(axis=0),
        weighted.max(axis=0),
    )

    # Step 4: Distance to ideal and anti-ideal
    d_pos = np.sqrt(((weighted - ideal)      ** 2).sum(axis=1))
    d_neg = np.sqrt(((weighted - anti_ideal) ** 2).sum(axis=1))

    # Step 5: Closeness coefficient
    denom = d_pos + d_neg
    denom[denom == 0] = 1e-12
    closeness = d_neg / denom

    ranked = sorted(zip(names, closeness.tolist()), key=lambda x: x[1], reverse=True)
    return ranked


# ── Monte Carlo confidence ─────────────────────────────────────────────────────
def monte_carlo_confidence(
    sm: ScenarioMetrics,
    simulator: "TrafficSimulator",
    scenario_graph: "nx.MultiDiGraph",
    baseline_graph: "nx.MultiDiGraph",
    time_slot: str,
    weights: dict[str, float],
    thresholds: dict[str, float],
    n_runs: int = 200,
    demand_sigma_pct: float = 0.15,
    rng_seed: int | None = 42,
) -> float:
    """
    Estimate confidence in the verdict by perturbing the demand implicit in
    BPR volume (±σ Gaussian) and checking agreement with the original verdict.

    The perturbation is applied by scaling edge capacities (which drives the
    DemandMatrix inside simulate()), so no demand data is invented.

    Parameters
    ----------
    sm               : original ScenarioMetrics
    simulator        : TrafficSimulator instance
    scenario_graph   : the modified graph for this scenario
    baseline_graph   : the unmodified graph
    time_slot        : e.g. 'morning_peak'
    weights          : criteria weights dict
    thresholds       : verdict thresholds dict
    n_runs           : number of Monte Carlo samples
    demand_sigma_pct : relative std dev for capacity perturbation
    rng_seed         : reproducibility seed (None = random)

    Returns
    -------
    float in [0.0, 1.0]: fraction of runs where verdict matches original.
    """
    import copy

    original_verdict = verdict(
        score_scenario(sm, weights), thresholds
    )

    rng = np.random.default_rng(rng_seed)
    matches = 0

    for _ in range(n_runs):
        # Sample a global demand scale factor (multiplicative perturbation)
        scale = rng.normal(loc=1.0, scale=demand_sigma_pct)
        scale = max(0.5, scale)  # avoid extreme negatives

        # Apply scale to capacity on a copy of the scenario graph
        G_scen_perturbed = copy.deepcopy(scenario_graph)
        for u, v, k, d in G_scen_perturbed.edges(data=True, keys=True):
            if "capacity_pcu_per_hr" in d:
                d["capacity_pcu_per_hr"] = float(d["capacity_pcu_per_hr"]) * scale

        G_base_perturbed = copy.deepcopy(baseline_graph)
        for u, v, k, d in G_base_perturbed.edges(data=True, keys=True):
            if "capacity_pcu_per_hr" in d:
                d["capacity_pcu_per_hr"] = float(d["capacity_pcu_per_hr"]) * scale

        # Re-simulate
        perturbed_sim  = simulator.simulate(G_scen_perturbed,  time_slot, "mc_scen")
        perturbed_base = simulator.simulate(G_base_perturbed, time_slot,  "mc_base")

        perturbed_sm = ScenarioMetrics(
            scenario_name=sm.scenario_name,
            sim=perturbed_sim,
            baseline=perturbed_base,
            cost_index=sm.cost_index,
            feasibility=sm.feasibility,
        )
        p_score   = score_scenario(perturbed_sm, weights)
        p_verdict = verdict(p_score, thresholds)

        if p_verdict == original_verdict:
            matches += 1

    return matches / n_runs
