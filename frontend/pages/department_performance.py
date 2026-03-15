import streamlit as st
import pandas as pd
import numpy as np
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from utils.data_generator import get_department_summary, get_dept_monthly_trend, get_revisit_trend
from utils.charts import COLORS, DEPT_COLORS, apply_layout
import plotly.express as px
import plotly.graph_objects as go

def render():
    # ── Page Header ───────────────────────────────────────────────────────────
    st.markdown("""
    <div class="page-header" style="
        background: linear-gradient(135deg, #101A30 0%, #0A1220 100%);
        border-color: #1A3055;">
      <div class="page-header-icon">🏢</div>
      <div>
        <div class="page-header-title">Department Performance & Efficiency Intelligence</div>
        <div class="page-header-desc">
          Benchmark departments · Track revisit rates · Identify bottlenecks · Drive operational improvements
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    dept_df  = get_department_summary()
    trend_df = get_dept_monthly_trend()
    rev_df   = get_revisit_trend()

    # ── Filters ───────────────────────────────────────────────────────────────
    col_f1, col_f2, _ = st.columns([1, 1, 2])
    metric_view = col_f1.selectbox("Primary Metric", ["Throughput", "Encounter Duration", "Revisit Rate", "Efficiency Score"])
    dept_select = col_f2.multiselect("Departments", dept_df["department"].tolist(), default=dept_df["department"].tolist()[:5])

    if not dept_select:
        dept_select = dept_df["department"].tolist()

    # ── KPI Row ───────────────────────────────────────────────────────────────
    st.markdown("<br>", unsafe_allow_html=True)
    k1, k2, k3, k4 = st.columns(4)

    def kpi(col, icon, val, label, sub, color):
        col.markdown(f"""
        <div class="metric-card" style="--accent: {color};">
          <div style="font-size:1.5rem;">{icon}</div>
          <div class="metric-value" style="color:{color};">{val}</div>
          <div class="metric-label">{label}</div>
          <div style="font-size:0.75rem; color:{COLORS['muted']}; margin-top:4px;">{sub}</div>
        </div>
        """, unsafe_allow_html=True)

    top_dept = dept_df.iloc[0]
    worst_dept = dept_df.iloc[-1]
    avg_rev  = dept_df["revisit_rate_pct"].mean()
    avg_dur  = dept_df["avg_encounter_min"].mean()

    kpi(k1, "🏆", top_dept["department"], "Top Performing Dept", f"Score: {top_dept['efficiency_score']:.1f}", COLORS["green"])
    kpi(k2, "⏱️", f"{avg_dur:.0f} min", "Avg Encounter Duration", "Across all departments", COLORS["cyan"])
    kpi(k3, "🔄", f"{avg_rev:.1f}%", "Avg Revisit Rate", "Hospital-wide benchmark", COLORS["amber"])
    kpi(k4, "📈", f"{dept_df['throughput_per_day'].sum():,}", "Total Daily Capacity", "Patients/day all depts", COLORS["purple"] if len(DEPT_COLORS) > 5 else "#9B6DFF")

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Row 1: Ranking + Radar ─────────────────────────────────────────────────
    col_l, col_r = st.columns([1.4, 1])

    with col_l:
        st.markdown('<div class="section-title">Department Productivity Ranking</div>', unsafe_allow_html=True)
        st.markdown('<div class="section-sub">Composite efficiency score (0–100) · Size = daily throughput · Color intensity = satisfaction score</div>', unsafe_allow_html=True)

        disp = dept_df[dept_df["department"].isin(dept_select)].copy()
        disp["rank_label"] = disp["rank"].apply(lambda r: f"#{r}")

        fig = px.bar(
            disp.sort_values("efficiency_score"),
            x="efficiency_score", y="department",
            orientation="h",
            color="revisit_rate_pct",
            color_continuous_scale=[[0, "#00E5A0"], [0.5, "#FFB547"], [1, "#FF4D6A"]],
            text="efficiency_score",
            labels={
                "efficiency_score": "Efficiency Score (0-100)",
                "department": "",
                "revisit_rate_pct": "Revisit Rate %",
            },
        )
        fig.update_traces(
            texttemplate="%{text:.1f}",
            textposition="outside",
            textfont=dict(color=COLORS["text"], size=11),
        )
        apply_layout(fig, height=420)
        fig.update_layout(
            xaxis_title="Composite Efficiency Score (higher = better)",
            coloraxis_colorbar=dict(
                title=dict(text="Revisit Rate %", font=dict(color=COLORS["muted"])),
                tickfont=dict(color=COLORS["muted"]),
            )
        )
        # Benchmark line at 70
        fig.add_vline(x=70, line_dash="dot", line_color=COLORS["amber"],
                      annotation_text="Benchmark (70)", annotation_font_color=COLORS["amber"])
        st.plotly_chart(fig, width="stretch")

    with col_r:
        st.markdown('<div class="section-title">Performance Multi-Axis Comparison</div>', unsafe_allow_html=True)
        st.markdown('<div class="section-sub">Radar chart comparing throughput, duration efficiency, revisit rate, and satisfaction across selected departments</div>', unsafe_allow_html=True)

        radardf = disp.head(6)
        categories = ["Throughput\nScore", "Duration\nEfficiency", "Low Revisit\nRate", "Patient\nSatisfaction", "Efficiency\nScore"]

        def normalize(series):
            return ((series - series.min()) / (series.max() - series.min() + 1e-6) * 100).round(1)

        radardf = radardf.copy()
        radardf["tp_score"]   = normalize(radardf["throughput_per_day"])
        radardf["dur_eff"]    = normalize(1 / radardf["avg_encounter_min"])
        radardf["low_rev"]    = normalize(1 / radardf["revisit_rate_pct"])
        radardf["sat_score"]  = normalize(radardf["patient_satisfaction"])
        radardf["eff_score"]  = normalize(radardf["efficiency_score"])

        fig_r = go.Figure()
        for i, (_, row) in enumerate(radardf.iterrows()):
            vals = [row["tp_score"], row["dur_eff"], row["low_rev"], row["sat_score"], row["eff_score"]]
            vals += [vals[0]]  # close polygon
            fig_r.add_trace(go.Scatterpolar(
                r=vals,
                theta=categories + [categories[0]],
                name=row["department"],
                line=dict(color=DEPT_COLORS[i % len(DEPT_COLORS)], width=2),
                fill="toself",
                fillcolor="rgba(0,100,200,0.07)",
            ))
        apply_layout(fig_r, height=420)
        fig_r.update_layout(
            polar=dict(
                radialaxis=dict(visible=True, range=[0, 100],
                               tickfont=dict(color=COLORS["muted"], size=9),
                               gridcolor="#1A2D45", linecolor="#1A2D45"),
                angularaxis=dict(tickfont=dict(color=COLORS["text"], size=10),
                                 gridcolor="#1A2D45", linecolor="#1A2D45"),
                bgcolor=COLORS["bg"],
            ),
        )
        st.plotly_chart(fig_r, width="stretch")

    # ── Row 2: Monthly trend + Revisit heatmap ─────────────────────────────────
    st.markdown("<br>", unsafe_allow_html=True)
    col_tl, col_tr = st.columns(2)

    with col_tl:
        st.markdown('<div class="section-title">Monthly Throughput Trend</div>', unsafe_allow_html=True)
        st.markdown('<div class="section-sub">Patient volume processed each month — 12-month view per department</div>', unsafe_allow_html=True)

        t_filtered = trend_df[trend_df["department"].isin(dept_select[:6])]
        fig_t = px.line(
            t_filtered, x="month", y="throughput", color="department",
            color_discrete_sequence=DEPT_COLORS,
            markers=True,
            labels={"month": "Month", "throughput": "Monthly Throughput (patients)", "department": "Department"},
        )
        apply_layout(fig_t, height=360)
        fig_t.update_traces(line_width=2, marker_size=5)
        fig_t.update_layout(xaxis_title="Month", yaxis_title="Monthly Throughput (patients/month)")
        st.plotly_chart(fig_t, width="stretch")

    with col_tr:
        st.markdown('<div class="section-title">Revisit Rate Heatmap (26 Weeks)</div>', unsafe_allow_html=True)
        st.markdown('<div class="section-sub">Weekly revisit frequency per department — darker = higher repeat visits (potential care gap)</div>', unsafe_allow_html=True)

        pivot = rev_df[rev_df["department"].isin(dept_select)].pivot(
            index="department", columns="week", values="revisit_rate"
        )
        # Only show last 12 weeks for readability
        pivot = pivot.iloc[:, -12:]
        pivot.columns = [str(c.date()) for c in pivot.columns]

        fig_h = go.Figure(go.Heatmap(
            z=pivot.values,
            x=pivot.columns,
            y=pivot.index,
            colorscale=[[0, "#0A1628"], [0.4, "#0066FF"], [0.7, "#FFB547"], [1, "#FF4D6A"]],
            showscale=True,
            colorbar=dict(
                title=dict(text="Revisit %", font=dict(color=COLORS["muted"])),
                tickfont=dict(color=COLORS["muted"]),
            ),
            hovertemplate="Dept: %{y}<br>Week: %{x}<br>Revisit Rate: %{z:.1f}%<extra></extra>",
        ))
        apply_layout(fig_h, height=360)
        fig_h.update_layout(
            xaxis=dict(title="Week (last 12 weeks)", tickangle=-45, tickfont=dict(size=9, color=COLORS["muted"])),
            yaxis=dict(title="Department"),
        )
        st.plotly_chart(fig_h, width="stretch")

    # ── Row 3: Encounter Duration + Alerts ────────────────────────────────────
    st.markdown("<br>", unsafe_allow_html=True)
    col_bl, col_br = st.columns([1.2, 1])

    with col_bl:
        st.markdown('<div class="section-title">Avg Encounter Duration by Department</div>', unsafe_allow_html=True)
        st.markdown('<div class="section-sub">Time per patient encounter (minutes) · Dashed line = hospital benchmark (35 min)</div>', unsafe_allow_html=True)

        dur_df = dept_df[dept_df["department"].isin(dept_select)].sort_values("avg_encounter_min", ascending=False)
        colors_dur = [COLORS["red"] if v > 45 else COLORS["amber"] if v > 35 else COLORS["green"]
                      for v in dur_df["avg_encounter_min"]]

        fig_d = go.Figure(go.Bar(
            x=dur_df["department"],
            y=dur_df["avg_encounter_min"],
            marker_color=colors_dur,
            marker_line_width=0,
            text=dur_df["avg_encounter_min"],
            texttemplate="%{text} min",
            textposition="outside",
            textfont=dict(color=COLORS["text"], size=10),
            hovertemplate="<b>%{x}</b><br>Avg Duration: %{y} min<extra></extra>",
        ))
        apply_layout(fig_d, height=340)
        fig_d.add_hline(y=35, line_dash="dot", line_color=COLORS["amber"],
                        annotation_text="Benchmark: 35 min", annotation_font_color=COLORS["amber"])
        fig_d.update_layout(
            xaxis_title="Department",
            yaxis_title="Avg Encounter Duration (minutes)",
            showlegend=False,
        )
        st.plotly_chart(fig_d, width="stretch")

    with col_br:
        st.markdown('<div class="section-title">🔔 Department Alerts</div>', unsafe_allow_html=True)
        st.markdown('<div class="section-sub">AI-detected performance anomalies and highlights</div>', unsafe_allow_html=True)

        high_rev = dept_df[dept_df["revisit_rate_pct"] > dept_df["revisit_rate_pct"].mean() * 1.2]
        fast_dept = dept_df[dept_df["avg_encounter_min"] < dept_df["avg_encounter_min"].mean() * 0.85]
        slow_dept = dept_df[dept_df["avg_encounter_min"] > dept_df["avg_encounter_min"].mean() * 1.15]

        for _, row in high_rev.iterrows():
            diff = row["revisit_rate_pct"] - dept_df["revisit_rate_pct"].mean()
            st.markdown(f"""
            <div class="alert-card alert-warning">
              <span>⚠️</span>
              <span style="font-size:0.87rem; color:{COLORS['text']};">
                <b>{row['department']}</b> has <b style="color:{COLORS['amber']}">{diff:+.1f}%</b> higher revisit 
                rate than hospital average ({row['revisit_rate_pct']:.1f}%).
              </span>
            </div>
            """, unsafe_allow_html=True)

        for _, row in fast_dept.iterrows():
            st.markdown(f"""
            <div class="alert-card alert-success">
              <span>✅</span>
              <span style="font-size:0.87rem; color:{COLORS['text']};">
                <b>{row['department']}</b> resolving cases <b style="color:{COLORS['green']}">
                {((dept_df['avg_encounter_min'].mean() - row['avg_encounter_min'])/dept_df['avg_encounter_min'].mean()*100):.0f}%
                </b> faster than benchmark.
              </span>
            </div>
            """, unsafe_allow_html=True)

        for _, row in slow_dept.head(2).iterrows():
            st.markdown(f"""
            <div class="alert-card alert-critical">
              <span>🚨</span>
              <span style="font-size:0.87rem; color:{COLORS['text']};">
                <b>{row['department']}</b> encounter duration ({row['avg_encounter_min']} min) 
                exceeds benchmark by <b style="color:{COLORS['red']}">
                {row['avg_encounter_min'] - 35:+.0f} min</b>.
              </span>
            </div>
            """, unsafe_allow_html=True)

        st.markdown(f"""
        <div class="alert-card alert-info">
          <span>ℹ️</span>
          <span style="font-size:0.87rem; color:{COLORS['text']};">
            Top performing dept: <b>{dept_df.iloc[0]['department']}</b> with efficiency score 
            <b style="color:{COLORS['cyan']}">{dept_df.iloc[0]['efficiency_score']:.1f}/100</b>.
          </span>
        </div>
        """, unsafe_allow_html=True)