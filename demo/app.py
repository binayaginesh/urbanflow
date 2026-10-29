"""
demo/app.py - UrbanFlow Dark Command-Center Dashboard.
Stage B: Platform, Integration & Visible Simulation.

Run with:
    streamlit run demo/app.py
"""
from __future__ import annotations

import sys
from pathlib import Path
import streamlit as st

# Ensure src/ is on sys.path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "src"))

from urbanflow_data.config import get_data_dir, load_config
from urbanflow_data.network_bundle import load_network
from urbanflow_data.simulation_engine import TrafficSimulator
from urbanflow_data.decision_layer import (
    ScenarioMetrics,
    score_scenario,
    verdict,
    explain,
    monte_carlo_confidence,
)
from urbanflow_data.optimizer import suggest_top3
from urbanflow_data.ml_components import CongestionTrendPredictor, AnomalyDetector
from urbanflow_data.transit_analysis import (
    compare_route_metrics,
    compute_route_metrics,
    metro_interchanges,
)
from urbanflow_data.validation_harness import run_validation
from urbanflow_data.report_generator import generate_planner_pdf_report
from urbanflow_data.dashboard_cache import (
    clear_cache,
    get_cached_simulation,
    is_cache_mode,
    is_offline_mode,
    set_cache_mode,
    set_offline_mode,
)
from urbanflow_data.dashboard_ui import (
    build_ai_suggest_card_html,
    build_anomaly_gauge,
    build_bottleneck_table,
    build_change_delta_map,
    build_comparison_bar_chart,
    build_comparison_matrix,
    build_error_by_group_chart,
    build_flow_animation_and_heatmap,
    build_highway_distribution_chart,
    build_network_map,
    build_route_delay_chart,
    build_speed_comparison_chart,
    build_transit_map,
    build_trend_prediction_chart,
    build_validation_scatter,
    build_verdict_card_html,
    build_waterfall_chart,
    get_custom_css,
)

# ── Page Configuration ────────────────────────────────────────────────────────
st.set_page_config(
    page_title="UrbanFlow // Bengaluru Command Center",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="expanded",
)

# Apply Dark Command-Center Theme
st.markdown(get_custom_css(), unsafe_allow_html=True)


# ── Data & Engine Loading ──────────────────────────────────────────────────────
@st.cache_resource
def get_cached_bundle():
    """Load config and NetworkBundle once per session."""
    data_dir = get_data_dir()
    if not (data_dir / "network.graphml").exists():
        sys.path.insert(0, str(ROOT / "demo"))
        import generate_demo_data
        generate_demo_data.build(data_dir)

    cfg = load_config(root=ROOT)
    net = load_network(data_dir)
    sim = TrafficSimulator(
        G=net.graph,
        bpr_params=net.bpr_params,
        bus_route_edges=net.bus_route_edges if not net.bus_route_edges.empty else None,
    )
    return cfg, net, sim


cfg, net, sim = get_cached_bundle()

# Preset junctions: real landmark nodes (48 Silk Board Flyover North, 52 Madiwala Police Stn) when present.
_nodes = set(int(n) for n in net.graph.nodes())
PRESET_A = 48 if 48 in _nodes else 0
PRESET_B = 52 if 52 in _nodes else 1


# ── Sidebar Controls ──────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### URBANFLOW // AGY-B")
    st.caption("AI-Powered Urban Mobility Decision Intelligence Platform")
    st.markdown("---")

    # Navigation Menu
    PAGES = [
        "Command Center",
        "Scenario Lab",
        "Compare & Recommend",
        "AI Insights",
        "Transit & Metro",
        "Validation Harness",
        "Pipeline & Data",
    ]

    selected_page = st.radio("Navigation", PAGES, index=0, label_visibility="collapsed")
    st.markdown("---")

    # Time slot selection
    st.markdown("**⏰ Temporal Profile**")
    slot_options = {
        "morning_peak": "Morning Peak (08:00 - 10:00)",
        "evening_peak": "Evening Peak (17:30 - 20:00)",
        "midday": "Midday Flow (13:00 - 15:00)",
        "night_offpeak": "Night Off-Peak (23:00)",
    }
    time_slot = st.selectbox(
        "Select Time Slot",
        options=list(slot_options.keys()),
        format_func=lambda s: slot_options[s],
        index=0,
    )

    st.markdown("---")
    st.markdown("**System Controls**")

    # Offline mode toggle
    offline_toggle = st.checkbox(
        "Offline Mode (no internet / tiles)",
        value=is_offline_mode(),
        help="Disables all external map tile calls; operates purely with local coordinates.",
    )
    set_offline_mode(offline_toggle)

    # Demo cache mode toggle
    cache_toggle = st.checkbox(
        "Demo Cache Mode",
        value=is_cache_mode(),
        help="Caches simulation runs to disk for instantaneous scenario demonstration.",
    )
    set_cache_mode(cache_toggle)

    if st.button("Clear Simulation Cache", use_container_width=True):
        count = clear_cache()
        st.success(f"Purged {count} cached scenario runs.")

    st.markdown("---")
    data_dir_path = get_data_dir()
    st.caption(f"**Data Source:** `{data_dir_path.name}/`")
    st.caption(f"**Nodes:** `{net.graph.number_of_nodes()}` | **Edges:** `{net.graph.number_of_edges()}`")
    st.caption(f"**Bus Routes:** `{len(net.bus_routes)}` | **BPR Params:** `{len(net.bpr_params)} classes`")


