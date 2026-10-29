"""
dashboard_ui.py - Reusable UI components, chart builders, and dark command-center theme.
"""
from __future__ import annotations

import logging
import math
from typing import Any
import pandas as pd
import plotly.graph_objects as go

from urbanflow_data.dashboard_cache import get_offline_map_theme, is_offline_mode
from urbanflow_data.network_bundle import NetworkBundle
from urbanflow_data.simulation_engine import SimResult

logger = logging.getLogger(__name__)


def get_custom_css() -> str:
    """Return dark command-center styling CSS."""
    return """
<style>
html, body, [class*="css"], .stMarkdown, .stText {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    color: #E2E8F0;
}

code, pre {
    font-family: 'JetBrains Mono', monospace !important;
}

.stApp {
    background-color: #0B0F19;
}

[data-testid="stSidebar"] {
    background-color: #0F172A;
    border-right: 1px solid #1E293B;
}

/* Header Banner */
.command-header {
    background: linear-gradient(135deg, rgba(15, 23, 42, 0.9) 0%, rgba(30, 41, 59, 0.9) 100%);
    border: 1px solid #1E293B;
    border-left: 4px solid #00E5FF;
    border-radius: 10px;
    padding: 16px 20px;
    margin-bottom: 24px;
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.4);
}

.command-title {
    font-size: 1.6rem;
    font-weight: 800;
    letter-spacing: -0.02em;
    color: #FFFFFF;
    margin: 0;
    display: flex;
    align-items: center;
    gap: 10px;
}

.command-subtitle {
    font-size: 0.85rem;
    color: #94A3B8;
    margin-top: 4px;
    margin-bottom: 0;
}

/* Pill Badges */
.status-pill {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 9999px;
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.05em;
    text-transform: uppercase;
}

.pill-green { background: rgba(16, 185, 129, 0.15); color: #10B981; border: 1px solid #10B981; }
.pill-amber { background: rgba(245, 158, 11, 0.15); color: #F59E0B; border: 1px solid #F59E0B; }
.pill-red { background: rgba(239, 68, 68, 0.15); color: #EF4444; border: 1px solid #EF4444; }
.pill-cyan { background: rgba(0, 229, 255, 0.15); color: #00E5FF; border: 1px solid #00E5FF; }

/* Metric Cards */
.kpi-container {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 16px;
    margin-bottom: 24px;
}

.kpi-card {
    background: #111827;
    border: 1px solid #1F2937;
    border-radius: 10px;
    padding: 16px;
    box-shadow: 0 2px 10px rgba(0, 0, 0, 0.3);
    transition: transform 0.15s ease, border-color 0.15s ease;
}

.kpi-card:hover {
    border-color: #38BDF8;
    transform: translateY(-2px);
}

.kpi-label {
    font-size: 0.75rem;
    font-weight: 600;
    color: #94A3B8;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    margin-bottom: 6px;
}

.kpi-value {
    font-size: 1.8rem;
    font-weight: 800;
    color: #F8FAFC;
    line-height: 1.1;
    margin-bottom: 4px;
}

.kpi-sub {
    font-size: 0.75rem;
    color: #64748B;
}

/* Card panel container */
.panel-card {
    background: #0F172A;
    border: 1px solid #1E293B;
    border-radius: 12px;
    padding: 20px;
    margin-bottom: 20px;
}

.panel-title {
    font-size: 1.05rem;
    font-weight: 700;
    color: #F1F5F9;
    margin-bottom: 14px;
    display: flex;
    align-items: center;
    gap: 8px;
}
</style>
"""


def get_speed_color(speed_kmh: float, max_speed_kmh: float = 45.0) -> str:
    """Return hex color on a smooth red -> yellow -> green scale."""
    ratio = max(0.0, min(1.0, speed_kmh / max(1.0, max_speed_kmh)))
    ratio = round(ratio * 12) / 12.0  # quantised: few distinct colours -> few plotly traces
    if ratio < 0.5:
        f = ratio * 2.0
        r = 245
        g = int(50 + 170 * f)
        b = 50
    else:
        f = (ratio - 0.5) * 2.0
        r = int(245 - 210 * f)
        g = int(220 + 20 * f)
        b = 60
    return f"rgb({r},{g},{b})"


def _grouped_line_traces(fig: go.Figure, segs: list) -> None:
    """Draw many road segments with few traces (one per colour/width) plus one hover layer.

    segs: list of (x0, y0, x1, y1, color, width, hover_text).
    Per-edge traces made the maps very slow to render in the browser.
    """
    groups: dict = {}
    hx: list = []
    hy: list = []
    ht: list = []
    for x0, y0, x1, y1, color, width, hover in segs:
        xs, ys = groups.setdefault((color, width), ([], []))
        xs.extend([x0, x1, None])
        ys.extend([y0, y1, None])
        hx.append((x0 + x1) / 2.0)
        hy.append((y0 + y1) / 2.0)
        ht.append(hover)
    for (color, width), (xs, ys) in groups.items():
        fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines", line=dict(color=color, width=width),
                                 hoverinfo="skip", showlegend=False))
    fig.add_trace(go.Scatter(x=hx, y=hy, mode="markers", marker=dict(size=9, opacity=0),
                             hoverinfo="text", hovertext=ht, showlegend=False))


