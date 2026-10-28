"""
tests/test_optimizer.py
Stage A – A3c: InterventionLibrary and suggest_top3 optimizer.
"""
from __future__ import annotations
import pytest
import networkx as nx

from urbanflow_data.optimizer import (
    InterventionLibrary,
    SuggestedIntervention,
    suggest_top3,
)
from urbanflow_data.decision_layer import (
    VERDICT_RECOMMENDED,
    VERDICT_MODERATE,
    VERDICT_NOT_RECOMMENDED,
)


# ── Minimal config fixture ────────────────────────────────────────────────────
MINIMAL_CFG = {
    "decision_intelligence": {
        "criteria_weights": {
            "congestion_ratio": 0.35,
            "speed_kmh":        0.30,
            "bus_delay_s":      0.20,
            "emissions_index":  0.15,
        },
        "verdict_thresholds": {"recommended": 0.60, "moderate": 0.40},
        "optimizer_candidates": [
            {
                "name": "Close Node A",
                "type": "close_node",
                "params": {"node_id": 1},
                "cost_index": 0.1,
                "feasibility": 0.9,
            },
            {
                "name": "Add New Road",
                "type": "add_edge",
                "params": {
                    "u": 0,
                    "v": 2,
                    "attrs": {
                        "edge_id": 9999,
                        "length_m": 800.0,
                        "lanes": 2,
                        "highway": "secondary",
                        "maxspeed_kmh": 35,
                        "free_flow_speed_kmh": 31.5,
                        "free_flow_time_s": 91.4,
                        "capacity_pcu_per_hr": 2210.0,
                        "is_bridge": False,
                        "is_flyover": False,
                        "has_signal_at_v": False,
                        "name": "New Bypass",
                    },
                },
                "cost_index": 0.5,
                "feasibility": 0.8,
            },
            {
                "name": "Close Node B",
                "type": "close_node",
                "params": {"node_id": 2},
                "cost_index": 0.05,
                "feasibility": 0.95,
            },
        ],
    }
}


BPR = {hw: {"alpha": 0.15, "beta": 4.0}
       for hw in ("primary", "secondary", "tertiary", "residential",
                  "unclassified", "service", "motorway", "trunk")}


def _make_graph() -> nx.MultiDiGraph:
    """Small 4-node connected graph for optimizer testing."""
    G = nx.MultiDiGraph()
    nodes = [(0, 77.61, 12.91), (1, 77.62, 12.91), (2, 77.63, 12.91), (3, 77.62, 12.92)]
    for nid, x, y in nodes:
        G.add_node(nid, x=x, y=y, node_id=nid)

    edges = [
        (0, 1, 0, "primary",   1500, 800),
        (1, 0, 1, "primary",   1500, 800),
        (1, 2, 2, "secondary", 1300, 600),
        (2, 1, 3, "secondary", 1300, 600),
        (0, 3, 4, "tertiary",  1000, 400),
        (3, 0, 5, "tertiary",  1000, 400),
        (3, 2, 6, "tertiary",  1000, 400),
        (2, 3, 7, "tertiary",  1000, 400),
    ]
    for u, v, eid, hw, cap, lm in edges:
        ff = {"primary": 40.5, "secondary": 31.5, "tertiary": 25.2}[hw]
        G.add_edge(u, v, edge_id=eid, length_m=lm, lanes=1 + (hw == "primary"),
                   highway=hw, maxspeed_kmh=int(ff / 0.9),
                   free_flow_speed_kmh=ff, free_flow_time_s=lm / (ff / 3.6),
                   capacity_pcu_per_hr=cap, is_bridge=False, is_flyover=False,
                   name=f"Road_{eid}")
    return G


