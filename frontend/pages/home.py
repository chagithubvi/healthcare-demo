import streamlit as st
import pandas as pd
import numpy as np
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from utils.data_generator import (
    get_home_kpis, get_doctor_encounters, get_department_summary, get_supply_consumption
)
from utils.charts import COLORS, DEPT_COLORS, apply_layout
import plotly.express as px
import plotly.graph_objects as go

def render():
    kpis = get_home_kpis()

    # ── Page Header ───────────────────────────────────────────────────────────
    st.markdown("""
    <div class="page-header">
      <div class="page-header-icon">🏥</div>
      <div>
        <div class="page-header-title">HealthIntel Command Center</div>
        <div class="page-header-desc">
          Real-time intelligence across 10,000 patients · 10 departments · Synthea Dataset
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Top KPI Row ───────────────────────────────────────────────────────────
    c1, c2, c3, c4, c5 = st.columns(5)

    def kpi_card(col, icon, value, label, delta, delta_type="up"):
        arrow = "▲" if delta_type == "up" else "▼"
        color = "#00E5A0" if delta_type == "up" else "#FF4D6A"
        col.markdown(f"""
        <div class="metric-card" style="--accent: linear-gradient(90deg, {COLORS['cyan']}, {COLORS['blue']});">
          <div style="font-size:1.8rem; margin-bottom:8px;">{icon}</div>
          <div class="metric-value">{value}</div>
          <div class="metric-label">{label}</div>
          <div class="metric-delta" style="color:{color};">{arrow} {delta}</div>
        </div>
        """, unsafe_allow_html=True)

    kpi_card(c1, "👥", f"{kpis['total_patients']:,}", "Total Patients", "10K dataset loaded", "up")
    kpi_card(c2, "📋", kpis['active_encounters_today'], "Encounters Today", "+5.2% vs yesterday", "up")
    kpi_card(c3, "⚠️", kpis['overloaded_providers'], "Overloaded Providers", "Needs attention", "down")
    kpi_card(c4, "📦", kpis['supply_risk_items'], "Supply Risk Items", "< 7 days stock", "down")
    kpi_card(c5, "⭐", kpis['avg_satisfaction'], "Avg Satisfaction", "+0.3 this month", "up")

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Row 2: Dept Throughput + Provider Status Donut ────────────────────────
    col_left, col_right = st.columns([1.6, 1])

    with col_left:
        st.markdown('<div class="section-title">Department Patient Throughput</div>', unsafe_allow_html=True)
        st.markdown('<div class="section-sub">Daily patients processed per department — benchmarked against hospital average</div>', unsafe_allow_html=True)
        dept_df = get_department_summary()
        fig = px.bar(
            dept_df.sort_values("throughput_per_day"),
            x="throughput_per_day", y="department",
            orientation="h",
            color="efficiency_score",
            color_continuous_scale=[[0, "#0A1628"], [0.4, "#0066FF"], [1, "#00E5A0"]],
            text="throughput_per_day",
            labels={"throughput_per_day": "Patients/Day", "department": "", "efficiency_score": "Efficiency Score"},
        )
        fig.update_traces(textposition="outside", textfont=dict(color=COLORS["text"], size=11))
        apply_layout(fig, height=400)
        fig.update_layout(coloraxis_colorbar=dict(
            tickfont=dict(color=COLORS["muted"]),
            title=dict(text="Score", font=dict(color=COLORS["muted"])),
        ))
        st.plotly_chart(fig, use_container_width=True)

    with col_right:
        st.markdown('<div class="section-title">Provider Load Status</div>', unsafe_allow_html=True)
        st.markdown('<div class="section-sub">Distribution of provider workload across the hospital</div>', unsafe_allow_html=True)
        doc_df = get_doctor_encounters()
        status_counts = doc_df["status"].value_counts()
        colors_map = {"Overloaded": COLORS["red"], "Optimal": COLORS["green"], "Underutilized": COLORS["amber"]}
        fig2 = go.Figure(go.Pie(
            labels=status_counts.index,
            values=status_counts.values,
            hole=0.62,
            marker=dict(
                colors=[colors_map.get(s, COLORS["cyan"]) for s in status_counts.index],
                line=dict(color=COLORS["bg"], width=3),
            ),
            textfont=dict(color=COLORS["text"], size=12),
        ))
        apply_layout(fig2, height=260, showlegend=True)
        fig2.add_annotation(
            text=f"<b>{len(doc_df)}</b><br><span style='font-size:10px'>Providers</span>",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=18, color=COLORS["text"], family="Space Grotesk"),
        )
        st.plotly_chart(fig2, use_container_width=True)

        # Status legend cards
        for status, cnt in status_counts.items():
            color = colors_map.get(status, COLORS["cyan"])
            st.markdown(f"""
            <div style="background:rgba(255,255,255,0.03); border:1px solid {color}30;
                        border-left: 3px solid {color}; border-radius:8px;
                        padding:8px 14px; margin-bottom:6px; display:flex;
                        justify-content:space-between; align-items:center;">
              <span style="color:{COLORS['text']}; font-size:0.85rem;">{status}</span>
              <span style="color:{color}; font-weight:700; font-size:1rem;">{cnt}</span>
            </div>
            """, unsafe_allow_html=True)

    # ── Row 3: Alerts panel + Supply Risk ─────────────────────────────────────
    st.markdown("<br>", unsafe_allow_html=True)
    col_a, col_b = st.columns(2)

    with col_a:
        st.markdown('<div class="section-title">🔔 Live Alerts</div>', unsafe_allow_html=True)
        st.markdown('<div class="section-sub">AI-generated operational alerts requiring attention</div>', unsafe_allow_html=True)

        alerts = [
            ("critical", "🚨", "Dr. Adams handling 35% more cases than department average."),
            ("critical", "🚨", "Emergency department showing provider overload risk."),
            ("warning",  "⚠️", "Orthopedics has 22% higher revisit rate than average."),
            ("warning",  "⚠️", "Glove consumption increased 40% this week — spike detected."),
            ("info",     "ℹ️", "Cardiology resolving cases 15% faster than benchmark."),
            ("success",  "✅", "3 providers returned to optimal load this week."),
            ("info",     "ℹ️", "Syringe usage trending 18% above monthly average."),
        ]
        for atype, icon, msg in alerts:
            st.markdown(f"""
            <div class="alert-card alert-{atype}">
              <span style="font-size:1.1rem;">{icon}</span>
              <span style="font-size:0.87rem; color:{COLORS['text']};">{msg}</span>
            </div>
            """, unsafe_allow_html=True)

    with col_b:
        st.markdown('<div class="section-title">📦 Supply Stock Status</div>', unsafe_allow_html=True)
        st.markdown('<div class="section-sub">Days until stockout — items below 14 days need attention</div>', unsafe_allow_html=True)
        sup_df = get_supply_consumption().head(10)
        risk_colors = {"Critical": COLORS["red"], "Warning": COLORS["amber"], "Safe": COLORS["green"]}
        fig3 = px.bar(
            sup_df.sort_values("days_until_stockout"),
            x="days_until_stockout", y="supply",
            orientation="h",
            color="risk",
            color_discrete_map=risk_colors,
            text="days_until_stockout",
            labels={"days_until_stockout": "Days Until Stockout", "supply": "", "risk": "Risk Level"},
        )
        fig3.update_traces(texttemplate="%{text:.1f}d", textposition="outside",
                           textfont=dict(color=COLORS["text"], size=10))
        apply_layout(fig3, height=380)
        fig3.add_vline(x=7, line_dash="dot", line_color=COLORS["red"],
                       annotation_text="Critical (7d)", annotation_font_color=COLORS["red"])
        fig3.add_vline(x=14, line_dash="dot", line_color=COLORS["amber"],
                       annotation_text="Warning (14d)", annotation_font_color=COLORS["amber"])
        st.plotly_chart(fig3, use_container_width=True)