# ── Run Baseline Simulation ───────────────────────────────────────────────────
def compute_baseline():
    return sim.simulate(net.graph, time_slot=time_slot, scenario_name="Baseline")


baseline_res = get_cached_simulation(f"baseline_{time_slot}", compute_baseline)


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE 1: COMMAND CENTER
# ═══════════════════════════════════════════════════════════════════════════════
if selected_page == "Command Center":
    st.markdown(
        f"""
        <div class="command-header">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <div>
                    <h1 class="command-title">URBANFLOW COMMAND CENTER</h1>
                    <p class="command-subtitle">BENGALURU CORRIDOR: SILK BOARD — HSR LAYOUT — KORAMANGALA — BTM</p>
                </div>
                <div style="display:flex; gap:8px;">
                    <span class="status-pill pill-cyan">SLOT: {time_slot.upper()}</span>
                    <span class="status-pill pill-green">STATUS: OPERATIONAL</span>
                    <span class="status-pill {'pill-amber' if is_offline_mode() else 'pill-green'}">
                        MODE: {'OFFLINE' if is_offline_mode() else 'CONNECTED'}
                    </span>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Real-Time City KPI Metric Bar
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.markdown(
            f"""
            <div class="kpi-card">
                <div class="kpi-label">Mean Congestion</div>
                <div class="kpi-value" style="color:#F59E0B;">{baseline_res.mean_congestion_ratio:.2f}x</div>
                <div class="kpi-sub">Baseline Delay Multiplier</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col2:
        st.markdown(
            f"""
            <div class="kpi-card">
                <div class="kpi-label">Corridor Speed</div>
                <div class="kpi-value" style="color:#00E5FF;">{baseline_res.mean_speed_kmh:.1f} <span style="font-size:1rem;">km/h</span></div>
                <div class="kpi-sub">Network Average</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col3:
        travel_time_min = baseline_res.total_travel_time_s / 60.0
        st.markdown(
            f"""
            <div class="kpi-card">
                <div class="kpi-label">Total Travel Time</div>
                <div class="kpi-value" style="color:#F8FAFC;">{travel_time_min:.1f} <span style="font-size:1rem;">min</span></div>
                <div class="kpi-sub">Vehicle Hours Expended</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col4:
        st.markdown(
            f"""
            <div class="kpi-card">
                <div class="kpi-label">Emissions Factor</div>
                <div class="kpi-value" style="color:#EC4899;">{baseline_res.emissions_index:.2f}x</div>
                <div class="kpi-sub">CO2 / PM Index</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col5:
        num_bottlenecks = len(baseline_res.bottleneck_edges)
        st.markdown(
            f"""
            <div class="kpi-card">
                <div class="kpi-label">Active Bottlenecks</div>
                <div class="kpi-value" style="color:{'#EF4444' if num_bottlenecks > 0 else '#10B981'};">{num_bottlenecks}</div>
                <div class="kpi-sub">Critical Edges Identified</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("<div style='height:16px;'></div>", unsafe_allow_html=True)

    # Main Command Center Layout
    map_col, stat_col = st.columns([1.8, 1.2])

    with map_col:
        st.markdown(
            """
            <div class="panel-card">
                <div class="panel-title">Real-Time Network Congestion & Topology</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        filter_col1, filter_col2 = st.columns(2)
        with filter_col1:
            highlight_bn = st.toggle("Highlight Bottleneck Corridors", value=True)
        with filter_col2:
            st.caption(f"Projection: EPSG:4326 | Offline Canvas: {'Active' if is_offline_mode() else 'Standard'}")

        fig_map = build_network_map(
            net,
            sim_result=baseline_res,
            highlight_bottlenecks=highlight_bn,
            offline=is_offline_mode(),
        )
        st.plotly_chart(fig_map, use_container_width=True)

    with stat_col:
        st.markdown(
            """
            <div class="panel-card">
                <div class="panel-title">Road Hierarchy & Speed Profile</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        subtab1, subtab2 = st.tabs(["Highway Classes", "Speed vs Cap"])
        with subtab1:
            fig_pie = build_highway_distribution_chart(net.edges)
            st.plotly_chart(fig_pie, use_container_width=True)

        with subtab2:
            fig_speed = build_speed_comparison_chart(net.edges, baseline_res)
            st.plotly_chart(fig_speed, use_container_width=True)

        st.markdown("**Critical Corridor Hotspots**")
        df_bn = build_bottleneck_table(net.edges, baseline_res)
        if not df_bn.empty:
            st.dataframe(df_bn, use_container_width=True, hide_index=True)
        else:
            st.info("No severe bottlenecks detected for this time slot.")

    # Quick Simulation Trigger Footer
    st.markdown("---")
    qc1, qc2, qc3 = st.columns([1.5, 1, 1])
    with qc1:
        st.markdown("#### Ready to test interventions?")
        st.caption("Inject flyovers, close junctions, or test VIP corridors in the Scenario Lab.")
    with qc2:
        if st.button("Quick Re-Calibrate Baseline", use_container_width=True):
            with st.spinner("Recomputing BPR volume delay curves..."):
                compute_baseline()
            st.success("Baseline state re-calibrated successfully!")
    with qc3:
        st.info("Switch to **Scenario Lab** in the sidebar to simulate before/after scenarios.")


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE 2: SCENARIO LAB
# ═══════════════════════════════════════════════════════════════════════════════
elif selected_page == "Scenario Lab":
    st.markdown(
        f"""
        <div class="command-header">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <div>
                    <h1 class="command-title">SCENARIO LAB // INTERVENTION ENGINE</h1>
                    <p class="command-subtitle">SIMULATE CANDIDATE TRANSPORTATION SCENARIOS & EVALUATE DECISION VERDICTS</p>
                </div>
                <div>
                    <span class="status-pill pill-cyan">SLOT: {time_slot.upper()}</span>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Scenario selection form: nothing is simulated until "Run Scenario" is pressed
    node_choices = {int(r["node_id"]): str(r["name"]) for _, r in net.nodes.iterrows()}
    PRESETS = [
        "Close Silk Board Junction (Node 48)",
        "Add HSR-Haralur Bypass Road (Node 10 → 11)",
        "VIP Convoy Diversion (Node 48 & Node 52 Closed)",
        "Custom Node Closure",
    ]
    with st.form("scenario_form"):
        s_col1, s_col2, s_col3 = st.columns([2, 1, 1])
        with s_col1:
            preset_in = st.selectbox("Select Candidate Intervention", PRESETS, index=0)
            custom_in = st.selectbox(
                "Junction to close (used only for Custom Node Closure)",
                options=list(node_choices.keys()),
                format_func=lambda n: f"#{n} - {node_choices[n]}",
            )
        with s_col2:
            cost_in = st.slider("Capital Cost Index", 0.0, 1.0, 0.15, step=0.05)
        with s_col3:
            feas_in = st.slider("Feasibility Score", 0.5, 1.0, 0.95, step=0.05)
        run_clicked = st.form_submit_button("Run Scenario", type="primary", use_container_width=True)

    if run_clicked:
        st.session_state["scen_params"] = {
            "preset": preset_in, "custom_node": custom_in, "cost": cost_in, "feas": feas_in,
        }
    _p = st.session_state.get("scen_params")
    if _p is None:
        st.info("Choose an intervention above, then press **Run Scenario** to simulate it and see the verdict.")
        st.stop()

    preset = _p["preset"]
    cost_idx = _p["cost"]
    feas_idx = _p["feas"]
    st.caption(f"Showing results for: **{preset}** (cost index {cost_idx:.2f}, feasibility {feas_idx:.2f}). Change the inputs and press Run Scenario to update.")

    scenario_name = preset
    scenario_key = preset.replace(" ", "_").replace("(", "").replace(")", "").replace("→", "to").replace("&", "and")

    if preset.startswith("Close Silk Board"):
        scen_net = net.close_node(PRESET_A)
    elif preset.startswith("Add HSR-Haralur"):
        scen_net = net.add_edge(
            10, 11,
            edge_id=9000, length_m=1200.0, lanes=2,
            highway="secondary", maxspeed_kmh=40,
            free_flow_speed_kmh=35.0, free_flow_time_s=123.4,
            capacity_pcu_per_hr=2200.0,
            is_bridge=False, is_flyover=False, has_signal_at_v=False,
            name="HSR-Haralur Bypass",
        )
    elif preset.startswith("VIP Convoy"):
        scen_net = net.close_node(PRESET_A).close_node(PRESET_B)
    else:
        selected_node = _p["custom_node"]
        scenario_name = f"Close Junction {node_choices[selected_node]}"
        scenario_key = f"custom_close_{selected_node}"
        scen_net = net.close_node(selected_node)

    # Run / Retrieve Simulation
    def run_scen():
        return sim.simulate(scen_net.graph, time_slot=time_slot, scenario_name=scenario_name)

    scen_res = get_cached_simulation(f"scen_{scenario_key}_{time_slot}", run_scen)

    # Compute Decision Intelligence Verdict
    weights = cfg["decision_intelligence"]["criteria_weights"]
    thresholds = cfg["decision_intelligence"]["verdict_thresholds"]

    sm = ScenarioMetrics(
        scenario_name=scenario_name,
        sim=scen_res,
        baseline=baseline_res,
        cost_index=cost_idx,
        feasibility=feas_idx,
    )
    score = score_scenario(sm, weights)
    verdict_label = verdict(score, thresholds)
    explanation = explain(sm, score, verdict_label)

    def run_mc():
        return monte_carlo_confidence(
            sm=sm,
            simulator=sim,
            scenario_graph=scen_net.graph,
            baseline_graph=net.graph,
            time_slot=time_slot,
            weights=weights,
            thresholds=thresholds,
            n_runs=40,
            rng_seed=42,
        )

    confidence = get_cached_simulation(f"mc_{scenario_key}_{time_slot}", run_mc)

    # 1. Verdict Card
    st.markdown(
        build_verdict_card_html(score, verdict_label, confidence, explanation, sm),
        unsafe_allow_html=True,
    )

    # PDF Decision Brief Download
    pdf_bytes = generate_planner_pdf_report(
        scenario_metrics=sm,
        score=score,
        verdict_label=verdict_label,
        confidence=confidence,
        explanation=explanation,
        time_slot=time_slot,
        weights=weights,
    )
    st.download_button(
        label="Download Planner Decision Brief (PDF)",
        data=pdf_bytes,
        file_name=f"UrbanFlow_Decision_Brief_{scenario_key}_{time_slot}.pdf",
        mime="application/pdf",
        use_container_width=True,
    )

    # 2. Multi-Criteria Score Waterfall & Visualizations
    v_col1, v_col2 = st.columns([1.1, 1.9])

    with v_col1:
        st.markdown(
            """
            <div class="panel-card">
                <div class="panel-title">MCDA Score Contribution Waterfall</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        fig_waterfall = build_waterfall_chart(sm, score, weights)
        st.plotly_chart(fig_waterfall, use_container_width=True)

    with v_col2:
        st.markdown(
            """
            <div class="panel-card">
                <div class="panel-title">Spatial Simulation & Impact Analysis</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        tab_map, tab_delta, tab_flow = st.tabs([
            "Before vs After Maps",
            "Change (Delta) Map",
            "Vehicle Flow & Heatmap",
        ])

        with tab_map:
            sub_c1, sub_c2 = st.columns(2)
            with sub_c1:
                st.caption(f"**Baseline Network** (Speed: {baseline_res.mean_speed_kmh:.1f} km/h)")
                fig_b = build_network_map(net, baseline_res, highlight_bottlenecks=False, offline=is_offline_mode())
                st.plotly_chart(fig_b, use_container_width=True)
            with sub_c2:
                st.caption(f"**{scenario_name}** (Speed: {scen_res.mean_speed_kmh:.1f} km/h)")
                fig_s = build_network_map(scen_net, scen_res, highlight_bottlenecks=False, offline=is_offline_mode())
                st.plotly_chart(fig_s, use_container_width=True)

        with tab_delta:
            st.caption("Corridor link velocity delta vs baseline: **Green** = Relieved / Faster, **Red** = Congested / Slower, **Muted** = Unchanged.")
            fig_delta = build_change_delta_map(net, baseline_res, scen_res, offline=is_offline_mode())
            st.plotly_chart(fig_delta, use_container_width=True)

        with tab_flow:
            st.caption("Assigned traffic flows: Width proportional to PCU volume; Heatmap particles indicate vehicle density.")
            fig_flow = build_flow_animation_and_heatmap(scen_net, scen_res, offline=is_offline_mode())
            st.plotly_chart(fig_flow, use_container_width=True)


# ═══════════════════════════════════════════════════════════════════════════════
# PLACEHOLDERS FOR REMAINING STAGE B PAGES
# ═══════════════════════════════════════════════════════════════════════════════
elif selected_page == "Compare & Recommend":
    st.markdown(
        f"""
        <div class="command-header">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <div>
                    <h1 class="command-title">COMPARE & RECOMMEND // DECISION MATRIX</h1>
                    <p class="command-subtitle">SIDE-BY-SIDE MULTI-SCENARIO BENCHMARKING & "AI SUGGESTS" TOP-3 INTERVENTIONS</p>
                </div>
                <div>
                    <span class="status-pill pill-cyan">SLOT: {time_slot.upper()}</span>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    tab_compare, tab_ai = st.tabs(["Multi-Scenario Comparison Matrix", "AI Suggests (TOPSIS Ranked)"])

    scen_candidates = [
        {"name": "Baseline (Current State)", "net": net, "cost": 0.0, "feas": 1.0},
        {"name": "Close Silk Board Junction", "net": net.close_node(PRESET_A), "cost": 0.1, "feas": 0.95},
        {
            "name": "Add HSR-Haralur Bypass",
            "net": net.add_edge(
                10, 11,
                edge_id=9000, length_m=1200.0, lanes=2,
                highway="secondary", maxspeed_kmh=40,
                free_flow_speed_kmh=35.0, free_flow_time_s=123.4,
                capacity_pcu_per_hr=2200.0,
                is_bridge=False, is_flyover=False, has_signal_at_v=False,
                name="HSR-Haralur Bypass",
            ),
            "cost": 0.35, "feas": 0.90,
        },
        {"name": "VIP Convoy Diversion", "net": net.close_node(PRESET_A).close_node(1), "cost": 0.15, "feas": 0.85},
    ]

    with tab_compare:
        st.markdown(
            """
            <div class="panel-card">
                <div class="panel-title">Multi-Criteria Performance Matrix</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        matrix_data = []
        weights = cfg["decision_intelligence"]["criteria_weights"]
        thresholds = cfg["decision_intelligence"]["verdict_thresholds"]

        for cand in scen_candidates:
            cname = cand["name"]
            ckey = cname.replace(" ", "_").replace("(", "").replace(")", "").replace("→", "to")
            cnet = cand["net"]

            def _run(g=cnet.graph, name=cname):
                return sim.simulate(g, time_slot=time_slot, scenario_name=name)

            res = get_cached_simulation(f"comp_{ckey}_{time_slot}", _run)

            if cname == "Baseline (Current State)":
                matrix_data.append({
                    "name": cname,
                    "verdict": "BASELINE",
                    "score": 0.500,
                    "speed": res.mean_speed_kmh,
                    "delta_speed": 0.0,
                    "congestion": res.mean_congestion_ratio,
                    "delta_congestion": 0.0,
                    "travel_time_min": res.total_travel_time_s / 60.0,
                    "delta_tt_min": 0.0,
                    "cost_index": cand["cost"],
                    "feasibility": cand["feas"],
                })
            else:
                sm_cand = ScenarioMetrics(cname, res, baseline_res, cost_index=cand["cost"], feasibility=cand["feas"])
                score_cand = score_scenario(sm_cand, weights)
                label_cand = verdict(score_cand, thresholds)

                matrix_data.append({
                    "name": cname,
                    "verdict": label_cand,
                    "score": score_cand,
                    "speed": res.mean_speed_kmh,
                    "delta_speed": sm_cand.delta_speed,
                    "congestion": res.mean_congestion_ratio,
                    "delta_congestion": sm_cand.delta_congestion,
                    "travel_time_min": res.total_travel_time_s / 60.0,
                    "delta_tt_min": (res.total_travel_time_s - baseline_res.total_travel_time_s) / 60.0,
                    "cost_index": cand["cost"],
                    "feasibility": cand["feas"],
                })

        df_matrix = build_comparison_matrix(matrix_data)
        st.dataframe(df_matrix, use_container_width=True, hide_index=True)

        st.markdown("<div style='height:16px;'></div>", unsafe_allow_html=True)
        bc1, bc2 = st.columns(2)
        with bc1:
            fig_speed_cmp = build_comparison_bar_chart(matrix_data, metric="speed", title="Average Network Speed (km/h) - Higher is Better")
            st.plotly_chart(fig_speed_cmp, use_container_width=True)
        with bc2:
            fig_cong_cmp = build_comparison_bar_chart(matrix_data, metric="congestion", title="Mean Congestion Ratio (x) - Lower is Better")
            st.plotly_chart(fig_cong_cmp, use_container_width=True)

    with tab_ai:
        st.markdown(
            """
            <div class="panel-card">
                <div class="panel-title">AI Suggests — Autonomous Intervention Optimization</div>
                <p style="color:#94A3B8; font-size:0.85rem; margin-top:-6px;">
                    Stage A TOPSIS algorithm evaluates all library candidates across speed, congestion, transit delay, emissions, and cost trade-offs.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        def _get_top3():
            return suggest_top3(
                base_graph=net.graph,
                bpr_params=net.bpr_params,
                time_slot=time_slot,
                cfg=cfg,
                bus_route_edges=net.bus_route_edges if not net.bus_route_edges.empty else None,
            )

        top3 = get_cached_simulation(f"optimizer_top3_{time_slot}", _get_top3)

        for rank, s in enumerate(top3, 1):
            st.markdown(build_ai_suggest_card_html(rank, s), unsafe_allow_html=True)

elif selected_page == "AI Insights":
    st.markdown(
        f"""
        <div class="command-header">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <div>
                    <h1 class="command-title">AI INSIGHTS // EXPLANATORY & PREDICTIVE INTELLIGENCE</h1>
                    <p class="command-subtitle">TRANSPARENT MCDA EXPLANATIONS, ML CONGESTION FORECASTS & SIMULATION ANOMALY MONITOR</p>
                </div>
                <div>
                    <span class="status-pill pill-cyan">SLOT: {time_slot.upper()}</span>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    ai_tab1, ai_tab2, ai_tab3 = st.tabs([
        "Decision Explanations",
        "ML Congestion Predictor",
        "Anomaly Detection Monitor",
    ])

    with ai_tab1:
        st.markdown(
            """
            <div class="panel-card">
                <div class="panel-title">Deterministic Decision Explainability</div>
                <p style="color:#94A3B8; font-size:0.85rem; margin-top:-6px;">
                    UrbanFlow uses deterministic rule templates driven strictly by normalized mathematical deltas (no stochastic hallucinations or ungrounded generative numbers).
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        sample_scen_choice = st.selectbox(
            "Select Scenario to Inspect Explanation",
            [
                "Close Silk Board Junction (Node 48)",
                "Add HSR-Haralur Bypass (Node 10 → 11)",
                "VIP Convoy Diversion (Node 48 & Node 52 Closed)",
            ],
            index=0,
        )

        if sample_scen_choice == "Close Silk Board Junction (Node 48)":
            test_net = net.close_node(PRESET_A)
            cost = 0.1
            feas = 0.95
        elif sample_scen_choice == "Add HSR-Haralur Bypass (Node 10 → 11)":
            test_net = net.add_edge(10, 11, edge_id=9000, length_m=1200.0, lanes=2, highway="secondary", maxspeed_kmh=40, free_flow_speed_kmh=35.0, free_flow_time_s=123.4, capacity_pcu_per_hr=2200.0, is_bridge=False, is_flyover=False, has_signal_at_v=False, name="HSR-Haralur Bypass")
            cost = 0.35
            feas = 0.90
        else:
            test_net = net.close_node(PRESET_A).close_node(1)
            cost = 0.15
            feas = 0.85

        def _run_ai_scen():
            return sim.simulate(test_net.graph, time_slot=time_slot, scenario_name=sample_scen_choice)

        t_res = get_cached_simulation(f"ai_exp_{sample_scen_choice}_{time_slot}", _run_ai_scen)
        t_sm = ScenarioMetrics(sample_scen_choice, t_res, baseline_res, cost_index=cost, feasibility=feas)
        t_score = score_scenario(t_sm, cfg["decision_intelligence"]["criteria_weights"])
        t_label = verdict(t_score, cfg["decision_intelligence"]["verdict_thresholds"])
        t_exp = explain(t_sm, t_score, t_label)

        st.markdown(
            f"""
            <div style="background:#111827; border-left:4px solid #38BDF8; border-radius:8px; padding:18px; margin-bottom:18px;">
                <div style="font-size:0.75rem; text-transform:uppercase; color:#94A3B8; font-weight:700;">Synthesized Justification</div>
                <div style="font-size:1.1rem; color:#F8FAFC; margin-top:6px; line-height:1.5;">{t_exp}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        ec1, ec2, ec3, ec4 = st.columns(4)
        with ec1:
            st.metric("Congestion Delta", f"{t_sm.delta_congestion:+.2f}x", delta_color="inverse")
        with ec2:
            st.metric("Mean Speed Delta", f"{t_sm.delta_speed:+.1f} km/h")
        with ec3:
            st.metric("Bus Delay Delta", f"{t_sm.delta_bus_delay:+.0f} s", delta_color="inverse")
        with ec4:
            st.metric("Emissions Index Delta", f"{t_sm.delta_emissions:+.2f}x", delta_color="inverse")

    with ai_tab2:
        st.markdown(
            """
            <div class="panel-card">
                <div class="panel-title">Machine Learning Trend Forecast (Ridge Regression)</div>
                <p style="color:#94A3B8; font-size:0.85rem; margin-top:-6px;">
                    Predicts time-of-day congestion ratios across road classes based on calibrated corridor observations.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Train / Cache Congestion Trend Predictor
        @st.cache_resource
        def get_trained_predictor():
            df_hist = net.edge_speeds.merge(net.edges[["edge_id", "highway"]], on="edge_id", how="left")
            pred = CongestionTrendPredictor()
            pred.fit(df_hist)
            return pred

        predictor = get_trained_predictor()

        hw_select = st.selectbox(
            "Select Road Classification to Forecast",
            ["primary", "secondary", "trunk", "tertiary", "residential"],
            index=0,
        )

        fig_pred = build_trend_prediction_chart(predictor, highway_class=hw_select)
        st.plotly_chart(fig_pred, use_container_width=True)

        st.caption(f"Model: Ridge Regression (L2 regularization) | Historical training points: {predictor._n_samples} | Status: Online")

    with ai_tab3:
        st.markdown(
            """
            <div class="panel-card">
                <div class="panel-title">Simulation Stability & Anomaly Monitor (Isolation Forest)</div>
                <p style="color:#94A3B8; font-size:0.85rem; margin-top:-6px;">
                    Flags statistically divergent simulation runs that deviate severely from expected corridor network equilibrium.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        @st.cache_resource
        def get_trained_detector():
            ensemble = []
            for s in ["morning_peak", "evening_peak", "midday", "night_offpeak"]:
                ensemble.append(sim.simulate(net.graph, s, "Base"))
                ensemble.append(sim.simulate(net.close_node(PRESET_A).graph, s, "Close preset node"))
            det = AnomalyDetector()
            det.fit(ensemble)
            return det

        detector = get_trained_detector()
        anom_score = detector.score(baseline_res)
        is_anom = detector.is_anomaly(baseline_res)

        anom_c1, anom_c2 = st.columns([1, 1.5])
        with anom_c1:
            fig_gauge = build_anomaly_gauge(anom_score, is_anom)
            st.plotly_chart(fig_gauge, use_container_width=True)
        with anom_c2:
            st.markdown(
                f"""
                <div style="background:#111827; border:1px solid #1E293B; border-radius:10px; padding:18px;">
                    <h4 style="margin:0 0 10px 0; color:#F1F5F9;">Network Stability Status</h4>
                    <p style="color:#94A3B8; font-size:0.88rem; line-height:1.5;">
                        Current simulation state is classified as <b>{'NORMAL' if not is_anom else 'ANOMALOUS'}</b>.
                        Metric vector sits safely within the learned corridor envelope.
                    </p>
                    <ul style="color:#94A3B8; font-size:0.85rem; line-height:1.6;">
                        <li>Anomaly Score: <b style="color:#00E5FF;">{anom_score:.4f}</b> (Threshold: 0.0)</li>
                        <li>Isolation Trees: 100 Estimators</li>
                        <li>Contamination Factor: 10%</li>
                    </ul>
                </div>
                """,
                unsafe_allow_html=True,
            )

elif selected_page == "Transit & Metro":
    st.markdown(
        f"""
        <div class="command-header">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <div>
                    <h1 class="command-title">TRANSIT & METRO // BMTC + NAMMA METRO</h1>
                    <p class="command-subtitle">BUS ROUTE RUNNING TIME, SCENARIO-INDUCED BUS DELAY & METRO INTERCHANGE ACCESS</p>
                </div>
                <div>
                    <span class="status-pill pill-cyan">SLOT: {time_slot.upper()}</span>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if net.bus_routes.empty:
        st.warning("No bus routes found in the current data directory. Transit analysis is unavailable.")
    else:
        transit_presets = {
            "Baseline (no intervention)": lambda: net,
            "Close Silk Board Junction (Node 48)": lambda: net.close_node(PRESET_A),
            "VIP Convoy Diversion (Node 48 & Node 52 Closed)": lambda: net.close_node(PRESET_A).close_node(1),
        }
        t_choice = st.selectbox("Scenario to evaluate for bus impact", list(transit_presets.keys()), index=1)
        t_net = transit_presets[t_choice]()
        t_key = "".join(c if c.isalnum() else "_" for c in t_choice)

        def _run_transit_scen():
            return sim.simulate(t_net.graph, time_slot=time_slot, scenario_name=t_choice)

        t_res = baseline_res if t_net is net else get_cached_simulation(f"transit_{t_key}_{time_slot}", _run_transit_scen)

        base_routes = compute_route_metrics(net, baseline_res, time_slot, scenario_graph=net.graph)
        scen_routes = compute_route_metrics(net, t_res, time_slot, scenario_graph=t_net.graph)
        route_cmp = compare_route_metrics(base_routes, scen_routes)
        walk_r = float(cfg.get("transit", {}).get("interchange_walk_radius_m", 400))
        inter_df = metro_interchanges(net, walk_radius_m=walk_r)

        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Bus Routes Modelled", f"{len(base_routes)}")
        k2.metric(
            "Network Bus Delay (engine)",
            f"{t_res.bus_delay_s / 60:.1f} min",
            f"{(t_res.bus_delay_s - baseline_res.bus_delay_s) / 60:+.1f} min vs baseline",
            delta_color="inverse",
        )
        k3.metric("Route Links Disrupted", f"{int(scen_routes['edges_disrupted'].sum())}")
        n_inter = int(inter_df["is_interchange"].sum()) if not inter_df.empty else 0
        k4.metric("Metro–Bus Interchanges", f"{n_inter} / {len(inter_df)}", help=f"Bus route within {walk_r:.0f} m walk radius (config: transit.interchange_walk_radius_m)")

        tm_col1, tm_col2 = st.columns([1.6, 1.4])
        with tm_col1:
            st.markdown('<div class="panel-card"><div class="panel-title">Bus Routes & Metro Stations</div></div>', unsafe_allow_html=True)
            st.plotly_chart(
                build_transit_map(net, scen_routes, inter_df, scenario_graph=None if t_net is net else t_net.graph),
                use_container_width=True,
            )
        with tm_col2:
            st.markdown('<div class="panel-card"><div class="panel-title">⏱Running Time Impact</div></div>', unsafe_allow_html=True)
            st.plotly_chart(build_route_delay_chart(route_cmp), use_container_width=True)
            if not route_cmp.empty:
                st.dataframe(
                    route_cmp[["route_id", "route_name", "sim_running_time_min_base", "sim_running_time_min_scen",
                               "delta_running_time_min", "edges_disrupted"]].rename(columns={
                        "route_id": "Route", "route_name": "Description",
                        "sim_running_time_min_base": "Base (min)", "sim_running_time_min_scen": "Scenario (min)",
                        "delta_running_time_min": "Δ (min)", "edges_disrupted": "Links Cut",
                    }),
                    use_container_width=True, hide_index=True,
                )

        st.markdown("**Route Service Detail (scenario)**")
        st.dataframe(scen_routes, use_container_width=True, hide_index=True)
        st.caption(
            "Headway comes from bus_routes.parquet (peak headway in morning/evening peak, off-peak otherwise). "
            "Bus-minutes lost per hour = route delay × buses per hour. Disrupted links are excluded from running-time "
            "sums because diversion paths for buses are not modelled."
        )

        st.markdown("**Namma Metro Interchange Access**")
        if inter_df.empty:
            st.info("No metro stations in the current data directory.")
        else:
            st.dataframe(inter_df.drop(columns=["lat", "lon"]), use_container_width=True, hide_index=True)
            st.caption("Metro headways and ridership are not part of the processed dataset and are therefore not shown.")

elif selected_page == "Validation Harness":
    st.markdown(
        f"""
        <div class="command-header">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <div>
                    <h1 class="command-title">VALIDATION HARNESS // MODEL CALIBRATION & INTEGRITY</h1>
                    <p class="command-subtitle">BPR CONGESTION ERROR METRICS, CORRIDOR HOLD-OUT VALIDATION & GRAPH INTEGRITY TESTS</p>
                </div>
                <div>
                    <span class="status-pill pill-cyan">SLOT: {time_slot.upper()}</span>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Compute/retrieve simulations for all 4 slots for validation
    all_slots = ["night_offpeak", "morning_peak", "midday", "evening_peak"]
    sims_by_slot = {}
    for s in all_slots:
        sims_by_slot[s] = get_cached_simulation(
            f"val_sim_{s}",
            lambda slot_name=s: sim.simulate(net.graph, time_slot=slot_name, scenario_name="Baseline")
        )

    val_report = run_validation(net, sims_by_slot, cfg, root=ROOT)

    for note in val_report.notes:
        st.info(f"ℹ{note}")

    # Top KPI Metrics
    vk1, vk2, vk3, vk4 = st.columns(4)
    vk1.metric("Reference Type", val_report.reference_label.upper())
    
    rmse_val = val_report.edge_overall.get("rmse")
    vk2.metric("Overall RMSE", f"{rmse_val:.2f} km/h" if rmse_val is not None else "N/A")

    mape_val = val_report.edge_overall.get("mape_pct")
    vk3.metric("Overall MAPE", f"{mape_val:.1f}%" if mape_val is not None else "N/A")

    int_pass = val_report.integrity_passed
    vk4.metric(
        "Bundle Integrity",
        "PASS (All Valid)" if int_pass else "FAIL",
        f"{sum(1 for c in val_report.integrity if c['passed'])}/{len(val_report.integrity)} checks",
        delta_color="normal" if int_pass else "inverse",
    )

    val_tab1, val_tab2, val_tab3 = st.tabs([
        "Edge Speed Agreement",
        "Corridor Hold-Out Validation",
        "Bundle Integrity Suite",
    ])

    with val_tab1:
        st.markdown('<div class="panel-card"><div class="panel-title">Observed vs Simulated Edge Speed Parity</div></div>', unsafe_allow_html=True)
        vcol1, vcol2 = st.columns([1.6, 1.4])
        with vcol1:
            fig_scat = build_validation_scatter(
                val_report.edge_df,
                reference_label=f"{val_report.reference_label} speed (km/h)"
            )
            st.plotly_chart(fig_scat, use_container_width=True)
        with vcol2:
            st.markdown("**Error Metrics by Time Slot**")
            if not val_report.edge_by_slot.empty:
                st.dataframe(val_report.edge_by_slot, use_container_width=True, hide_index=True)
                fig_slot_err = build_error_by_group_chart(val_report.edge_by_slot, "time_slot", "Error (km/h) by Time Slot")
                st.plotly_chart(fig_slot_err, use_container_width=True)

        st.markdown("**Error Metrics by Highway Classification**")
        if not val_report.edge_by_class.empty:
            st.dataframe(val_report.edge_by_class, use_container_width=True, hide_index=True)

    with val_tab2:
        st.markdown('<div class="panel-card"><div class="panel-title">70/30 Hold-Out Corridor Calibration Split</div></div>', unsafe_allow_html=True)
        if val_report.corridor_df.empty:
            st.warning("No manual field observations loaded yet. Hold-out calibration tests will activate in Stage C.")
        else:
            hc1, hc2 = st.columns(2)
            with hc1:
                st.markdown("**Calibration Set Metrics (70%)**")
                cal_m = val_report.calibration_metrics
                st.json(cal_m)
            with hc2:
                st.markdown("**Hold-Out Test Set Metrics (30%)**")
                hold_m = val_report.holdout_metrics
                st.json(hold_m)
            st.dataframe(val_report.corridor_df, use_container_width=True, hide_index=True)

    with val_tab3:
        st.markdown('<div class="panel-card"><div class="panel-title">Automated Network & Bundle Integrity Tests</div></div>', unsafe_allow_html=True)
        df_int = pd.DataFrame(val_report.integrity)
        df_int["Status"] = df_int["passed"].apply(lambda p: "PASS" if p else "FAIL")
        st.dataframe(df_int[["Status", "check", "detail"]], use_container_width=True, hide_index=True)

elif selected_page == "Pipeline & Data":
    st.markdown(
        f"""
        <div class="command-header">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <div>
                    <h1 class="command-title">PIPELINE & DATA // PROVENANCE & SCHEMA INSPECTOR</h1>
                    <p class="command-subtitle">RAW VS PROCESSED DATASETS, METADATA SPECIFICATIONS & DATA DICTIONARY REFERENCE</p>
                </div>
                <div>
                    <span class="status-pill pill-cyan">DATA: {data_dir_path.name.upper()}</span>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    p_tab1, p_tab2, p_tab3, p_tab4 = st.tabs([
        "Dataset Inspector",
        "Metadata & Provenance",
        "Data Dictionary",
        "Active Configuration",
    ])

    with p_tab1:
        st.markdown('<div class="panel-card"><div class="panel-title">Processed Data Table Browser</div></div>', unsafe_allow_html=True)
        available_tables = {
            "Edges (Road Segments)": net.edges,
            "Nodes (Junctions)": net.nodes,
            "Bus Routes (BMTC)": net.bus_routes,
            "Bus Route Edges (Sequence)": net.bus_route_edges,
            "Bus Stops": net.bus_stops,
            "Metro Stations (Namma Metro)": net.metro_stations if net.metro_stations is not None else pd.DataFrame(),
            "Calibrated Edge Speeds": net.edge_speeds,
        }
        chosen_table_name = st.selectbox("Select Table to Inspect", list(available_tables.keys()), index=0)
        df_target = available_tables[chosen_table_name]

        if df_target.empty:
            st.info("This table is empty in the current data directory.")
        else:
            col_info1, col_info2 = st.columns([1, 3])
            col_info1.metric("Rows", len(df_target))
            col_info1.metric("Columns", len(df_target.columns))
            with col_info2:
                st.caption(f"**Schema Data Types:** `{dict(zip(df_target.columns, [str(t) for t in df_target.dtypes]))}`")

            # Clean display (convert geometry or bytes for table viewing)
            disp_df = df_target.copy()
            for c in disp_df.columns:
                if str(disp_df[c].dtype) == "geometry" or c == "geometry":
                    disp_df[c] = disp_df[c].astype(str)

            st.dataframe(disp_df, use_container_width=True)

    with p_tab2:
        st.markdown('<div class="panel-card"><div class="panel-title">Dataset Metadata & Provenance</div></div>', unsafe_allow_html=True)
        pm1, pm2 = st.columns(2)
        with pm1:
            st.markdown("**Build Metadata (`metadata.json`)**")
            st.json(net.meta)
            st.markdown("**BPR Parameters (`bpr_params.json`)**")
            st.json(net.bpr_params)
        with pm2:
            st.markdown("**Provenance Record (`data/PROVENANCE.md`)**")
            prov_file = ROOT / "data" / "PROVENANCE.md"
            if prov_file.exists():
                st.markdown(prov_file.read_text(encoding="utf-8"))
            else:
                st.info("PROVENANCE.md not found.")

    with p_tab3:
        st.markdown('<div class="panel-card"><div class="panel-title">Schema Data Dictionary (`docs/DATA_DICTIONARY.md`)</div></div>', unsafe_allow_html=True)
        dict_file = ROOT / "docs" / "DATA_DICTIONARY.md"
        if dict_file.exists():
            st.markdown(dict_file.read_text(encoding="utf-8"))
        else:
            st.info("DATA_DICTIONARY.md not found.")

    with p_tab4:
        st.markdown('<div class="panel-card"><div class="panel-title">Active Configuration (`config/config.yaml`)</div></div>', unsafe_allow_html=True)
        st.json(cfg)
