"""
scripts/demo_check.py
Smoke-test for Stage A: generates demo data if absent, loads the NetworkBundle,
runs a baseline and a closure scenario, and asserts the metrics change.

Exit 0 on success, 1 on failure.  Used manually and in CI.
"""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "src"))


def main() -> int:
    processed = ROOT / "data" / "processed"

    # ── 1. Generate demo data if not present ──────────────────────────────────
    if not (processed / "network.graphml").exists():
        print("[demo_check] Generating synthetic demo data...")
        sys.path.insert(0, str(ROOT / "demo"))
        import generate_demo_data
        generate_demo_data.build(processed)

    # ── 2. Load the NetworkBundle ─────────────────────────────────────────────
    print("[demo_check] Loading NetworkBundle...")
    from urbanflow_data.network_bundle import load_network
    net = load_network(processed)
    print(f"[demo_check] {net!r}")
    assert net.graph.number_of_nodes() > 0, "Graph has no nodes!"
    assert net.graph.number_of_edges() > 0, "Graph has no edges!"

    # ── 3. Import the simulator ───────────────────────────────────────────────
    from urbanflow_data.simulation_engine import TrafficSimulator

    sim = TrafficSimulator(
        G=net.graph,
        bpr_params=net.bpr_params,
        bus_route_edges=net.bus_route_edges,
    )

    # ── 4. Baseline simulation ────────────────────────────────────────────────
    print("[demo_check] Running baseline simulation (morning_peak)...")
    baseline = sim.simulate(net.graph, time_slot="morning_peak", scenario_name="Baseline")
    print(f"  {baseline.summary()}")
    assert baseline.mean_congestion_ratio >= 1.0, "Baseline congestion should be >= 1.0"

    # ── 5. Closure scenario — close node 0 (Silk Board) ───────────────────────
    print("[demo_check] Running closure scenario (close node 0 – Silk Board)...")
    net_closed = net.close_node(0)
    closure = sim.simulate(net_closed.graph, time_slot="morning_peak", scenario_name="Close Silk Board")
    print(f"  {closure.summary()}")

    # The two scenarios should produce different results.
    different = (
        closure.mean_congestion_ratio != baseline.mean_congestion_ratio
        or closure.mean_speed_kmh != baseline.mean_speed_kmh
    )
    if not different:
        print("[demo_check] FAIL: closure scenario is identical to baseline — routing is not topology-sensitive.")
        return 1

    print("[demo_check] Scenarios produce different results ✓")

    # ── 6. New-road scenario — add edge 10→11 ────────────────────────────────
    print("[demo_check] Running add-road scenario (edge 10→11)...")
    net_new_road = net.add_edge(
        10, 11,
        edge_id=9000, length_m=1200.0, lanes=2,
        highway="secondary", maxspeed_kmh=40,
        free_flow_speed_kmh=35.0, free_flow_time_s=123.4,
        capacity_pcu_per_hr=2210.0,
        is_bridge=False, is_flyover=False, has_signal_at_v=False,
        name="HSR-Haralur Bypass",
    )
    new_road = sim.simulate(net_new_road.graph, time_slot="morning_peak", scenario_name="Add Road")
    print(f"  {new_road.summary()}")
    # New road should carry positive volume on edge 9000 (if the simulator assigns flow)
    # (This assertion is strengthened after A2; for now we just verify it runs.)
    print("[demo_check] Add-road scenario ran successfully ✓")

    print("\n[demo_check] ALL CHECKS PASSED ✓")
    return 0


if __name__ == "__main__":
    sys.exit(main())
