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
from urbanflow_data.dashboard_cache import (
    clear_cache,
    get_cached_simulation,
    is_cache_mode,
    is_offline_mode,
    set_cache_mode,
    set_offline_mode,
)
from urbanflow_data.dashboard_ui import (
    build_bottleneck_table,
    build_highway_distribution_chart,
    build_network_map,
    build_speed_comparison_chart,
    get_custom_css,
)

# ── Page Configuration ────────────────────────────────────────────────────────
st.set_page_config(
    page_title="UrbanFlow // Bengaluru Command Center",
    page_icon="🚦",
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


# ── Sidebar Controls ──────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🚦 URBANFLOW // AGY-B")
    st.caption("AI-Powered Urban Mobility Decision Intelligence Platform")
    st.markdown("---")

    # Navigation Menu
    PAGES = [
        "🎛️ Command Center",
        "🧪 Scenario Lab",
        "⚖️ Compare & Recommend",
        "💡 AI Insights",
        "🚌 Transit & Metro",
        "🛡️ Validation Harness",
        "🗄️ Pipeline & Data",
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
    st.markdown("**⚙️ System Controls**")

    # Offline mode toggle
    offline_toggle = st.checkbox(
        "🌐 Offline Mode (no internet / tiles)",
        value=is_offline_mode(),
        help="Disables all external map tile calls; operates purely with local coordinates.",
    )
    set_offline_mode(offline_toggle)

    # Demo cache mode toggle
    cache_toggle = st.checkbox(
        "⚡ Demo Cache Mode",
        value=is_cache_mode(),
        help="Caches simulation runs to disk for instantaneous scenario demonstration.",
    )
    set_cache_mode(cache_toggle)

    if st.button("🧹 Clear Simulation Cache", use_container_width=True):
        count = clear_cache()
        st.success(f"Purged {count} cached scenario runs.")

    st.markdown("---")
    # System Info
    data_dir_path = get_data_dir()
    st.caption(f"📁 **Data Source:** `{data_dir_path.name}/`")
    st.caption(f"🌐 **Nodes:** `{net.graph.number_of_nodes()}` | **Edges:** `{net.graph.number_of_edges()}`")
    st.caption(f"🚌 **Bus Routes:** `{len(net.bus_routes)}` | **BPR Params:** `{len(net.bpr_params)} classes`")


# ── Run Baseline Simulation ───────────────────────────────────────────────────
def compute_baseline():
    return sim.simulate(net.graph, time_slot=time_slot, scenario_name="Baseline")


baseline_res = get_cached_simulation(f"baseline_{time_slot}", compute_baseline)


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE 1: COMMAND CENTER
# ═══════════════════════════════════════════════════════════════════════════════
if selected_page == "🎛️ Command Center":
    # Top System Header Banner
    st.markdown(
        f"""
        <div class="command-header">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <div>
                    <h1 class="command-title">🚦 URBANFLOW COMMAND CENTER</h1>
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
                <div class="panel-title">🗺️ Real-Time Network Congestion & Topology</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        filter_col1, filter_col2 = st.columns(2)
        with filter_col1:
            highlight_bn = st.toggle("🚨 Highlight Bottleneck Corridors", value=True)
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
                <div class="panel-title">📊 Road Hierarchy & Speed Profile</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        subtab1, subtab2 = st.tabs(["🛣️ Highway Classes", "⚡ Speed vs Cap"])
        with subtab1:
            fig_pie = build_highway_distribution_chart(net.edges)
            st.plotly_chart(fig_pie, use_container_width=True)

        with subtab2:
            fig_speed = build_speed_comparison_chart(net.edges, baseline_res)
            st.plotly_chart(fig_speed, use_container_width=True)

        # Bottlenecks summary table
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
        st.markdown("#### 🚀 Ready to test interventions?")
        st.caption("Inject flyovers, close junctions, or test VIP corridors in the Scenario Lab.")
    with qc2:
        if st.button("⚡ Quick Re-Calibrate Baseline", use_container_width=True):
            with st.spinner("Recomputing BPR volume delay curves..."):
                compute_baseline()
            st.success("Baseline state re-calibrated successfully!")
    with qc3:
        st.info("Switch to **🧪 Scenario Lab** in the sidebar to simulate before/after scenarios.")


# ═══════════════════════════════════════════════════════════════════════════════
# PLACEHOLDERS FOR REMAINING STAGE B PAGES
# ═══════════════════════════════════════════════════════════════════════════════
elif selected_page == "🧪 Scenario Lab":
    st.title("🧪 Scenario Lab")
    st.info("Scenario Lab will be fully wired in Step B3 (Before/After maps, change delta map, animated flows, traffic-light verdict card, confidence gauge, waterfall chart).")

elif selected_page == "⚖️ Compare & Recommend":
    st.title("⚖️ Compare & Recommend")
    st.info("Compare & Recommend will be wired in Step B4 (Multi-scenario side-by-side comparison & AI Suggests via suggest_top3 optimizer).")

elif selected_page == "💡 AI Insights":
    st.title("💡 AI Insights")
    st.info("AI Insights will be wired in Step B5 (Natural language explanations, ML CongestionTrendPredictor, AnomalyDetector).")

elif selected_page == "🚌 Transit & Metro":
    st.title("🚌 Transit & Metro")
    st.info("Transit & Metro will be wired in Step B6 (BMTC routes, delays, Namma Metro integration).")

elif selected_page == "🛡️ Validation Harness":
    st.title("🛡️ Validation Harness")
    st.info("Validation Harness will be wired in Step B7 (BPR error metrics, calibration tests, hold-out corridors).")

elif selected_page == "🗄️ Pipeline & Data":
    st.title("🗄️ Pipeline & Data")
    st.info("Pipeline & Data will be wired in Step B6 (Raw vs processed inspector, metadata viewer, data dictionary).")
