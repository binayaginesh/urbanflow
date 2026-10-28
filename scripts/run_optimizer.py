"""
scripts/run_optimizer.py
CLI entry point for the top-3 intervention optimizer.
Respects URBANFLOW_DATA_DIR.

Usage:
    python scripts/run_optimizer.py --slot morning_peak
    python scripts/run_optimizer.py --slot evening_peak --data data/processed
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

# Ensure src/ is importable when called directly
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "src"))

from urbanflow_data.config import get_data_dir


def main() -> int:
    parser = argparse.ArgumentParser(
        description="UrbanFlow – Top-3 Intervention Optimizer (Stage A & B)"
    )
    parser.add_argument(
        "--slot",
        default="morning_peak",
        choices=["night_offpeak", "morning_peak", "midday", "evening_peak"],
        help="Time slot for simulation (default: morning_peak)",
    )
    parser.add_argument(
        "--data",
        default=None,
        help="Path to processed data directory (default: URBANFLOW_DATA_DIR or data/processed)",
    )
    args = parser.parse_args()

    processed = get_data_dir(args.data) if args.data else get_data_dir(ROOT / "data" / "processed")

    # ── Generate demo data if not present ────────────────────────────────────
    if not (processed / "network.graphml").exists():
        print(f"[optimizer] No processed data found; generating synthetic demo data at {processed}...")
        sys.path.insert(0, str(ROOT / "demo"))
        import generate_demo_data
        generate_demo_data.build(processed)

    # ── Load config ───────────────────────────────────────────────────────────
    from urbanflow_data.config import load_config
    cfg = load_config(root=ROOT)

    # ── Load network ──────────────────────────────────────────────────────────
    from urbanflow_data.network_bundle import load_network
    net = load_network(processed)
    print(f"[optimizer] Loaded {net!r}")

    # ── Run optimizer ─────────────────────────────────────────────────────────
    from urbanflow_data.optimizer import suggest_top3
    print(f"\n[optimizer] Evaluating interventions for slot='{args.slot}'...\n")
    suggestions = suggest_top3(
        base_graph=net.graph,
        bpr_params=net.bpr_params,
        time_slot=args.slot,
        cfg=cfg,
        bus_route_edges=net.bus_route_edges if not net.bus_route_edges.empty else None,
    )

    if not suggestions:
        print("[optimizer] No suggestions produced (check config optimizer_candidates).")
        return 1

    # ── Print results ─────────────────────────────────────────────────────────
    print("=" * 70)
    print(f"  UrbanFlow – Top Interventions for slot: {args.slot}")
    print("=" * 70)
    for rank, s in enumerate(suggestions, 1):
        verdict_badge = {
            "RECOMMENDED":     "[RECOMMENDED]",
            "MODERATE":        "[MODERATE]",
            "NOT RECOMMENDED": "[NOT RECOMMENDED]",
        }.get(s.verdict_label, f"[{s.verdict_label}]")
        print(f"\n  Rank #{rank}: {s.name}")
        print(f"  Verdict:         {verdict_badge}")
        print(f"  TOPSIS score:    {s.topsis_score:.4f}")
        print(f"  Composite score: {s.composite_score:.4f}")
        print(f"  Cost index:      {s.cost_index:.0%}")
        print(f"  Feasibility:     {s.feasibility:.0%}")
        print(f"  {s.explanation}")
    print("\n" + "=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
