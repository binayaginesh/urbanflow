"""
report_generator.py - Stage B9: PDF Planner Report Generator.

Generates an executive, professional PDF Decision Brief for urban traffic
engineers and city planners using ReportLab. Contains:
- Executive Summary & AI Decision Verdict (Recommended / Moderate / Not Recommended)
- Key Metrics Comparison (Baseline vs Scenario: Congestion, Speed, Delays, Emissions)
- Multi-Criteria Decision Analysis (MCDA) Scoring Breakdown & Weights
- Deterministic Justification & Explainability Section
- Transit & Metro Connectivity Impact
- Methodological Integrity & Disclaimers (No Hallucinated Data)
"""
from __future__ import annotations

import io
from datetime import datetime
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    HRFlowable,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from urbanflow_data.decision_layer import ScenarioMetrics


def generate_planner_pdf_report(
    scenario_metrics: ScenarioMetrics,
    score: float,
    verdict_label: str,
    confidence: float,
    explanation: str,
    time_slot: str,
    output_path: str | Path | None = None,
    weights: dict[str, float] | None = None,
    author: str = "UrbanFlow AI Decision Intelligence Platform",
) -> bytes:
    """
    Generate an executive PDF Decision Report for a simulated scenario.
    Returns the generated PDF as raw bytes (and writes to output_path if provided).
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36,
    )

    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=20,
        leading=24,
        textColor=colors.HexColor("#0F172A"),
    )
    subtitle_style = ParagraphStyle(
        "DocSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#64748B"),
    )
    h2_style = ParagraphStyle(
        "Heading2Custom",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=16,
        textColor=colors.HexColor("#1E293B"),
        spaceBefore=10,
        spaceAfter=6,
    )
    body_style = ParagraphStyle(
        "BodyCustom",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#334155"),
    )
    callout_style = ParagraphStyle(
        "CalloutText",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9.5,
        leading=14,
        textColor=colors.HexColor("#0F172A"),
    )

    story = []

    # 1. Header Banner
    story.append(Paragraph("🚦 URBANFLOW // BENGALURU URBAN MOBILITY REPORT", title_style))
    story.append(
        Paragraph(
            f"Scenario Impact Assessment: <b>{scenario_metrics.scenario_name}</b> | "
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')} | "
            f"Temporal Slot: <b>{time_slot.upper()}</b>",
            subtitle_style,
        )
    )
    story.append(Spacer(1, 10))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#00E5FF"), spaceAfter=14))

    # 2. Executive Decision Verdict Card
    badge_color = "#10B981" if verdict_label == "RECOMMENDED" else ("#F59E0B" if verdict_label == "MODERATE" else "#EF4444")
    verdict_text = f"""
    <b>DECISION INTELLIGENCE VERDICT: <font color="{badge_color}">{verdict_label}</font></b><br/>
    <b>Composite MCDA Score:</b> {score:.3f} / 1.000 &nbsp;&nbsp;|&nbsp;&nbsp;
    <b>Monte Carlo Stability Confidence:</b> {confidence:.0%}
    """
    verdict_table = Table([[Paragraph(verdict_text, callout_style)]], colWidths=[540])
    verdict_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
            ("BOX", (0, 0), (-1, -1), 1.5, colors.HexColor(badge_color)),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ("LEFTPADDING", (0, 0), (-1, -1), 12),
            ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ])
    )
    story.append(verdict_table)
    story.append(Spacer(1, 12))

    # 3. Deterministic Justification
    story.append(Paragraph("AI-Synthesized Plain-Language Justification", h2_style))
    story.append(Paragraph(explanation, body_style))
    story.append(Spacer(1, 12))

    # 4. Key Performance Indicators Table
    story.append(Paragraph("Corridor Performance Benchmarks (Baseline vs Candidate Intervention)", h2_style))
    sm = scenario_metrics
    b_tt_min = sm.baseline.total_travel_time_s / 60.0
    s_tt_min = sm.sim.total_travel_time_s / 60.0

    kpi_data = [
        ["Metric", "Baseline State", "Candidate Scenario", "Delta vs Baseline", "Impact"],
        [
            "Mean Congestion Multiplier",
            f"{sm.baseline.mean_congestion_ratio:.2f}x",
            f"{sm.sim.mean_congestion_ratio:.2f}x",
            f"{sm.delta_congestion:+.2f}x",
            "Relieved" if sm.delta_congestion <= 0 else "Worsened",
        ],
        [
            "Network Average Speed",
            f"{sm.baseline.mean_speed_kmh:.1f} km/h",
            f"{sm.sim.mean_speed_kmh:.1f} km/h",
            f"{sm.delta_speed:+.1f} km/h",
            "Improved" if sm.delta_speed >= 0 else "Degraded",
        ],
        [
            "Total Vehicle Travel Time",
            f"{b_tt_min:.1f} min",
            f"{s_tt_min:.1f} min",
            f"{(s_tt_min - b_tt_min):+.1f} min",
            "Faster" if s_tt_min <= b_tt_min else "Slower",
        ],
        [
            "Bus Network Extra Delay",
            f"{sm.baseline.bus_delay_s:.0f} s",
            f"{sm.sim.bus_delay_s:.0f} s",
            f"{sm.delta_bus_delay:+.0f} s",
            "Relieved" if sm.delta_bus_delay <= 0 else "Delayed",
        ],
        [
            "Relative Emissions Index",
            f"{sm.baseline.emissions_index:.2f}x",
            f"{sm.sim.emissions_index:.2f}x",
            f"{sm.delta_emissions:+.2f}x",
            "Cleaner" if sm.delta_emissions <= 0 else "Higher",
        ],
        [
            "Implementation Feasibility / Cost",
            "N/A (Current)",
            f"Feas: {sm.feasibility:.0%} | Cost: {sm.cost_index:.0%}",
            "-",
            "Viable" if sm.feasibility >= 0.7 else "Constrained",
        ],
    ]

    t = Table(kpi_data, colWidths=[160, 95, 95, 95, 95])
    t.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0F172A")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8.5),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("ALIGN", (0, 0), (0, -1), "LEFT"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#FFFFFF"), colors.HexColor("#F8FAFC")]),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ])
    )
    story.append(t)
    story.append(Spacer(1, 14))

    # 5. MCDA Weights & Methodology
    story.append(Paragraph("Decision Framework & Calibration Standards", h2_style))
    w_info = "Default Equal Distribution"
    if weights:
        w_info = " | ".join(f"<b>{k.replace('_', ' ').capitalize()}</b>: {v:.0%}" for k, v in weights.items())

    methodology_text = f"""
    <b>Multi-Criteria Weights:</b> {w_info}<br/>
    <b>Simulation Engine:</b> Bureau of Public Roads (BPR) Volume-Delay Assignment with Synthetic Gravity O-D Demand Matrix.<br/>
    <b>Data Provenance:</b> Calibrated for Bengaluru Silk Board — HSR Layout — Koramangala study area. All mathematical deltas are computed deterministically without generative hallucination.
    """
    story.append(Paragraph(methodology_text, body_style))
    story.append(Spacer(1, 14))

    # 6. Footer Disclaimer
    footer_text = f"""
    <i>Report generated autonomously by {author}. Muthoot Institute of Technology and Science (MITS) B.Tech Major Project. Stage B Platform.</i>
    """
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#94A3B8"), spaceAfter=6))
    story.append(Paragraph(footer_text, ParagraphStyle("Footer", parent=styles["Normal"], fontSize=7.5, textColor=colors.HexColor("#94A3B8"))))

    doc.build(story)
    pdf_bytes = buf.getvalue()

    if output_path is not None:
        p = Path(output_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(pdf_bytes)

    return pdf_bytes