def build_network_map(
    net: NetworkBundle,
    sim_result: SimResult | None = None,
    highlight_bottlenecks: bool = False,
    offline: bool = False,
) -> go.Figure:
    """
    Build an interactive 2D command-center map of the road network.
    Uses local coordinate projection with dark theme that operates 100% offline.
    """
    theme = get_offline_map_theme()
    edges_df = net.edges
    nodes_df = net.nodes

    bottleneck_set = set(sim_result.bottleneck_edges) if sim_result else set()
    speeds_map = sim_result.edge_speeds if sim_result else {}

    fig = go.Figure()

    # Draw edge lines
    _segs: list = []
    for _, edge in edges_df.iterrows():
        eid = int(edge["edge_id"])
        lat_u, lon_u = edge.get("lat_u"), edge.get("lon_u")
        lat_v, lon_v = edge.get("lat_v"), edge.get("lon_v")

        if pd.isna(lat_u) or pd.isna(lon_u) or pd.isna(lat_v) or pd.isna(lon_v):
            continue

        spd = speeds_map.get(eid, edge.get("free_flow_speed_kmh", 30.0))
        is_bottleneck = eid in bottleneck_set

        if highlight_bottlenecks and is_bottleneck:
            line_color = "#FF1744"
            line_width = 4.5
        else:
            line_color = get_speed_color(spd)
            line_width = 3.5 if edge.get("highway") in ("primary", "trunk") else 2.0

        hover_txt = (
            f"<b>{edge.get('name', 'Segment')}</b><br>"
            f"Edge ID: #{eid}<br>"
            f"Class: {edge.get('highway')}<br>"
            f"Lanes: {edge.get('lanes', 1)} | Cap: {edge.get('capacity_pcu_per_hr', 0):.0f} PCU/hr<br>"
            f"Speed: {spd:.1f} km/h (Free Flow: {edge.get('free_flow_speed_kmh', 0):.1f} km/h)"
        )
        if is_bottleneck:
            hover_txt += "<br><span style='color:#FF1744'><b>BOTTLENECK</b></span>"

        _segs.append((lon_u, lat_u, lon_v, lat_v, line_color, line_width, hover_txt))

    _grouped_line_traces(fig, _segs)

    # Draw junction nodes
    node_x = []
    node_y = []
    node_txt = []
    node_colors = []

    for _, n in nodes_df.iterrows():
        nid = int(n["node_id"])
        x = n.get("x")
        y = n.get("y")
        if pd.isna(x) or pd.isna(y):
            continue

        is_sig = n.get("is_signalised", False)
        node_x.append(x)
        node_y.append(y)
        node_txt.append(
            f"<b>Junction: {n.get('name', f'Node {nid}')}</b><br>"
            f"Node ID: #{nid}<br>"
            f"Signalised: {'Yes ' if is_sig else 'No'}"
        )
        node_colors.append("#00E5FF" if is_sig else "#94A3B8")

    fig.add_trace(
        go.Scatter(
            x=node_x,
            y=node_y,
            mode="markers",
            marker=dict(
                size=8,
                color=node_colors,
                symbol="circle",
                line=dict(color="#0B0F19", width=1.5),
            ),
            hoverinfo="text",
            hovertext=node_txt,
            name="Junctions",
            showlegend=True,
        )
    )

    fig.update_layout(
        paper_bgcolor=theme["paper_bgcolor"],
        plot_bgcolor=theme["plot_bgcolor"],
        margin=dict(l=10, r=10, t=10, b=10),
        height=520,
        xaxis=dict(
            title="Longitude",
            showgrid=True,
            gridcolor=theme["grid_color"],
            zeroline=False,
            color="#64748B",
        ),
        yaxis=dict(
            title="Latitude",
            showgrid=True,
            gridcolor=theme["grid_color"],
            zeroline=False,
            color="#64748B",
            scaleanchor="x",
            scaleratio=1.0,
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            font=dict(color="#94A3B8", size=11),
        ),
        hoverlabel=dict(
            bgcolor="#1E293B",
            font_size=12,
            font_family="Inter",
            bordercolor="#38BDF8",
        ),
    )

    return fig


def build_highway_distribution_chart(edges_df: pd.DataFrame) -> go.Figure:
    """Build a donut chart of highway classifications in the study area."""
    counts = edges_df["highway"].value_counts().reset_index()
    counts.columns = ["highway", "count"]

    color_palette = [
        "#00E5FF", "#38BDF8", "#3B82F6", "#818CF8",
        "#A855F7", "#EC4899", "#10B981", "#F59E0B",
    ]

    fig = go.Figure(
        data=[
            go.Pie(
                labels=counts["highway"],
                values=counts["count"],
                hole=0.6,
                marker=dict(colors=color_palette[:len(counts)]),
                textinfo="label+percent",
                hoverinfo="label+value+percent",
            )
        ]
    )

    fig.update_layout(
        paper_bgcolor="#0F172A",
        plot_bgcolor="#0F172A",
        font=dict(color="#E2E8F0", family="Inter"),
        margin=dict(l=20, r=20, t=20, b=20),
        height=260,
        showlegend=False,
    )
    return fig


