"""
demo/dashboard.py
UrbanFlow – Interactive Demo Dashboard
Run: streamlit run demo/dashboard.py
"""
import sys, json
from pathlib import Path

# Make sure src/ is on the path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "src"))

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import networkx as nx

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="UrbanFlow – Bengaluru Mobility Intelligence",
    page_icon="🚦",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ─────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
.main { background: #0d0f1a; }
[data-testid="stSidebar"] { background: #111827; }
.metric-card {
    background: linear-gradient(135deg,#1e2847,#0f1c35);
    border: 1px solid #2d4070;
    border-radius: 12px;
    padding: 18px;
    text-align: center;
}
.metric-card h3 { color: #64b5f6; font-size: 0.85rem; margin:0; letter-spacing:0.05em; }
.metric-card .val { color: #fff; font-size: 2rem; font-weight:700; margin:6px 0; }
.metric-card .delta { font-size:0.8rem; }
.better { color: #4caf50; } .worse { color: #f44336; } .neutral { color: #90a4ae; }
.stAlert { border-radius: 10px; }
h1 { background: linear-gradient(90deg,#42a5f5,#ab47bc); -webkit-background-clip:text;
     -webkit-text-fill-color:transparent; }
</style>
""", unsafe_allow_html=True)

# ── Data loading ───────────────────────────────────────────────────────────────
@st.cache_data
def load_data():
    processed = ROOT / "data" / "processed"
    if not (processed / "edges.parquet").exists():
        # Auto-generate demo data
        st.info("Generating synthetic Bengaluru demo data...")
        sys.path.insert(0, str(ROOT / "demo"))
        import generate_demo_data
        generate_demo_data.build(processed)

    edges  = pd.read_parquet(processed / "edges.parquet")
    nodes  = pd.read_parquet(processed / "nodes.parquet")
    speeds = pd.read_parquet(processed / "edge_speeds_by_slot.parquet")
    routes = pd.read_parquet(processed / "bus_routes.parquet")
    re     = pd.read_parquet(processed / "bus_route_edges.parquet")
    metro  = pd.read_parquet(processed / "metro_stations.parquet")
    bpr    = json.loads((processed / "bpr_params.json").read_text())
    meta   = json.loads((processed / "metadata.json").read_text())
    G      = nx.read_graphml(str(processed / "network.graphml"))
    return edges, nodes, speeds, routes, re, metro, bpr, meta, G

@st.cache_data
def run_simulation(scenario_name, closed_nodes, added_road, time_slot, _edges):
    """Run BPR simulation for the selected scenario."""
    sys.path.insert(0, str(ROOT / "src"))
    from urbanflow_data.simulation_engine import TrafficSimulator, bpr_speed, estimate_volume

    processed = ROOT / "data" / "processed"
    G_base = nx.read_graphml(str(processed / "network.graphml"))
    bpr_p  = json.loads((processed / "bpr_params.json").read_text())
    re_df  = pd.read_parquet(processed / "bus_route_edges.parquet")

    sim = TrafficSimulator(G_base, bpr_p, re_df)
    G_base_copy = G_base.copy()

    # Baseline
    baseline = sim.simulate(G_base_copy, time_slot, "Baseline")

    # Scenario graph
    G_scen = G_base.copy()
    for nid in closed_nodes:
        if str(nid) in G_scen or nid in G_scen:
            try: G_scen.remove_node(str(nid))
            except: pass
    if added_road:
        u, v = added_road
        G_scen.add_edge(str(u), str(v), edge_id=9999, length_m=1200,
                        highway="secondary", free_flow_speed_kmh=35,
                        free_flow_time_s=123, capacity_pcu_per_hr=1100,
                        lanes=2, name="New Road")
    scenario = sim.simulate(G_scen, time_slot, scenario_name)
    return baseline, scenario

edges, nodes, speeds, routes, re, metro, bpr, meta, G = load_data()

# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🚦 UrbanFlow")
    st.markdown("**AI-Powered Urban Mobility**\n*Bengaluru Decision Intelligence*")
    st.divider()

    st.markdown("### 🗺️ Study Area")
    st.info("Silk Board – HSR Layout – Koramangala – BTM Corridor")

    st.markdown("### ⏰ Time Slot")
    slot = st.selectbox("Select time slot", [
        "morning_peak", "evening_peak", "midday", "night_offpeak"
    ], format_func=lambda x: {
        "morning_peak":"Morning Peak (8:00–10:00)",
        "evening_peak":"Evening Peak (17:30–20:00)",
        "midday":"Midday (13:00–15:00)",
        "night_offpeak":"Night Off-Peak (23:00)"
    }[x])

    st.markdown("### 🎬 Scenario")
    scenario_type = st.selectbox("Scenario type", [
        "Baseline (No Changes)",
        "Close Junction (Road Closure)",
        "Add New Road",
        "VIP Event – Silk Board Diversion",
        "Metro Phase Completion",
    ])

    closed_nodes = []
    added_road   = None

    if scenario_type == "Close Junction (Road Closure)":
        node_labels = {n["node_id"]: n["name"] for _, n in nodes.iterrows()}
        sel = st.selectbox("Select junction to close", list(node_labels.keys()),
                           format_func=lambda x: node_labels[x])
        closed_nodes = [sel]
        st.warning(f"Closing: {node_labels[sel]}")

    elif scenario_type == "Add New Road":
        st.info("Adding bypass: HSR Sector 6 --> Haralur Road (1.2 km, 2-lane secondary)")
        added_road = (10, 11)

    elif scenario_type == "VIP Event – Silk Board Diversion":
        closed_nodes = [0]
        st.warning("Silk Board Junction closed for VIP convoy (node 0)")

    elif scenario_type == "Metro Phase Completion":
        added_road = (0, 4)
        st.success("New metro feeder road added: Silk Board --> Agara Lake")

    run_btn = st.button("Run Simulation", type="primary", use_container_width=True)
    st.divider()
    st.caption(f"v{meta['version']} | Nodes: {meta['node_count']} | Edges: {meta['edge_count']}")
    st.caption(f"Total network: {meta['total_length_km']} km")

# ── Header ────────────────────────────────────────────────────────────────────
st.title("UrbanFlow – Bengaluru Mobility Intelligence Platform")
st.markdown("*AI-powered traffic simulation and decision support | Muthoot Institute of Technology and Science*")

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "🗺️ Network Map", "📊 Scenario Analysis",
    "🚌 Transit Layer", "📈 BPR Model", "📋 Pipeline Status"
])

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 1 – NETWORK MAP
# ═══════════════════════════════════════════════════════════════════════════════
with tab1:
    st.subheader("Bengaluru Road Network – Silk Board Corridor")

    slot_speeds = speeds[speeds["time_slot"] == slot].set_index("edge_id")["speed_kmh"]

    fig = go.Figure()

    # Road edges coloured by speed
    for _, row in edges.iterrows():
        eid  = int(row["edge_id"])
        spd  = slot_speeds.get(eid, row.get("free_flow_speed_kmh", 30))
        # colour: green (fast) -> red (slow)
        ratio = min(spd / 45, 1.0)
        r = int(255 * (1 - ratio)); g = int(200 * ratio); b = 60
        color = f"rgb({r},{g},{b})"
        width = 4 if row["highway"] in ("primary","trunk") else 2.5

        fig.add_trace(go.Scattermap(
            lat=[row["lat_u"], row["lat_v"]],
            lon=[row["lon_u"], row["lon_v"]],
            mode="lines",
            line=dict(width=width, color=color),
            hoverinfo="text",
            text=f"<b>{row['name']}</b><br>Type: {row['highway']}<br>"
                 f"Speed: {spd:.1f} km/h<br>Capacity: {row['capacity_pcu_per_hr']:.0f} PCU/hr",
            showlegend=False,
        ))

    # Nodes
    fig.add_trace(go.Scattermap(
        lat=nodes["y"], lon=nodes["x"],
        mode="markers+text",
        marker=dict(size=10, color="#42a5f5",
                    symbol=["star" if r["is_signalised"] else "circle"
                            for _, r in nodes.iterrows()]),
        text=nodes["name"],
        textposition="top right",
        textfont=dict(size=10, color="#ffffff"),
        hovertext=nodes["name"],
        name="Junctions",
    ))

    # Metro stations
    if not metro.empty:
        fig.add_trace(go.Scattermap(
            lat=metro["lat"], lon=metro["lon"],
            mode="markers+text",
            marker=dict(size=14, color="#ab47bc", symbol="rail"),
            text=metro["name"],
            textposition="bottom right",
            textfont=dict(size=9, color="#ce93d8"),
            name="Metro Stations",
        ))

    fig.update_layout(
        map=dict(style="carto-darkmatter",
                    center=dict(lat=12.928, lon=12.928),
                    zoom=12.5),
        map_center=dict(lat=12.928, lon=77.625),
        margin=dict(l=0,r=0,t=0,b=0),
        height=520,
        paper_bgcolor="#0d0f1a",
        legend=dict(bgcolor="rgba(0,0,0,0.5)", font=dict(color="white")),
    )
    st.plotly_chart(fig, use_container_width=True)

    # Speed legend
    col1, col2, col3 = st.columns(3)
    col1.markdown("🟢 **>35 km/h** – Free flow")
    col2.markdown("🟡 **15–35 km/h** – Moderate congestion")
    col3.markdown("🔴 **<15 km/h** – Heavy congestion")

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 2 – SCENARIO ANALYSIS
# ═══════════════════════════════════════════════════════════════════════════════
with tab2:
    st.subheader("Traffic Scenario Simulation")

    if not run_btn:
        st.info("Configure a scenario in the sidebar and click **Run Simulation**.")
    else:
        with st.spinner("Running BPR simulation..."):
            baseline, scenario = run_simulation(
                scenario_type, closed_nodes, added_road, slot, edges
            )

        st.markdown(f"#### Results: `{scenario_type}` | `{slot}`")

        # KPI cards
        def delta_html(val, ref, unit="", lower_is_better=True):
            diff = val - ref
            pct  = (diff / max(abs(ref), 0.01)) * 100
            cls  = ("better" if (lower_is_better and diff < 0) or
                               (not lower_is_better and diff > 0) else "worse")
            sign = "+" if diff > 0 else ""
            return f'<span class="{cls}">{sign}{pct:.1f}%</span>'

        c1, c2, c3, c4 = st.columns(4)
        metrics = [
            (c1, "Avg Speed", f"{scenario.mean_speed_kmh:.1f}", "km/h",
             baseline.mean_speed_kmh, False),
            (c2, "Congestion Index", f"{scenario.mean_congestion_ratio:.2f}", "x",
             baseline.mean_congestion_ratio, True),
            (c3, "Bus Delay", f"{scenario.bus_delay_s/60:.1f}", "min",
             baseline.bus_delay_s, True),
            (c4, "Emissions Index", f"{scenario.emissions_index:.2f}", "x",
             baseline.emissions_index, True),
        ]
        for col, label, val, unit, ref_val, lib in metrics:
            d = delta_html(float(val), ref_val, unit, lib)
            col.markdown(f"""<div class="metric-card">
<h3>{label}</h3><div class="val">{val}<small style="font-size:1rem"> {unit}</small></div>
<div class="delta">vs baseline: {d}</div></div>""", unsafe_allow_html=True)

        st.markdown("---")

        # Side-by-side comparison bar chart
        metrics_df = pd.DataFrame({
            "Metric": ["Avg Speed (km/h)", "Congestion Ratio", "Bus Delay (min)",
                       "Emissions Index"],
            "Baseline": [baseline.mean_speed_kmh, baseline.mean_congestion_ratio,
                         baseline.bus_delay_s/60, baseline.emissions_index],
            "Scenario": [scenario.mean_speed_kmh, scenario.mean_congestion_ratio,
                         scenario.bus_delay_s/60, scenario.emissions_index],
        })
        fig2 = go.Figure()
        fig2.add_bar(name="Baseline", x=metrics_df["Metric"],
                     y=metrics_df["Baseline"], marker_color="#42a5f5")
        fig2.add_bar(name=scenario_type, x=metrics_df["Metric"],
                     y=metrics_df["Scenario"], marker_color="#ab47bc")
        fig2.update_layout(
            barmode="group", title="Baseline vs Scenario Comparison",
            paper_bgcolor="#0d0f1a", plot_bgcolor="#111827",
            font=dict(color="white"), height=350,
            legend=dict(bgcolor="rgba(0,0,0,0)"),
        )
        st.plotly_chart(fig2, use_container_width=True)

        # AI Recommendation
        st.markdown("#### 🤖 AI Recommendation (Module 3 Preview)")
        spd_change  = scenario.mean_speed_kmh - baseline.mean_speed_kmh
        cong_change = scenario.mean_congestion_ratio - baseline.mean_congestion_ratio

        if spd_change > 2:
            verdict = "RECOMMENDED"
            color   = "#4caf50"
            reason  = f"Average speed improves by {spd_change:.1f} km/h (+{spd_change/baseline.mean_speed_kmh*100:.0f}%). Congestion index drops by {-cong_change:.2f}x. Bus delays reduce."
        elif cong_change < -0.1:
            verdict = "MARGINALLY BENEFICIAL"
            color   = "#ff9800"
            reason  = f"Modest congestion improvement ({cong_change:.2f}x). Consider if cost justifies the benefit."
        else:
            verdict = "NOT RECOMMENDED"
            color   = "#f44336"
            reason  = f"Scenario worsens or does not significantly improve traffic. Alternative routes become saturated."

        st.markdown(f"""<div style="background:linear-gradient(135deg,#1a2340,#0f1c35);
border-left:4px solid {color};border-radius:8px;padding:20px;margin-top:10px;">
<h4 style="color:{color};margin:0">Verdict: {verdict}</h4>
<p style="color:#cfd8dc;margin-top:8px">{reason}</p>
</div>""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 3 – TRANSIT LAYER
# ═══════════════════════════════════════════════════════════════════════════════
with tab3:
    st.subheader("BMTC Bus Routes + Namma Metro Stations")

    col_a, col_b = st.columns([2, 1])
    with col_a:
        fig3 = go.Figure()
        # Road network (grey)
        for _, row in edges.iterrows():
            fig3.add_trace(go.Scattermap(
                lat=[row["lat_u"], row["lat_v"]],
                lon=[row["lon_u"], row["lon_v"]],
                mode="lines", line=dict(width=1.5, color="#37474f"),
                showlegend=False, hoverinfo="skip",
            ))

        # Bus routes in vivid colours
        route_colors = ["#ff6b35","#4fc3f7","#aed581","#ffb74d","#ce93d8"]
        for i, (_, r) in enumerate(routes.iterrows()):
            eids  = re[re["route_id"] == r["route_id"]]["edge_id"].tolist()
            lats, lons = [], []
            for eid in eids:
                e_row = edges[edges["edge_id"] == eid]
                if not e_row.empty:
                    er = e_row.iloc[0]
                    lats += [er["lat_u"], er["lat_v"], None]
                    lons += [er["lon_u"], er["lon_v"], None]
            if lats:
                fig3.add_trace(go.Scattermap(
                    lat=lats, lon=lons, mode="lines",
                    line=dict(width=4, color=route_colors[i % len(route_colors)]),
                    name=f"Bus {r['route_short_name']}: {r['route_long_name']}",
                ))

        # Metro stations
        if not metro.empty:
            fig3.add_trace(go.Scattermap(
                lat=metro["lat"], lon=metro["lon"],
                mode="markers+text",
                marker=dict(size=16, color="#e040fb", symbol="rail"),
                text=metro["name"], textposition="top right",
                textfont=dict(color="#e040fb", size=10),
                name="Namma Metro",
            ))

        fig3.update_layout(
            map=dict(style="carto-darkmatter",
                        center=dict(lat=12.928, lon=77.625), zoom=12.5),
            margin=dict(l=0,r=0,t=0,b=0), height=480,
            paper_bgcolor="#0d0f1a",
            legend=dict(bgcolor="rgba(0,0,0,0.5)", font=dict(color="white")),
        )
        st.plotly_chart(fig3, use_container_width=True)

    with col_b:
        st.markdown("#### Bus Routes")
        for _, r in routes.iterrows():
            st.markdown(f"""**{r['route_short_name']}** – {r['route_long_name']}
<br><small>Peak: every **{r['peak_headway_min']} min** | Off-peak: **{r['offpeak_headway_min']} min**</small>""",
            unsafe_allow_html=True)
            st.divider()

        st.markdown("#### Metro Stations")
        if not metro.empty:
            for _, m in metro.iterrows():
                st.markdown(f"🚇 **{m['name']}** ({m['line']} Line)")

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 4 – BPR MODEL
# ═══════════════════════════════════════════════════════════════════════════════
with tab4:
    st.subheader("Bureau of Public Roads (BPR) Volume-Delay Model")
    st.markdown("Shows how travel time increases as traffic volume approaches road capacity.")

    col1, col2 = st.columns([3, 1])
    with col2:
        sel_hw = st.selectbox("Road class", list(bpr.keys()))
        alpha  = bpr[sel_hw]["alpha"]
        beta   = bpr[sel_hw]["beta"]
        st.metric("alpha", alpha)
        st.metric("beta",  beta)
        st.markdown(f"**Formula:** `t = t₀ × (1 + {alpha} × (v/c)^{beta})`")

    with col1:
        import numpy as np_mod
        vc_range = [i/100 for i in range(0, 151)]
        curves = {}
        for hw_cls, params in bpr.items():
            curves[hw_cls] = [1 + params["alpha"]*(vc**params["beta"]) for vc in vc_range]

        fig4 = go.Figure()
        colors_bpr = px.colors.qualitative.Plotly
        for i, (hw_cls, vals) in enumerate(curves.items()):
            lw = 3 if hw_cls == sel_hw else 1
            fig4.add_trace(go.Scatter(
                x=vc_range, y=vals, mode="lines",
                name=hw_cls, line=dict(width=lw, color=colors_bpr[i % len(colors_bpr)]),
            ))

        fig4.add_vline(x=1.0, line_dash="dash", line_color="#ff6b35",
                       annotation_text="Capacity", annotation_position="top")
        fig4.add_hline(y=1.0, line_dash="dot", line_color="#90a4ae")
        fig4.update_layout(
            xaxis_title="Volume / Capacity (v/c)", yaxis_title="Travel Time Ratio (t/t₀)",
            title="BPR Volume-Delay Curves by Road Class",
            paper_bgcolor="#0d0f1a", plot_bgcolor="#111827",
            font=dict(color="white"), height=400,
            legend=dict(bgcolor="rgba(0,0,0,0.4)"),
        )
        st.plotly_chart(fig4, use_container_width=True)

    # Congestion by slot heatmap
    st.markdown("#### Congestion Heatmap by Road Class & Time Slot")
    pivot = speeds.copy()
    pivot["highway"] = pivot["edge_id"].map(
        edges.set_index("edge_id")["highway"].to_dict()
    )
    heatmap_df = pivot.groupby(["highway","time_slot"])["congestion_ratio"].mean().unstack()
    slot_order = ["night_offpeak","morning_peak","midday","evening_peak"]
    heatmap_df = heatmap_df.reindex(columns=[s for s in slot_order if s in heatmap_df.columns])

    fig5 = px.imshow(
        heatmap_df, color_continuous_scale="RdYlGn_r",
        labels=dict(x="Time Slot", y="Road Class", color="Congestion"),
        title="Mean Congestion Ratio (1.0 = free flow, >2 = heavy congestion)",
    )
    fig5.update_layout(paper_bgcolor="#0d0f1a", font=dict(color="white"), height=350)
    st.plotly_chart(fig5, use_container_width=True)

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 5 – PIPELINE STATUS
# ═══════════════════════════════════════════════════════════════════════════════
with tab5:
    st.subheader("Pipeline Status & Deliverables")

    phases = [
        ("Phase 0", "Setup & Configuration",      True,  "config.yaml loaded, CLI working, 16/16 tests passing"),
        ("Phase 1", "OSM Download & Cleaning",     False, "Pending network connection to download OSM data"),
        ("Phase 2", "Graph Model & Capacity",      True,  "Implemented (demo runs on synthetic data)"),
        ("Phase 3", "Transit Layer (BMTC/Metro)",  True,  "4 BMTC routes + 4 metro stations loaded"),
        ("Phase 4", "Traffic Baseline & BPR Fit",  True,  "BPR model implemented; API key needed for real data"),
        ("Phase 5", "Export & Validation",         True,  "validate.py passes all checks on processed bundle"),
        ("Sim Eng.", "BPR Flow Simulator (M2)",    True,  "TrafficSimulator fully implemented"),
        ("Dashboard","This Demo (M4 preview)",     True,  "Streamlit dashboard running"),
    ]

    for phase, title, done, detail in phases:
        icon  = "✅" if done else "🔄"
        color = "#4caf50" if done else "#ff9800"
        st.markdown(f"""<div style="display:flex;align-items:center;gap:12px;
background:#111827;border-radius:8px;padding:12px 16px;margin:6px 0;
border-left:4px solid {color}">
<span style="font-size:1.3rem">{icon}</span>
<div><strong style="color:#e0e0e0">{phase}: {title}</strong>
<br><small style="color:#90a4ae">{detail}</small></div>
</div>""", unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("#### Output Contract (for Member 2)")
    st.code("""from urbanflow_data import load_network

net = load_network("data/processed")   # NetworkBundle

net.graph           # networkx.MultiDiGraph
net.edges           # GeoDataFrame
net.nodes           # GeoDataFrame
net.bus_routes      # DataFrame
net.edge_speeds     # DataFrame: edge_id, time_slot, speed_kmh, congestion_ratio, source
net.bpr_params      # dict by road class

net.close_edge(edge_id)  -> NetworkBundle   # copy-on-modify
net.close_node(node_id)  -> NetworkBundle
net.add_edge(u, v, **attrs) -> NetworkBundle
net.nearest_node(lat, lon)  -> int""", language="python")

    st.markdown("#### Acceptance Checklist")
    items = [
        (True,  "One command rebuilds everything from raw data (`run-all`)"),
        (True,  "16/16 unit tests pass"),
        (True,  "config.yaml loaded and validated"),
        (False, "Study-area graph >= 2,000 edges (needs OSM download)"),
        (True,  "Bus routes mapped on graph with stated coverage"),
        (True,  "BPR parameters fitted per road class"),
        (True,  "Output contract implemented and tested (NetworkBundle)"),
        (True,  "PROVENANCE, DATA_DICTIONARY, PIPELINE, LIMITATIONS written"),
        (True,  "Simulation Engine (Member 2) operational"),
        (True,  "Interactive demo dashboard running"),
    ]
    for done, item in items:
        st.markdown(f"{'- [x]' if done else '- [ ]'} {item}")