# ── InterventionLibrary tests ──────────────────────────────────────────────────
class TestInterventionLibrary:
    def test_loads_candidates_from_config(self):
        lib = InterventionLibrary(MINIMAL_CFG)
        assert len(lib.candidates()) == 3

    def test_empty_config_returns_empty_list(self):
        lib = InterventionLibrary({})
        assert lib.candidates() == []

    def test_apply_close_node_returns_copy(self):
        G   = _make_graph()
        lib = InterventionLibrary(MINIMAL_CFG)
        cand = MINIMAL_CFG["decision_intelligence"]["optimizer_candidates"][0]  # close_node 1
        G2  = lib.apply(cand, G)
        assert 1 not in G2               # node removed in copy
        assert 1 in G                    # original unchanged

    def test_apply_add_edge_returns_copy(self):
        G   = _make_graph()
        lib = InterventionLibrary(MINIMAL_CFG)
        cand = MINIMAL_CFG["decision_intelligence"]["optimizer_candidates"][1]  # add_edge
        G2  = lib.apply(cand, G)
        assert G2.number_of_edges() > G.number_of_edges()
        assert G.number_of_edges() == 8  # original unchanged

    def test_apply_unknown_type_raises(self):
        G   = _make_graph()
        lib = InterventionLibrary({})
        with pytest.raises(ValueError, match="Unknown intervention type"):
            lib.apply({"type": "teleport", "params": {}}, G)


# ── suggest_top3 tests ─────────────────────────────────────────────────────────
class TestSuggestTop3:
    def test_returns_at_most_3(self):
        G       = _make_graph()
        results = suggest_top3(G, BPR, "morning_peak", MINIMAL_CFG)
        assert len(results) <= 3

    def test_returns_list_of_suggested_interventions(self):
        G       = _make_graph()
        results = suggest_top3(G, BPR, "morning_peak", MINIMAL_CFG)
        for r in results:
            assert isinstance(r, SuggestedIntervention)

    def test_names_are_unique(self):
        G       = _make_graph()
        results = suggest_top3(G, BPR, "morning_peak", MINIMAL_CFG)
        names   = [r.name for r in results]
        assert len(names) == len(set(names)), "Duplicate names in results"

    def test_verdict_labels_are_valid(self):
        G       = _make_graph()
        results = suggest_top3(G, BPR, "morning_peak", MINIMAL_CFG)
        valid   = {VERDICT_RECOMMENDED, VERDICT_MODERATE, VERDICT_NOT_RECOMMENDED}
        for r in results:
            assert r.verdict_label in valid, f"Invalid verdict: {r.verdict_label!r}"

    def test_topsis_scores_in_01(self):
        G       = _make_graph()
        results = suggest_top3(G, BPR, "morning_peak", MINIMAL_CFG)
        for r in results:
            assert 0.0 <= r.topsis_score <= 1.0

    def test_composite_scores_in_01(self):
        G       = _make_graph()
        results = suggest_top3(G, BPR, "morning_peak", MINIMAL_CFG)
        for r in results:
            assert 0.0 <= r.composite_score <= 1.0

    def test_topsis_descending_order(self):
        G       = _make_graph()
        results = suggest_top3(G, BPR, "morning_peak", MINIMAL_CFG)
        scores  = [r.topsis_score for r in results]
        assert all(scores[i] >= scores[i + 1] - 1e-9 for i in range(len(scores) - 1)), \
            f"Results not in descending TOPSIS order: {scores}"

    def test_explanation_nonempty(self):
        G       = _make_graph()
        results = suggest_top3(G, BPR, "morning_peak", MINIMAL_CFG)
        for r in results:
            assert len(r.explanation) > 10

    def test_no_candidates_returns_empty(self):
        G   = _make_graph()
        cfg = {"decision_intelligence": {"optimizer_candidates": []}}
        assert suggest_top3(G, BPR, "morning_peak", cfg) == []

    def test_baseline_not_mutated(self):
        """The base graph must not be modified after suggesting interventions."""
        G            = _make_graph()
        edge_count   = G.number_of_edges()
        node_count   = G.number_of_nodes()
        suggest_top3(G, BPR, "morning_peak", MINIMAL_CFG)
        assert G.number_of_edges() == edge_count, "suggest_top3 mutated base graph edges"
        assert G.number_of_nodes() == node_count, "suggest_top3 mutated base graph nodes"

    def test_works_across_slots(self):
        G = _make_graph()
        for slot in ["night_offpeak", "morning_peak", "midday", "evening_peak"]:
            results = suggest_top3(G, BPR, slot, MINIMAL_CFG)
            assert isinstance(results, list)