def build_speed_comparison_chart(
    edges_df: pd.DataFrame,
    sim_result: SimResult | None = None,
) -> go.Figure:
    """Bar chart comparing free-flow speed vs active simulated speed by highway class."""
    speeds_map = sim_result.edge_speeds if sim_result else {}
    df = edges_df.copy()
    df["active_speed"] = df["edge_id"].map(
        lambda eid: speeds_map.get(int(eid), df.loc[df["edge_id"] == eid, "free_flow_speed_kmh"].iloc[0] if (df["edge_id"] == eid).any() else 30.0)
    )

    grouped = df.groupby("highway")[["free_flow_speed_kmh", "active_speed"]].mean().reset_index()

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=grouped["highway"],
            y=grouped["free_flow_speed_kmh"],
            name="Free Flow Speed",
            marker_color="#3B82F6",
        )
    )
    fig.add_trace(
        go.Bar(
            x=grouped["highway"],
            y=grouped["active_speed"],
            name="Current Peak Speed",
            marker_color="#10B981" if sim_result is None else "#F59E0B",
        )
    )

    fig.update_layout(
        barmode="group",
        paper_bgcolor="#0F172A",
        plot_bgcolor="#0F172A",
        font=dict(color="#E2E8F0", family="Inter"),
        margin=dict(l=20, r=20, t=30, b=20),
        height=260,
        yaxis=dict(
            title="Speed (km/h)",
            gridcolor="#1E293B",
            zeroline=False,
            color="#94A3B8",
        ),
        xaxis=dict(color="#94A3B8"),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            font=dict(size=11),
        ),
    )
    return fig


def build_bottleneck_table(
    edges_df: pd.DataFrame,
    sim_result: SimResult | None = None,
) -> pd.DataFrame:
    """Return top bottleneck corridors sorted by congestion severity."""
    if sim_result is None:
        return pd.DataFrame(columns=["edge_id", "name", "highway", "speed_kmh", "status"])

    speeds_map = sim_result.edge_speeds
    rows = []
    for eid in sim_result.bottleneck_edges:
        match = edges_df[edges_df["edge_id"] == eid]
        name = match["name"].iloc[0] if not match.empty else f"Segment #{eid}"
        hw = match["highway"].iloc[0] if not match.empty else "road"
        spd = speeds_map.get(eid, 0.0)
        rows.append({
            "Edge ID": eid,
            "Corridor Name": name,
            "Class": hw,
            "Sim Speed (km/h)": round(spd, 1),
            "Severity": "CRITICAL" if spd < 15 else "CONGESTED",
        })

    return pd.DataFrame(rows)


def build_change_delta_map(
    net: NetworkBundle,
    base_sim: SimResult,
    scen_sim: SimResult,
    offline: bool = False,
) -> go.Figure:
    """
    Build a delta (change) map comparing baseline speeds vs scenario speeds.
    Edges colored: Green (improved), Red (worsened), Muted Slate (neutral).
    """
    theme = get_offline_map_theme()
    edges_df = net.edges
    nodes_df = net.nodes
    base_speeds = base_sim.edge_speeds
    scen_speeds = scen_sim.edge_speeds

    fig = go.Figure()

    _segs: list = []
    for _, edge in edges_df.iterrows():
        eid = int(edge["edge_id"])
        lat_u, lon_u = edge.get("lat_u"), edge.get("lon_u")
        lat_v, lon_v = edge.get("lat_v"), edge.get("lon_v")
        if pd.isna(lat_u) or pd.isna(lon_u) or pd.isna(lat_v) or pd.isna(lon_v):
            continue

        s0 = base_speeds.get(eid, edge.get("free_flow_speed_kmh", 30.0))
        s1 = scen_speeds.get(eid, edge.get("free_flow_speed_kmh", 30.0))
        delta = s1 - s0

        if delta > 1.0:
            color = "#10B981"  # Improved
            width = 4.0
            status = f"<span style='color:#10B981'><b>▲ IMPROVED (+{delta:.1f} km/h)</b></span>"
        elif delta < -1.0:
            color = "#EF4444"  # Worsened
            width = 4.0
            status = f"<span style='color:#EF4444'><b>▼ CONGESTED ({delta:.1f} km/h)</b></span>"
        else:
            color = "#334155"  # Neutral
            width = 2.0
            status = f"<span style='color:#94A3B8'>NEUTRAL ({delta:+.1f} km/h)</span>"

        hover_txt = (
            f"<b>{edge.get('name', 'Segment')}</b> (#{eid})<br>"
            f"Baseline: {s0:.1f} km/h → Scenario: {s1:.1f} km/h<br>"
            f"Impact: {status}"
        )

        _segs.append((lon_u, lat_u, lon_v, lat_v, color, width, hover_txt))

    _grouped_line_traces(fig, _segs)

    # Junction nodes
    node_x = [n["x"] for _, n in nodes_df.iterrows() if not pd.isna(n.get("x"))]
    node_y = [n["y"] for _, n in nodes_df.iterrows() if not pd.isna(n.get("y"))]
    fig.add_trace(
        go.Scatter(
            x=node_x,
            y=node_y,
            mode="markers",
            marker=dict(size=6, color="#00E5FF", symbol="circle"),
            hoverinfo="skip",
            name="Junctions",
            showlegend=False,
        )
    )

    fig.update_layout(
        paper_bgcolor=theme["paper_bgcolor"],
        plot_bgcolor=theme["plot_bgcolor"],
        margin=dict(l=10, r=10, t=10, b=10),
        height=500,
        xaxis=dict(showgrid=True, gridcolor=theme["grid_color"], color="#64748B", title="Longitude"),
        yaxis=dict(showgrid=True, gridcolor=theme["grid_color"], color="#64748B", scaleanchor="x", scaleratio=1.0, title="Latitude"),
        hoverlabel=dict(bgcolor="#1E293B", bordercolor="#38BDF8", font_size=12),
    )
    return fig


