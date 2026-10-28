"""
tests/test_decision_layer.py
Stage A – A3a + A3b: decision scoring, verdict, explain, TOPSIS, Monte Carlo.
"""
from __future__ import annotations
import pytest
import networkx as nx
import pandas as pd

from urbanflow_data.simulation_engine import TrafficSimulator, SimResult
from urbanflow_data.decision_layer import (
    ScenarioMetrics,
    score_scenario,
    verdict,
    explain,
    topsis_rank,
    monte_carlo_confidence,
    VERDICT_RECOMMENDED,
    VERDICT_MODERATE,
    VERDICT_NOT_RECOMMENDED,
)

# ── Shared config stubs ────────────────────────────────────────────────────────
WEIGHTS = {
    "congestion_ratio": 0.35,
    "speed_kmh":        0.30,
    "bus_delay_s":      0.20,
    "emissions_index":  0.15,
}
THRESHOLDS = {"recommended": 0.60, "moderate": 0.40}


def _make_sim_result(
    name: str = "Test",
    cong: float = 1.5,
    speed: float = 25.0,
    bus_delay: float = 60.0,
    emissions: float = 1.2,
) -> SimResult:
    return SimResult(
        scenario_name=name,
        time_slot="morning_peak",
        total_travel_time_s=3000.0,
        mean_congestion_ratio=cong,
        mean_speed_kmh=speed,
        bottleneck_edges=[],
        bus_delay_s=bus_delay,
        emissions_index=emissions,
        edge_speeds={},
        edge_volumes={},
    )


def _make_sm(
    baseline_cong: float = 1.8,
    baseline_speed: float = 20.0,
    baseline_bus: float = 120.0,
    baseline_emis: float = 1.5,
    scen_cong: float = 1.3,
    scen_speed: float = 28.0,
    scen_bus: float = 80.0,
    scen_emis: float = 1.1,
    cost_index: float = 0.3,
    feasibility: float = 1.0,
) -> ScenarioMetrics:
    base = _make_sim_result("Baseline", baseline_cong, baseline_speed, baseline_bus, baseline_emis)
    scen = _make_sim_result("Scenario", scen_cong, scen_speed, scen_bus, scen_emis)
    return ScenarioMetrics("Scenario", scen, base, cost_index, feasibility)


# ──────────────────────────────────────────────────────────────────────────────
# ScenarioMetrics delta properties
# ──────────────────────────────────────────────────────────────────────────────
def test_delta_congestion_sign():
    sm = _make_sm(baseline_cong=2.0, scen_cong=1.5)
    assert sm.delta_congestion == pytest.approx(-0.5)


def test_delta_speed_sign():
    sm = _make_sm(baseline_speed=20.0, scen_speed=28.0)
    assert sm.delta_speed == pytest.approx(8.0)


# ──────────────────────────────────────────────────────────────────────────────
# score_scenario
# ──────────────────────────────────────────────────────────────────────────────
def test_score_bounds():
    sm    = _make_sm()
    s     = score_scenario(sm, WEIGHTS)
    assert 0.0 <= s <= 1.0, f"Score out of bounds: {s}"


def test_score_improves_with_better_scenario():
    sm_good = _make_sm(baseline_cong=2.5, scen_cong=1.2, baseline_speed=15, scen_speed=35)
    sm_bad  = _make_sm(baseline_cong=1.2, scen_cong=2.5, baseline_speed=35, scen_speed=15)
    assert score_scenario(sm_good, WEIGHTS) > score_scenario(sm_bad, WEIGHTS)


def test_score_penalised_by_feasibility():
    sm_full  = _make_sm(feasibility=1.0)
    sm_half  = _make_sm(feasibility=0.5)
    s_full   = score_scenario(sm_full,  WEIGHTS)
    s_halved = score_scenario(sm_half,  WEIGHTS)
    assert s_halved < s_full + 1e-9, "Lower feasibility must not increase score"


def test_score_unchanged_scenario():
    """A scenario identical to baseline should score ≈ 0.5 (neutral)."""
    base = _make_sim_result()
    scen = _make_sim_result()
    sm   = ScenarioMetrics("Same", scen, base, 0.0, 1.0)
    s    = score_scenario(sm, WEIGHTS)
    assert 0.45 <= s <= 0.55, f"Neutral scenario should score near 0.5; got {s}"


