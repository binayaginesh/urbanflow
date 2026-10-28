# UrbanFlow Stage A Handoff Note

**Author:** Mehrin Fathima M S (MUT23CA042)  
**Recipient:** Swathy (Stage B: Dashboard + Validation Harness), Team  
**Date:** 2026-10-27  
**Branch:** `stage-a-decision`  
**Git Tag:** `stage-a-done`  

---

## 1. Overview of Delivered Components

In Stage A, the simulation engine was upgraded from static volume estimation to a **gravity-model demand matrix and shortest-path flow assignment**, and a complete **Decision Intelligence Layer** was implemented.

### Core Modules Delivered in `src/urbanflow_data/`:
1. **Simulation Engine Upgrade (`simulation_engine.py`)**:
   - `DemandMatrix`: Synthesizes origin-destination PCU/hr flow based on network topology, node coordinates, and time-slot capacity factors.
   - `FlowAssigner`: Assigns O-D demand over scenario shortest paths (`free_flow_time_s`), routing traffic realistically around road/node closures and onto newly added bypasses.
   - `TrafficSimulator.simulate()`: Applies BPR curves based on assigned flows, computing travel times, bottleneck edges, bus route delays, and emissions indices.
2. **Decision Layer (`decision_layer.py`)**:
   - `ScenarioMetrics`: Container for comparing scenario simulation results against baseline.
   - `score_scenario()`: Multi-criteria sigmoid scoring across congestion, speed, bus delay, emissions, cost, and feasibility.
   - `verdict()`: Config-driven 3-tier verdict (`RECOMMENDED`, `MODERATE`, `NOT RECOMMENDED`).
   - `explain()`: Deterministic plain-English explanation detailing top metric deltas vs baseline.
   - `topsis_rank()`: Multi-criteria TOPSIS ranking algorithm.
   - `monte_carlo_confidence()`: Perturbs network demand/capacities across $N$ runs to estimate stability.
3. **Intervention Optimizer (`optimizer.py`)**:
   - `InterventionLibrary`: Loads candidate interventions from `config/config.yaml`.
   - `suggest_top3()`: Evaluates candidate interventions non-destructively (copy-on-modify) and returns the top 3 ranked by TOPSIS score.
4. **Machine Learning Components (`ml_components.py`)**:
   - `CongestionTrendPredictor`: Ridge regression model predicting slot $\times$ highway class congestion ratios.
   - `AnomalyDetector`: Isolation Forest model flagging statistical outlier simulation results.

---

## 2. 10-Line Code Example for Stage B (Swathy)

Here is how Stage B dashboard or validation scripts load the network, simulate a scenario, and evaluate a decision verdict:

```python
from urbanflow_data import load_network, score_scenario, verdict, explain, ScenarioMetrics
from urbanflow_data.simulation_engine import TrafficSimulator
from urbanflow_data.config import load_config

cfg = load_config()
net = load_network("data/processed")
sim = TrafficSimulator(net.bpr_params, cfg=cfg)

# 1. Baseline and closure scenario simulations
base_res = sim.simulate(net.graph, "morning_peak", bus_route_edges=net.bus_route_edges)
scenario_net = net.close_edge(list(net.graph.edges(data=True))[0][2]["edge_id"])
scen_res = sim.simulate(scenario_net.graph, "morning_peak", bus_route_edges=scenario_net.bus_route_edges)

# 2. Decision Intelligence evaluation
metrics = ScenarioMetrics("Closure", scen_res, base_res, cost_index=0.1, feasibility=0.9)
score = score_scenario(metrics, cfg["decision_intelligence"]["criteria_weights"])
label = verdict(score, cfg["decision_intelligence"]["verdict_thresholds"])
reason = explain(metrics, base_res)
print(f"Verdict: {label} (Score: {score:.3f})\nReason: {reason}")
```

---

## 3. Top-3 Optimizer Example

```python
from urbanflow_data.optimizer import suggest_top3

suggestions = suggest_top3(
    base_graph=net.graph,
    bpr_params=net.bpr_params,
    time_slot="morning_peak",
    cfg=cfg,
    bus_route_edges=net.bus_route_edges,
)
for rank, s in enumerate(suggestions, 1):
    print(f"#{rank} {s.name} -> {s.verdict_label} (TOPSIS: {s.topsis_score:.3f})")
```

---

## 4. Test Suite & Validation Summary

- **Test Suite**: `90/90 passed` (`pytest -v tests/`).
- **Determinism**: Validated in `tests/test_simulation_engine.py` and `tests/test_decision_layer.py`.
- **Copy-on-Modify**: Original baseline graph is never mutated when evaluating scenarios.
- **Config-Driven**: Weights, thresholds, and candidate interventions are defined in `config/config.yaml`.