def build_flow_animation_and_heatmap(
    net: NetworkBundle,
    sim_result: SimResult,
    offline: bool = False,
) -> go.Figure:
    """
    Build animated vehicle flow density and heatmap visualization.
    Line widths scale with PCU flow volume and points highlight flow intensity.
    """
    theme = get_offline_map_theme()
    edges_df = net.edges
    vols = sim_result.edge_volumes
    speeds = sim_result.edge_speeds

    max_vol = max(vols.values()) if vols and max(vols.values()) > 0 else 1.0

    fig = go.Figure()

    scatter_pts_x = []
    scatter_pts_y = []
    scatter_pts_text = []
    scatter_pts_color = []
    scatter_pts_size = []

    _segs: list = []
    for _, edge in edges_df.iterrows():
        eid = int(edge["edge_id"])
        lat_u, lon_u = edge.get("lat_u"), edge.get("lon_u")
        lat_v, lon_v = edge.get("lat_v"), edge.get("lon_v")
        if pd.isna(lat_u) or pd.isna(lon_u) or pd.isna(lat_v) or pd.isna(lon_v):
            continue

        vol = vols.get(eid, 0.0)
        spd = speeds.get(eid, edge.get("free_flow_speed_kmh", 30.0))
        cap = edge.get("capacity_pcu_per_hr", 1000.0)
        vc_ratio = vol / max(1.0, cap)

        width = round((1.5 + 5.5 * min(1.0, vol / max_vol)) * 1.5) / 1.5  # quantised widths -> few traces
        color = get_speed_color(spd)

        hover_txt = (
            f"<b>{edge.get('name', 'Corridor')}</b><br>"
            f"Assigned Flow: {vol:.0f} PCU/hr<br>"
            f"Capacity: {cap:.0f} PCU/hr (v/c = {vc_ratio:.2f})<br>"
            f"Speed: {spd:.1f} km/h"
        )

        _segs.append((lon_u, lat_u, lon_v, lat_v, color, width, hover_txt))

        mid_x = (lon_u + lon_v) / 2.0
        mid_y = (lat_u + lat_v) / 2.0
        scatter_pts_x.append(mid_x)
        scatter_pts_y.append(mid_y)
        scatter_pts_text.append(hover_txt)
        scatter_pts_size.append(min(16, max(5, int((vol / max_vol) * 15))))
        scatter_pts_color.append("#FF1744" if vc_ratio > 0.8 else ("#FFD600" if vc_ratio > 0.5 else "#00E5FF"))

    _grouped_line_traces(fig, _segs)
    fig.add_trace(
        go.Scatter(
            x=scatter_pts_x,
            y=scatter_pts_y,
            mode="markers",
            marker=dict(
                size=scatter_pts_size,
                color=scatter_pts_color,
                opacity=0.85,
                line=dict(width=1, color="#0B0F19"),
            ),
            hoverinfo="text",
            hovertext=scatter_pts_text,
            name="Vehicle Flow Density",
            showlegend=True,
        )
    )

    fig.update_layout(
        paper_bgcolor=theme["paper_bgcolor"],
        plot_bgcolor=theme["plot_bgcolor"],
        margin=dict(l=10, r=10, t=10, b=10),
        height=500,
        xaxis=dict(showgrid=True, gridcolor=theme["grid_color"], color="#64748B", title="Longitude"),
        yaxis=dict(showgrid=True, gridcolor=theme["grid_color"], color="#64748B", scaleanchor="x", scaleratio=1.0, title="Latitude"),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            font=dict(color="#94A3B8", size=11),
        ),
        hoverlabel=dict(bgcolor="#1E293B", bordercolor="#38BDF8", font_size=12),
    )
    return fig