# ──────────────────────────────────────────────────────────────────────────────
# verdict
# ──────────────────────────────────────────────────────────────────────────────
def test_verdict_recommended_at_threshold():
    v = verdict(THRESHOLDS["recommended"], THRESHOLDS)
    assert v == VERDICT_RECOMMENDED


def test_verdict_recommended_above_threshold():
    v = verdict(0.95, THRESHOLDS)
    assert v == VERDICT_RECOMMENDED


def test_verdict_moderate_at_threshold():
    v = verdict(THRESHOLDS["moderate"], THRESHOLDS)
    assert v == VERDICT_MODERATE


def test_verdict_moderate_between_thresholds():
    mid = (THRESHOLDS["recommended"] + THRESHOLDS["moderate"]) / 2
    v   = verdict(mid, THRESHOLDS)
    assert v == VERDICT_MODERATE


def test_verdict_not_recommended_below_moderate():
    v = verdict(THRESHOLDS["moderate"] - 0.01, THRESHOLDS)
    assert v == VERDICT_NOT_RECOMMENDED


def test_verdict_not_recommended_at_zero():
    v = verdict(0.0, THRESHOLDS)
    assert v == VERDICT_NOT_RECOMMENDED


def test_verdict_values_are_fixed_strings():
    """Verify the three labels are the canonical strings."""
    assert VERDICT_RECOMMENDED     == "RECOMMENDED"
    assert VERDICT_MODERATE        == "MODERATE"
    assert VERDICT_NOT_RECOMMENDED == "NOT RECOMMENDED"


# ──────────────────────────────────────────────────────────────────────────────
# explain
# ──────────────────────────────────────────────────────────────────────────────
def test_explain_returns_nonempty_string():
    sm = _make_sm()
    s  = score_scenario(sm, WEIGHTS)
    v  = verdict(s, THRESHOLDS)
    e  = explain(sm, s, v)
    assert isinstance(e, str) and len(e) > 20


def test_explain_contains_verdict():
    sm = _make_sm(baseline_cong=2.5, scen_cong=1.1, baseline_speed=15, scen_speed=38)
    s  = score_scenario(sm, WEIGHTS)
    v  = verdict(s, THRESHOLDS)
    e  = explain(sm, s, v)
    assert v in e


def test_explain_contains_numeric_deltas():
    """Explanation must report actual numbers, not generic strings."""
    sm = _make_sm()
    s  = score_scenario(sm, WEIGHTS)
    v  = verdict(s, THRESHOLDS)
    e  = explain(sm, s, v)
    # At least one number with a decimal point should appear
    import re
    assert re.search(r"\d+\.\d+", e), "Explanation must contain numeric deltas"


# ──────────────────────────────────────────────────────────────────────────────
# topsis_rank
# ──────────────────────────────────────────────────────────────────────────────
def _make_ranked_scenarios():
    """Create three scenarios: Best >> Good > Mediocre."""
    base = _make_sim_result("Baseline", 2.5, 15, 200, 1.8)

    best  = ScenarioMetrics("Best",     _make_sim_result("Best",     1.0, 40, 10,  0.9), base, 0.4, 1.0)
    good  = ScenarioMetrics("Good",     _make_sim_result("Good",     1.6, 28, 80,  1.2), base, 0.3, 0.9)
    medi  = ScenarioMetrics("Mediocre", _make_sim_result("Mediocre", 2.2, 18, 150, 1.6), base, 0.2, 0.8)

    scored = [(sm, score_scenario(sm, WEIGHTS)) for sm in (best, good, medi)]
    return scored


def test_topsis_returns_all_scenarios():
    ranked = topsis_rank(_make_ranked_scenarios(), WEIGHTS)
    assert len(ranked) == 3


def test_topsis_best_ranks_first():
    ranked = topsis_rank(_make_ranked_scenarios(), WEIGHTS)
    assert ranked[0][0] == "Best", f"Expected 'Best' first; got {ranked[0][0]}"


def test_topsis_scores_in_01():
    ranked = topsis_rank(_make_ranked_scenarios(), WEIGHTS)
    for name, score in ranked:
        assert 0.0 <= score <= 1.0, f"{name} TOPSIS score out of [0,1]: {score}"


