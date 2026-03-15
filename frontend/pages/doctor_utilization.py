import streamlit as st
import pandas as pd
import numpy as np
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from utils.data_generator import get_doctor_encounters, get_doctor_trend, get_dept_provider_distribution
from utils.charts import COLORS, DEPT_COLORS, STATUS_COLORS, apply_layout
import plotly.express as px
import plotly.graph_objects as go

def render():
    # ── Page Header ───────────────────────────────────────────────────────────
    st.markdown("""
    <div class="page-header" style="
        background: linear-gradient(135deg, #0D1F38 0%, #0A1220 100%);
        border-color: #1E3A58;">
      <div class="page-header-icon">👨‍⚕️</div>
      <div>
        <div class="page-header-title">Doctor Utilization & Workload Intelligence</div>
        <div class="page-header-desc">
          Identify overloaded vs underutilized providers · Prevent burnout · Optimize patient allocation
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    doc_df = get_doctor_encounters()
    trend_df = get_doctor_trend()
    dist_df = get_dept_provider_distribution()

    # ── Filters ───────────────────────────────────────────────────────────────
    col_f1, col_f2, _ = st.columns([1, 1, 2])
    dept_filter = col_f1.selectbox("Filter by Department", ["All Departments"] + list(doc_df["department"].unique()))
    status_filter = col_f2.selectbox("Filter by Status", ["All", "Overloaded", "Optimal", "Underutilized"])

    filtered = doc_df.copy()
    if dept_filter != "All Departments":
        filtered = filtered[filtered["department"] == dept_filter]
    if status_filter != "All":
        filtered = filtered[filtered["status"] == status_filter]

    # ── KPI Row ───────────────────────────────────────────────────────────────
    st.markdown("<br>", unsafe_allow_html=True)
    k1, k2, k3, k4 = st.columns(4)

    def kpi(col, icon, val, label, color=COLORS["cyan"]):
        col.markdown(f"""
        <div class="metric-card" style="--accent: {color};">
          <div style="font-size:1.6rem;">{icon}</div>
          <div class="metric-value" style="color:{color};">{val}</div>
          <div class="metric-label">{label}</div>
        </div>
        """, unsafe_allow_html=True)

    overloaded = (doc_df["status"] == "Overloaded").sum()
    underutil  = (doc_df["status"] == "Underutilized").sum()
    avg_load   = doc_df["avg_daily_patients"].mean()

    kpi(k1, "👩‍⚕️", len(doc_df), "Total Providers", COLORS["cyan"])
    kpi(k2, "🔴", overloaded,  "Overloaded Providers", COLORS["red"])
    kpi(k3, "🟡", underutil,   "Underutilized Providers", COLORS["amber"])
    kpi(k4, "📊", f"{avg_load:.1f}", "Avg Daily Patients", COLORS["green"])

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Row 1: Workload bar + status heatmap ─────────────────────────────────
    col_l, col_r = st.columns([1.5, 1])

    with col_l:
        st.markdown('<div class="section-title">Provider Workload vs Department Average</div>', unsafe_allow_html=True)
        st.markdown('<div class="section-sub">Average daily patients per provider — bars colored by workload status. Dashed line = department benchmark.</div>', unsafe_allow_html=True)

        disp = filtered.sort_values("pct_vs_avg", ascending=False)
        color_seq = [STATUS_COLORS.get(s, COLORS["cyan"]) for s in disp["status"]]

        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=disp["doctor"],
            y=disp["avg_daily_patients"],
            marker_color=color_seq,
            marker_line_width=0,
            text=[f"{v} pts<br>{p:+.0f}%" for v, p in zip(disp["avg_daily_patients"], disp["pct_vs_avg"])],
            textposition="outside",
            textfont=dict(color=COLORS["text"], size=10),
            hovertemplate="<b>%{x}</b><br>Avg Daily Patients: %{y}<br>vs Dept Avg: %{text}<extra></extra>",
        ))
        # Dept average reference line
        if dept_filter != "All Departments":
            avg = disp["dept_mean"].mean()
            fig.add_hline(y=avg, line_dash="dot", line_color=COLORS["amber"],
                          annotation_text=f"Dept Avg: {avg:.1f}",
                          annotation_font_color=COLORS["amber"])
        apply_layout(fig, height=420)
        fig.update_layout(
            xaxis_title="Provider",
            yaxis_title="Avg Daily Patients",
            showlegend=False,
        )
        st.plotly_chart(fig, use_container_width=True)

    with col_r:
        st.markdown('<div class="section-title">Provider Status Breakdown</div>', unsafe_allow_html=True)
        st.markdown('<div class="section-sub">Each provider\'s workload classification relative to their department benchmark</div>', unsafe_allow_html=True)

        for _, row in filtered.iterrows():
            color = STATUS_COLORS.get(row["status"], COLORS["cyan"])
            bar_pct = min(100, max(0, (row["avg_daily_patients"] / 40) * 100))
            st.markdown(f"""
            <div style="background:#0D1F38; border:1px solid #1E3558;
                        border-left:4px solid {color}; border-radius:10px;
                        padding:10px 14px; margin-bottom:7px;">
              <div style="display:flex; justify-content:space-between; align-items:center;">
                <div>
                  <div style="color:{COLORS['text']}; font-weight:600; font-size:0.88rem;">{row['doctor']}</div>
                  <div style="color:{COLORS['muted']}; font-size:0.75rem;">{row['department']}</div>
                </div>
                <div style="text-align:right;">
                  <div style="color:{color}; font-weight:700; font-size:1rem;">{row['avg_daily_patients']}</div>
                  <div style="color:{color}; font-size:0.72rem;">{row['status']}</div>
                </div>
              </div>
              <div style="background:#1A2D45; border-radius:4px; height:4px; margin-top:8px;">
                <div style="background:{color}; width:{bar_pct}%; height:4px; border-radius:4px;"></div>
              </div>
              <div style="display:flex; justify-content:space-between; margin-top:3px;">
                <span style="color:{COLORS['muted']}; font-size:0.68rem;">0</span>
                <span style="color:{color}; font-size:0.68rem;">{row['pct_vs_avg']:+.1f}% vs avg</span>
                <span style="color:{COLORS['muted']}; font-size:0.68rem;">40</span>
              </div>
            </div>
            """, unsafe_allow_html=True)

    # ── Row 2: Trend + Department distribution ────────────────────────────────
    st.markdown("<br>", unsafe_allow_html=True)
    col_tl, col_tr = st.columns(2)

    with col_tl:
        st.markdown('<div class="section-title">Workload Trend — Last 30 Days</div>', unsafe_allow_html=True)
        st.markdown('<div class="section-sub">Daily encounter count per provider. Use filter above to focus on a department.</div>', unsafe_allow_html=True)

        t_dept = dept_filter if dept_filter != "All Departments" else None
        if t_dept:
            t_df = trend_df[trend_df["department"] == t_dept]
        else:
            # Show top 5 busiest
            top5 = doc_df.nlargest(5, "avg_daily_patients")["doctor"].tolist()
            t_df = trend_df[trend_df["doctor"].isin(top5)]

        fig_t = px.line(
            t_df, x="date", y="encounters", color="doctor",
            color_discrete_sequence=DEPT_COLORS,
            markers=False,
            labels={"date": "Date", "encounters": "Daily Encounters", "doctor": "Provider"},
        )
        apply_layout(fig_t, height=360)
        fig_t.update_traces(line_width=2)
        fig_t.update_layout(xaxis_title="Date", yaxis_title="Daily Encounters (count)")
        st.plotly_chart(fig_t, use_container_width=True)

    with col_tr:
        st.markdown('<div class="section-title">Department Provider Distribution</div>', unsafe_allow_html=True)
        st.markdown('<div class="section-sub">Provider count vs average patient load — bubble size = overload risk</div>', unsafe_allow_html=True)

        fig_b = px.scatter(
            dist_df,
            x="provider_count",
            y="avg_load",
            size="max_load",
            color="department",
            color_discrete_sequence=DEPT_COLORS,
            hover_data=["overloaded", "underutilized"],
            text="department",
            labels={
                "provider_count": "Number of Providers",
                "avg_load": "Avg Daily Patients / Provider",
                "department": "Department",
                "max_load": "Max Load (bubble size)",
                "overloaded": "Overloaded Providers",
                "underutilized": "Underutilized Providers",
            },
        )
        fig_b.update_traces(textposition="top center", textfont=dict(color=COLORS["text"], size=9))
        apply_layout(fig_b, height=360, showlegend=False)
        fig_b.update_layout(
            xaxis_title="Number of Providers in Department",
            yaxis_title="Avg Daily Patients per Provider",
        )
        st.plotly_chart(fig_b, use_container_width=True)

    # ── Alerts ────────────────────────────────────────────────────────────────
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown('<div class="section-title">🔔 Workload Alerts</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-sub">AI-detected anomalies in provider workload distribution</div>', unsafe_allow_html=True)

    # Dynamic alerts from data
    overloaded_docs = doc_df[doc_df["status"] == "Overloaded"]
    underutil_docs  = doc_df[doc_df["status"] == "Underutilized"]

    ac1, ac2 = st.columns(2)
    with ac1:
        for _, row in overloaded_docs.iterrows():
            st.markdown(f"""
            <div class="alert-card alert-critical">
              <span>🚨</span>
              <span style="font-size:0.87rem; color:{COLORS['text']};">
                <b>{row['doctor']}</b> ({row['department']}) handling 
                <b style="color:{COLORS['red']}">{row['pct_vs_avg']:+.1f}%</b> more cases than department average.
              </span>
            </div>
            """, unsafe_allow_html=True)

        if "Emergency" in doc_df[doc_df["status"] == "Overloaded"]["department"].values:
            st.markdown(f"""
            <div class="alert-card alert-critical">
              <span>🚨</span>
              <span style="font-size:0.87rem; color:{COLORS['text']};">
                Emergency department showing <b style="color:{COLORS['red']}">provider overload risk</b>. Recommend immediate reallocation.
              </span>
            </div>
            """, unsafe_allow_html=True)

    with ac2:
        if len(underutil_docs) > 0:
            st.markdown(f"""
            <div class="alert-card alert-warning">
              <span>⚠️</span>
              <span style="font-size:0.87rem; color:{COLORS['text']};">
                <b>{len(underutil_docs)} providers</b> are below optimal utilization this week. 
                Consider patient redistribution.
              </span>
            </div>
            """, unsafe_allow_html=True)

        for _, row in underutil_docs.iterrows():
            st.markdown(f"""
            <div class="alert-card alert-warning">
              <span>⚠️</span>
              <span style="font-size:0.87rem; color:{COLORS['text']};">
                <b>{row['doctor']}</b> ({row['department']}) running at 
                <b style="color:{COLORS['amber']}">{row['pct_vs_avg']:+.1f}%</b> vs department average. 
                Capacity available for additional cases.
              </span>
            </div>
            """, unsafe_allow_html=True)

        st.markdown(f"""
        <div class="alert-card alert-info">
          <span>ℹ️</span>
          <span style="font-size:0.87rem; color:{COLORS['text']};">
            Optimal load redistribution could reduce top provider overload by <b style="color:{COLORS['cyan']}">~18%</b> with current staffing.
          </span>
        </div>
        """, unsafe_allow_html=True)