def build_verdict_card_html(
    score: float,
    verdict_label: str,
    confidence: float,
    explanation: str,
    sm: Any = None,
) -> str:
    """Generate responsive dark-mode HTML verdict card with traffic-light indicators."""
    colors = {
        "RECOMMENDED": {"bg": "rgba(16, 185, 129, 0.12)", "border": "#10B981", "badge": "#10B981", "icon": ""},
        "MODERATE": {"bg": "rgba(245, 158, 11, 0.12)", "border": "#F59E0B", "badge": "#F59E0B", "icon": ""},
        "NOT RECOMMENDED": {"bg": "rgba(239, 68, 68, 0.12)", "border": "#EF4444", "badge": "#EF4444", "icon": ""},
    }
    cfg = colors.get(verdict_label, colors["NOT RECOMMENDED"])

    conf_pct = confidence * 100.0
    conf_level = "High Stability" if conf_pct >= 80 else ("Moderate Stability" if conf_pct >= 60 else "Low Stability")
    conf_color = "#10B981" if conf_pct >= 80 else ("#F59E0B" if conf_pct >= 60 else "#EF4444")

    delta_html = ""
    if sm is not None:
        delta_html = f"""
        <div style="display:grid; grid-template-columns: repeat(4, 1fr); gap:10px; margin: 14px 0;">
            <div style="background:#0F172A; padding:10px; border-radius:8px; border:1px solid #1E293B; text-align:center;">
                <div style="font-size:0.7rem; color:#94A3B8; text-transform:uppercase;">Congestion Δ</div>
                <div style="font-size:1.1rem; font-weight:700; color:{'#10B981' if sm.delta_congestion <= 0 else '#EF4444'};">
                    {sm.delta_congestion:+.2f}x
                </div>
            </div>
            <div style="background:#0F172A; padding:10px; border-radius:8px; border:1px solid #1E293B; text-align:center;">
                <div style="font-size:0.7rem; color:#94A3B8; text-transform:uppercase;">Speed Δ</div>
                <div style="font-size:1.1rem; font-weight:700; color:{'#10B981' if sm.delta_speed >= 0 else '#EF4444'};">
                    {sm.delta_speed:+.1f} km/h
                </div>
            </div>
            <div style="background:#0F172A; padding:10px; border-radius:8px; border:1px solid #1E293B; text-align:center;">
                <div style="font-size:0.7rem; color:#94A3B8; text-transform:uppercase;">Bus Delay Δ</div>
                <div style="font-size:1.1rem; font-weight:700; color:{'#10B981' if sm.delta_bus_delay <= 0 else '#EF4444'};">
                    {sm.delta_bus_delay:+.0f} s
                </div>
            </div>
            <div style="background:#0F172A; padding:10px; border-radius:8px; border:1px solid #1E293B; text-align:center;">
                <div style="font-size:0.7rem; color:#94A3B8; text-transform:uppercase;">Emissions Δ</div>
                <div style="font-size:1.1rem; font-weight:700; color:{'#10B981' if sm.delta_emissions <= 0 else '#EF4444'};">
                    {sm.delta_emissions:+.2f}x
                </div>
            </div>
        </div>
        """

    return f"""
    <div style="background:{cfg['bg']}; border:2px solid {cfg['border']}; border-radius:12px; padding:20px; margin-bottom:20px;">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
            <div style="display:flex; align-items:center; gap:10px;">
                <span style="font-size:1.6rem;">{cfg['icon']}</span>
                <div>
                    <div style="font-size:0.75rem; text-transform:uppercase; color:#94A3B8; letter-spacing:0.05em; font-weight:600;">AI Decision Intelligence Verdict</div>
                    <div style="font-size:1.6rem; font-weight:800; color:{cfg['badge']}; line-height:1.1;">{verdict_label}</div>
                </div>
            </div>
            <div style="text-align:right;">
                <div style="font-size:0.75rem; text-transform:uppercase; color:#94A3B8; font-weight:600;">Composite Score</div>
                <div style="font-size:2rem; font-weight:800; color:#FFFFFF; line-height:1.1;">{score:.3f} <span style="font-size:0.9rem; color:#64748B;">/ 1.0</span></div>
            </div>
        </div>

        <div style="margin: 12px 0 6px 0; display:flex; justify-content:space-between; align-items:center;">
            <span style="font-size:0.8rem; color:#CBD5E1; font-weight:600;">
                Monte Carlo Stability: <b style="color:{conf_color};">{conf_pct:.1f}%</b> ({conf_level})
            </span>
            <span style="font-size:0.75rem; color:#64748B;">50 Perturbations (σ=15%)</span>
        </div>
        <div style="background:#1E293B; height:8px; border-radius:4px; overflow:hidden;">
            <div style="background:{conf_color}; width:{min(100.0, max(0.0, conf_pct))}%; height:100%; border-radius:4px;"></div>
        </div>

        {delta_html}

        <div style="background:#0F172A; border-left:3px solid {cfg['border']}; border-radius:6px; padding:12px 14px; margin-top:14px;">
            <div style="font-size:0.75rem; font-weight:700; color:#38BDF8; margin-bottom:4px; text-transform:uppercase;">Analytical Justification</div>
            <div style="font-size:0.88rem; color:#E2E8F0; line-height:1.5;">{explanation}</div>
        </div>
    </div>
    """


def build_waterfall_chart(
    sm: Any,
    score: float,
    weights: dict[str, float],
) -> go.Figure:
    """Build a waterfall chart breaking down the multi-criteria contributions."""
    def _sig(x: float) -> float:
        return 1.0 / (1.0 + math.exp(-3.0 * x))

    NORM = {
        "congestion_ratio": 1.0,
        "speed_kmh": 10.0,
        "bus_delay_s": 120.0,
        "emissions_index": 1.0,
    }

    signed_deltas = {
        "congestion_ratio": -sm.delta_congestion / NORM["congestion_ratio"],
        "speed_kmh": sm.delta_speed / NORM["speed_kmh"],
        "bus_delay_s": -sm.delta_bus_delay / NORM["bus_delay_s"],
        "emissions_index": -sm.delta_emissions / NORM["emissions_index"],
    }

    w_cong = weights.get("congestion_ratio", 0.35)
    w_spd = weights.get("speed_kmh", 0.30)
    w_bus = weights.get("bus_delay_s", 0.20)
    w_emis = weights.get("emissions_index", 0.15)

    c_cong = w_cong * (_sig(signed_deltas["congestion_ratio"]) - 0.5)
    c_spd = w_spd * (_sig(signed_deltas["speed_kmh"]) - 0.5)
    c_bus = w_bus * (_sig(signed_deltas["bus_delay_s"]) - 0.5)
    c_emis = w_emis * (_sig(signed_deltas["emissions_index"]) - 0.5)

    raw_score = 0.5 + c_cong + c_spd + c_bus + c_emis
    c_feas = raw_score * (sm.feasibility - 1.0)

    x = ["Neutral Base", "Congestion Relief", "Speed Boost", "Transit Delay", "Emissions", "Feasibility", "Verdict Score"]
    y = [0.50, c_cong, c_spd, c_bus, c_emis, c_feas, 0]
    measure = ["relative", "relative", "relative", "relative", "relative", "relative", "total"]

    fig = go.Figure(
        go.Waterfall(
            name="MCDA Breakdown",
            orientation="v",
            measure=measure,
            x=x,
            textposition="outside",
            text=[f"{v:+.3f}" if m == "relative" else f"{score:.3f}" for v, m in zip(y, measure)],
            y=y,
            connector={"line": {"color": "#334155"}},
            decreasing={"marker": {"color": "#EF4444"}},
            increasing={"marker": {"color": "#10B981"}},
            totals={"marker": {"color": "#00E5FF"}},
        )
    )

    fig.update_layout(
        paper_bgcolor="#0F172A",
        plot_bgcolor="#0F172A",
        font=dict(color="#E2E8F0", family="Inter"),
        margin=dict(l=20, r=20, t=30, b=20),
        height=320,
        yaxis=dict(
            title="Score Contribution",
            gridcolor="#1E293B",
            zeroline=True,
            zerolinecolor="#334155",
            color="#94A3B8",
            range=[0.0, 1.05],
        ),
        xaxis=dict(color="#94A3B8"),
        showlegend=False,
    )
    return fig