def test_topsis_strictly_descending():
    ranked = topsis_rank(_make_ranked_scenarios(), WEIGHTS)
    scores = [s for _, s in ranked]
    assert all(scores[i] >= scores[i + 1] for i in range(len(scores) - 1)), \
        f"TOPSIS scores not descending: {scores}"


def test_topsis_empty_input():
    assert topsis_rank([], WEIGHTS) == []


def test_topsis_single_scenario():
    base = _make_sim_result("Baseline")
    sm   = ScenarioMetrics("Solo", _make_sim_result("Solo", 1.3, 30, 50, 1.1), base, 0.0, 1.0)
    ranked = topsis_rank([(sm, 0.7)], WEIGHTS)
    assert len(ranked) == 1
    assert 0.0 <= ranked[0][1] <= 1.0


# ──────────────────────────────────────────────────────────────────────────────
# monte_carlo_confidence
# ──────────────────────────────────────────────────────────────────────────────
def _make_graph_for_mc():
    G = nx.MultiDiGraph()
    nodes = [(0, 77.610, 12.917), (1, 77.620, 12.917), (2, 77.630, 12.917)]
    for nid, x, y in nodes:
        G.add_node(nid, x=x, y=y, node_id=nid)
    edges = [
        (0, 1, 0, "primary",   1500, 800),
        (1, 0, 1, "primary",   1500, 800),
        (1, 2, 2, "secondary", 1300, 600),
        (2, 1, 3, "secondary", 1300, 600),
    ]
    FF = {"primary": 40.5, "secondary": 31.5}
    for u, v, eid, hw, cap, lm in edges:
        ff = FF[hw]
        G.add_edge(u, v, edge_id=eid, length_m=lm, lanes=1,
                   highway=hw, maxspeed_kmh=int(ff/0.9),
                   free_flow_speed_kmh=ff,
                   free_flow_time_s=lm / (ff / 3.6),
                   capacity_pcu_per_hr=cap,
                   is_bridge=False, is_flyover=False,
                   name=f"Road_{eid}")
    return G


def test_monte_carlo_confidence_in_range():
    G = _make_graph_for_mc()
    bpr = {hw: {"alpha": 0.15, "beta": 4.0}
           for hw in ("primary", "secondary", "motorway", "trunk",
                      "tertiary", "residential", "unclassified", "service")}
    sim = TrafficSimulator(G, bpr)

    base_res = sim.simulate(G, "morning_peak", "Baseline")
    scen_res = sim.simulate(G, "morning_peak", "Scenario")
    sm = ScenarioMetrics("Scenario", scen_res, base_res, 0.3, 1.0)

    confidence = monte_carlo_confidence(
        sm=sm,
        simulator=sim,
        scenario_graph=G,
        baseline_graph=G,
        time_slot="morning_peak",
        weights=WEIGHTS,
        thresholds=THRESHOLDS,
        n_runs=20,          # small for speed in tests
        demand_sigma_pct=0.15,
        rng_seed=42,
    )
    assert 0.0 <= confidence <= 1.0, f"Confidence out of [0,1]: {confidence}"


def test_monte_carlo_deterministic():
    """Same seed → same confidence value."""
    G = _make_graph_for_mc()
    bpr = {hw: {"alpha": 0.15, "beta": 4.0}
           for hw in ("primary", "secondary", "motorway", "trunk",
                      "tertiary", "residential", "unclassified", "service")}
    sim = TrafficSimulator(G, bpr)

    base_res = sim.simulate(G, "morning_peak", "Baseline")
    scen_res = sim.simulate(G, "morning_peak", "Scenario")
    sm = ScenarioMetrics("Scenario", scen_res, base_res, 0.3, 1.0)

    kwargs = dict(
        sm=sm, simulator=sim, scenario_graph=G, baseline_graph=G,
        time_slot="morning_peak", weights=WEIGHTS, thresholds=THRESHOLDS,
        n_runs=10, demand_sigma_pct=0.10, rng_seed=7,
    )
    c1 = monte_carlo_confidence(**kwargs)
    c2 = monte_carlo_confidence(**kwargs)
    assert c1 == c2, "Same seed must yield same confidence"
