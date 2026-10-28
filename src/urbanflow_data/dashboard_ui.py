"""
dashboard_ui.py - Reusable UI components, chart builders, and dark command-center theme.
"""
from __future__ import annotations

import logging
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
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;700&display=swap');

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
    if ratio < 0.5:
        # Red to Yellow
        f = ratio * 2.0
        r = 245
        g = int(50 + 170 * f)
        b = 50
    else:
        # Yellow to Green
        f = (ratio - 0.5) * 2.0
        r = int(245 - 210 * f)
        g = int(220 + 20 * f)
        b = 60
    return f"rgb({r},{g},{b})"


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
            hover_txt += "<br><span style='color:#FF1744'><b>⚠️ BOTTLENECK</b></span>"

        fig.add_trace(
            go.Scatter(
                x=[lon_u, lon_v, None],
                y=[lat_u, lat_v, None],
                mode="lines",
                line=dict(color=line_color, width=line_width),
                hoverinfo="text",
                hovertext=hover_txt,
                showlegend=False,
            )
        )

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
            f"Signalised: {'Yes 🚦' if is_sig else 'No'}"
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

    # Layout styling: offline command-center viewport
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