def build_comparison_matrix(scenarios_data: list[dict[str, Any]]) -> pd.DataFrame:
    """Format a dataframe comparing metrics across multiple scenarios."""
    rows = []
    for s in scenarios_data:
        rows.append({
            "Scenario": s["name"],
            "Verdict": s.get("verdict", "-"),
            "Score": f"{s.get('score', 0.0):.3f}",
            "Avg Speed (km/h)": f"{s.get('speed', 0.0):.1f}",
            "Speed Δ": f"{s.get('delta_speed', 0.0):+.1f}",
            "Congestion (x)": f"{s.get('congestion', 0.0):.2f}x",
            "Congestion Δ": f"{s.get('delta_congestion', 0.0):+.2f}x",
            "Travel Time (min)": f"{s.get('travel_time_min', 0.0):.1f}",
            "Travel Time Δ": f"{s.get('delta_tt_min', 0.0):+.1f}",
            "Cost Index": f"{s.get('cost_index', 0.0):.0%}",
            "Feasibility": f"{s.get('feasibility', 1.0):.0%}",
        })
    return pd.DataFrame(rows)


def build_comparison_bar_chart(
    scenarios_data: list[dict[str, Any]],
    metric: str = "speed",
    title: str = "Average Speed (km/h)",
) -> go.Figure:
    """Bar chart comparing a key metric across candidate scenarios."""
    names = [s["name"] for s in scenarios_data]
    vals = [s.get(metric, 0.0) for s in scenarios_data]
    verdicts = [s.get("verdict", "") for s in scenarios_data]

    colors = []
    for v in verdicts:
        if v == "RECOMMENDED":
            colors.append("#10B981")
        elif v == "MODERATE":
            colors.append("#F59E0B")
        elif v == "NOT RECOMMENDED":
            colors.append("#EF4444")
        else:
            colors.append("#38BDF8")

    fig = go.Figure(
        go.Bar(
            x=names,
            y=vals,
            marker_color=colors,
            text=[f"{v:.1f}" for v in vals],
            textposition="auto",
        )
    )
    fig.update_layout(
        title=dict(text=title, font=dict(color="#F1F5F9", size=14)),
        paper_bgcolor="#0F172A",
        plot_bgcolor="#0F172A",
        font=dict(color="#E2E8F0", family="Inter"),
        margin=dict(l=20, r=20, t=40, b=30),
        height=280,
        yaxis=dict(gridcolor="#1E293B", color="#94A3B8"),
        xaxis=dict(color="#94A3B8"),
    )
    return fig


def build_ai_suggest_card_html(rank: int, s: Any) -> str:
    """Build a styled card for an AI Suggestion."""
    colors = {
        "RECOMMENDED": {"bg": "rgba(16, 185, 129, 0.12)", "border": "#10B981", "badge": "#10B981"},
        "MODERATE": {"bg": "rgba(245, 158, 11, 0.12)", "border": "#F59E0B", "badge": "#F59E0B"},
        "NOT RECOMMENDED": {"bg": "rgba(239, 68, 68, 0.12)", "border": "#EF4444", "badge": "#EF4444"},
    }
    cfg = colors.get(s.verdict_label, colors["MODERATE"])
    rank_colors = {1: "#FFD700", 2: "#C0C0C0", 3: "#CD7F32"}
    r_col = rank_colors.get(rank, "#38BDF8")

    return f"""
    <div style="background:{cfg['bg']}; border:1px solid {cfg['border']}; border-radius:10px; padding:16px; margin-bottom:16px;">
        <div style="display:flex; justify-content:space-between; align-items:flex-start;">
            <div style="display:flex; align-items:center; gap:10px;">
                <span style="background:{r_col}; color:#0B0F19; font-weight:800; font-size:0.85rem; padding:3px 10px; border-radius:6px;">
                    RANK #{rank}
                </span>
                <div>
                    <div style="font-size:1.15rem; font-weight:700; color:#FFFFFF;">{s.name}</div>
                    <div style="font-size:0.75rem; color:#94A3B8;">Candidate Strategy</div>
                </div>
            </div>
            <div style="text-align:right;">
                <span style="display:inline-block; padding:3px 10px; border-radius:9999px; font-size:0.75rem; font-weight:700; background:{cfg['border']}; color:#FFFFFF;">
                    {s.verdict_label}
                </span>
                <div style="font-size:0.8rem; color:#94A3B8; margin-top:4px;">
                    TOPSIS: <b style="color:#00E5FF;">{s.topsis_score:.4f}</b> | Score: <b>{s.composite_score:.3f}</b>
                </div>
            </div>
        </div>
        <div style="margin-top:12px; background:#0F172A; border-radius:6px; padding:10px 14px; font-size:0.85rem; color:#E2E8F0; line-height:1.4;">
            {s.explanation}
        </div>
        <div style="display:flex; gap:16px; margin-top:10px; font-size:0.75rem; color:#94A3B8;">
            <span>Cost Index: <b style="color:#F1F5F9;">{s.cost_index:.0%}</b></span>
            <span>Feasibility: <b style="color:#F1F5F9;">{s.feasibility:.0%}</b></span>
        </div>
    </div>
    """


def build_trend_prediction_chart(
    predictor: Any,
    highway_class: str = "primary",
) -> go.Figure:
    """Build a diurnal congestion ratio forecast across time slots."""
    slots = ["night_offpeak", "morning_peak", "midday", "evening_peak"]
    slot_labels = ["Night Off-Peak\n(23:00)", "Morning Peak\n(08:00)", "Midday Flow\n(14:00)", "Evening Peak\n(18:30)"]
    preds = [predictor.predict(s, highway_class) for s in slots]

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=slot_labels,
            y=preds,
            mode="lines+markers",
            line=dict(color="#00E5FF", width=3.5),
            marker=dict(size=10, color="#38BDF8", symbol="diamond"),
            name=f"Predicted ({highway_class})",
        )
    )

    fig.update_layout(
        title=dict(text=f"Predicted Diurnal Congestion Ratio — {highway_class.upper()}", font=dict(color="#F1F5F9", size=14)),
        paper_bgcolor="#0F172A",
        plot_bgcolor="#0F172A",
        font=dict(color="#E2E8F0", family="Inter"),
        margin=dict(l=20, r=20, t=40, b=30),
        height=300,
        yaxis=dict(title="Congestion Ratio (x)", gridcolor="#1E293B", color="#94A3B8"),
        xaxis=dict(color="#94A3B8"),
    )
    return fig


def build_anomaly_gauge(score: float, is_anomaly: bool) -> go.Figure:
    """Build an indicator gauge for simulation anomaly score."""
    color = "#EF4444" if is_anomaly else "#10B981"
    status_text = "ANOMALOUS OUTLIER" if is_anomaly else "NORMAL DISTRIBUTION"

    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=score,
            title={"text": f"Isolation Forest Anomaly Score<br><span style='font-size:0.8rem;color:{color}'>{status_text}</span>", "font": {"size": 14, "color": "#F1F5F9"}},
            gauge={
                "axis": {"range": [-0.5, 0.5], "tickcolor": "#94A3B8"},
                "bar": {"color": color},
                "steps": [
                    {"range": [-0.5, 0.0], "color": "rgba(239, 68, 68, 0.2)"},
                    {"range": [0.0, 0.5], "color": "rgba(16, 185, 129, 0.2)"},
                ],
                "threshold": {
                    "line": {"color": "#F59E0B", "width": 3},
                    "thickness": 0.75,
                    "value": 0.0,
                },
            },
        )
    )

    fig.update_layout(
        paper_bgcolor="#0F172A",
        plot_bgcolor="#0F172A",
        font=dict(color="#E2E8F0", family="Inter"),
        margin=dict(l=20, r=20, t=50, b=20),
        height=280,
    )
    return fig



# ── Stage B6: Transit & Metro ─────────────────────────────────────────────────
_ROUTE_PALETTE = ["#00E5FF", "#F59E0B", "#A855F7", "#10B981", "#EC4899", "#3B82F6", "#F97316", "#84CC16"]


def _dark_layout(fig: go.Figure, title: str | None = None, height: int = 320) -> go.Figure:
    """Apply the shared dark command-center chart layout."""
    fig.update_layout(
        title=dict(text=title, font=dict(color="#F1F5F9", size=14)) if title else None,
        paper_bgcolor="#0F172A",
        plot_bgcolor="#0F172A",
        font=dict(color="#E2E8F0", family="Inter"),
        margin=dict(l=20, r=20, t=40 if title else 10, b=30),
        height=height,
        yaxis=dict(gridcolor="#1E293B", color="#94A3B8"),
        xaxis=dict(gridcolor="#1E293B", color="#94A3B8"),
        legend=dict(font=dict(color="#94A3B8", size=11)),
    )
    return fig


def build_transit_map(
    net: NetworkBundle,
    route_metrics: pd.DataFrame | None = None,
    interchanges: pd.DataFrame | None = None,
    scenario_graph: Any = None,
) -> go.Figure:
    """
    Offline map of bus routes over the road network plus metro stations.
    Route edges removed in the scenario graph are drawn dashed red.
    """
    theme = get_offline_map_theme()
    fig = go.Figure()
    edges_idx = net.edges.set_index("edge_id")

    # Background road network (muted)
    xs: list[Any] = []
    ys: list[Any] = []
    for _, e in net.edges.iterrows():
        xs += [e["lon_u"], e["lon_v"], None]
        ys += [e["lat_u"], e["lat_v"], None]
    fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines", line=dict(color="#334155", width=1.5),
                             hoverinfo="skip", name="Road network"))

    live: set[int] | None = None
    if scenario_graph is not None:
        live = {int(d["edge_id"]) for _, _, d in scenario_graph.edges(data=True) if d.get("edge_id") is not None}

    delay_map: dict[str, float] = {}
    if route_metrics is not None and not route_metrics.empty:
        delay_map = dict(zip(route_metrics["route_id"], route_metrics["delay_min"]))

    cut_x: list[Any] = []
    cut_y: list[Any] = []
    for i, rid in enumerate(net.bus_route_edges["route_id"].drop_duplicates().tolist() if not net.bus_route_edges.empty else []):
        seq = net.bus_route_edges[net.bus_route_edges["route_id"] == rid].sort_values("seq")
        rx: list[Any] = []
        ry: list[Any] = []
        for eid in seq["edge_id"].astype(int):
            if eid not in edges_idx.index:
                continue
            e = edges_idx.loc[eid]
            target_x, target_y = (cut_x, cut_y) if (live is not None and eid not in live) else (rx, ry)
            target_x += [e["lon_u"], e["lon_v"], None]
            target_y += [e["lat_u"], e["lat_v"], None]
        d = delay_map.get(rid)
        label = f"Route {rid}" + (f" (+{d:.1f} min)" if d is not None else "")
        fig.add_trace(go.Scatter(x=rx, y=ry, mode="lines", line=dict(color=_ROUTE_PALETTE[i % len(_ROUTE_PALETTE)], width=4),
                                 name=label, hoverinfo="name"))

    if cut_x:
        fig.add_trace(go.Scatter(x=cut_x, y=cut_y, mode="lines", line=dict(color="#FF1744", width=4, dash="dash"),
                                 name="Disrupted by scenario", hoverinfo="name"))

    ms = net.metro_stations
    if ms is not None and not ms.empty:
        hover = []
        for _, s in ms.iterrows():
            txt = f"<b>{s['name']}</b><br>Line: {s.get('line', 'n/a')}"
            if interchanges is not None and not interchanges.empty:
                row = interchanges[interchanges["station"] == s["name"]]
                if not row.empty:
                    r = row.iloc[0]
                    txt += f"<br>Nearest junction: {r['nearest_junction']} ({r['distance_m']:.0f} m)"
                    txt += f"<br>Bus routes in walk radius: {r['bus_routes_within_radius'] or 'none'}"
            hover.append(txt)
        fig.add_trace(go.Scatter(x=ms["lon"], y=ms["lat"], mode="markers+text", text=ms["name"],
                                 textposition="top center", textfont=dict(color="#FDE047", size=10),
                                 marker=dict(size=13, color="#FDE047", symbol="square", line=dict(color="#0B0F19", width=2)),
                                 hoverinfo="text", hovertext=hover, name="Namma Metro station"))

    fig.update_layout(
        paper_bgcolor=theme["paper_bgcolor"], plot_bgcolor=theme["plot_bgcolor"],
        margin=dict(l=10, r=10, t=10, b=10), height=520,
        xaxis=dict(title="Longitude", gridcolor=theme["grid_color"], zeroline=False, color="#64748B"),
        yaxis=dict(title="Latitude", gridcolor=theme["grid_color"], zeroline=False, color="#64748B",
                   scaleanchor="x", scaleratio=1.0),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(color="#94A3B8", size=11)),
    )
    return fig


def build_route_delay_chart(route_cmp: pd.DataFrame) -> go.Figure:
    """Grouped bar chart of bus running time: baseline vs scenario, per route."""
    fig = go.Figure()
    if route_cmp is not None and not route_cmp.empty:
        fig.add_trace(go.Bar(x=route_cmp["route_id"], y=route_cmp["sim_running_time_min_base"],
                             name="Baseline", marker_color="#3B82F6"))
        fig.add_trace(go.Bar(x=route_cmp["route_id"], y=route_cmp["sim_running_time_min_scen"],
                             name="Scenario", marker_color="#F59E0B"))
        fig.update_layout(barmode="group")
    _dark_layout(fig, "Bus Running Time per Route (min) — Lower is Better")
    fig.update_yaxes(title="minutes")
    return fig


# ── Stage B7: Validation Harness ──────────────────────────────────────────────
_SLOT_COLORS = {"night_offpeak": "#818CF8", "morning_peak": "#F59E0B", "midday": "#10B981", "evening_peak": "#EC4899"}


def build_validation_scatter(
    df: pd.DataFrame,
    obs_col: str = "observed_speed_kmh",
    pred_col: str = "simulated_speed_kmh",
    color_col: str = "time_slot",
    title: str = "Simulated vs Reference Edge Speed (km/h)",
    reference_label: str = "reference",
) -> go.Figure:
    """Observed-vs-predicted scatter with a y = x parity line."""
    fig = go.Figure()
    if df is not None and not df.empty:
        for key, g in df.groupby(color_col):
            fig.add_trace(go.Scatter(
                x=g[obs_col], y=g[pred_col], mode="markers", name=str(key),
                marker=dict(size=9, color=_SLOT_COLORS.get(str(key), "#38BDF8"), opacity=0.85,
                            line=dict(color="#0B0F19", width=1)),
                hovertemplate=f"{reference_label}: %{{x:.2f}}<br>model: %{{y:.2f}}<extra>{key}</extra>",
            ))
        lo = float(min(df[obs_col].min(), df[pred_col].min()))
        hi = float(max(df[obs_col].max(), df[pred_col].max()))
        fig.add_trace(go.Scatter(x=[lo, hi], y=[lo, hi], mode="lines", name="parity (y = x)",
                                 line=dict(color="#64748B", dash="dot")))
    _dark_layout(fig, title, height=380)
    fig.update_xaxes(title=reference_label)
    fig.update_yaxes(title="model")
    return fig


def build_error_by_group_chart(by_group: pd.DataFrame, key: str, title: str) -> go.Figure:
    """Bar chart of RMSE and MAE per group (slot or road class)."""
    fig = go.Figure()
    if by_group is not None and not by_group.empty:
        fig.add_trace(go.Bar(x=by_group[key], y=by_group["rmse"], name="RMSE", marker_color="#EF4444"))
        fig.add_trace(go.Bar(x=by_group[key], y=by_group["mae"], name="MAE", marker_color="#F59E0B"))
        fig.update_layout(barmode="group")
    _dark_layout(fig, title, height=320)
    return fig
