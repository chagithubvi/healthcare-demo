import streamlit as st
import pandas as pd
import numpy as np
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from utils.data_generator import (
    get_supply_consumption, get_supply_trend, get_supply_forecast, get_dept_supply_usage
)
from utils.charts import COLORS, DEPT_COLORS, STATUS_COLORS, apply_layout
import plotly.express as px
import plotly.graph_objects as go

def render():
    # ── Page Header ───────────────────────────────────────────────────────────
    st.markdown("""
    <div class="page-header" style="
        background: linear-gradient(135deg, #0D2035 0%, #0A1820 100%);
        border-color: #1E3850;">
      <div class="page-header-icon">📦</div>
      <div>
        <div class="page-header-title">Medical Supply Consumption & Demand Forecasting</div>
        <div class="page-header-desc">
          Monitor usage patterns · Detect spikes · Forecast 30-day demand · Prevent stockouts
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    supply_df  = get_supply_consumption()
    trend_df   = get_supply_trend()
    forecast_df = get_supply_forecast()
    dept_sup_df = get_dept_supply_usage()

    # ── Filters ───────────────────────────────────────────────────────────────
    col_f1, col_f2, _ = st.columns([1.2, 1, 1.8])
    supply_sel = col_f1.selectbox("Supply Item (Trend & Forecast)", supply_df["supply"].tolist()[:6])
    risk_filter = col_f2.selectbox("Filter by Risk Level", ["All", "Critical", "Warning", "Safe"])

    disp_supply = supply_df.copy()
    if risk_filter != "All":
        disp_supply = disp_supply[disp_supply["risk"] == risk_filter]

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

    critical = (supply_df["risk"] == "Critical").sum()
    warning  = (supply_df["risk"] == "Warning").sum()
    total_monthly_cost = supply_df["monthly_cost"].sum()
    min_stock_item = supply_df.nsmallest(1, "days_until_stockout").iloc[0]

    kpi(k1, "🚨", critical, "Critical Items", "< 7 days until stockout", COLORS["red"])
    kpi(k2, "⚠️", warning,  "Warning Items",  "7–14 days remaining", COLORS["amber"])
    kpi(k3, "💰", f"${total_monthly_cost:,.0f}", "Monthly Supply Cost", "All categories combined", COLORS["cyan"])
    kpi(k4, "📉", f"{min_stock_item['days_until_stockout']:.1f}d", "Lowest Stock",
        min_stock_item["supply"][:20], COLORS["red"])

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Row 1: Top consumed + Stock status ────────────────────────────────────
    col_l, col_r = st.columns([1.4, 1])

    with col_l:
        st.markdown('<div class="section-title">Top 10 Most Consumed Medical Supplies</div>', unsafe_allow_html=True)
        st.markdown('<div class="section-sub">Monthly usage volume — color indicates stock risk level (Green = safe, Amber = warning, Red = critical)</div>', unsafe_allow_html=True)

        top10 = supply_df.head(10).copy()
        risk_colors = {"Critical": COLORS["red"], "Warning": COLORS["amber"], "Safe": COLORS["green"]}
        bar_colors = [risk_colors[r] for r in top10["risk"]]

        fig = go.Figure(go.Bar(
            x=top10["monthly_units"],
            y=top10["supply"],
            orientation="h",
            marker_color=bar_colors,
            marker_line_width=0,
            text=[f"{v:,} units" for v in top10["monthly_units"]],
            textposition="outside",
            textfont=dict(color=COLORS["text"], size=10),
            hovertemplate="<b>%{y}</b><br>Monthly: %{x:,} units<br>Cost: $%{customdata:,.0f}<extra></extra>",
            customdata=top10["monthly_cost"],
        ))
        apply_layout(fig, height=420)
        fig.update_layout(
            xaxis_title="Monthly Consumption (units)",
            yaxis_title="",
            showlegend=False,
        )
        st.plotly_chart(fig, width="stretch")

    with col_r:
        st.markdown('<div class="section-title">Supply Stock Status</div>', unsafe_allow_html=True)
        st.markdown('<div class="section-sub">Current stock health — days until reorder needed</div>', unsafe_allow_html=True)

        for _, row in disp_supply.iterrows():
            color = risk_colors.get(row["risk"], COLORS["green"])
            pct = min(100, (row["days_until_stockout"] / 30) * 100)
            icon = "🔴" if row["risk"] == "Critical" else "🟡" if row["risk"] == "Warning" else "🟢"

            st.markdown(f"""
            <div style="background:#0D1F38; border:1px solid #1E3558;
                        border-left:4px solid {color}; border-radius:10px;
                        padding:10px 14px; margin-bottom:7px;">
              <div style="display:flex; justify-content:space-between; align-items:center;">
                <div style="flex:1;">
                  <div style="color:{COLORS['text']}; font-weight:600; font-size:0.83rem; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">{icon} {row['supply']}</div>
                  <div style="color:{COLORS['muted']}; font-size:0.72rem;">Stock: {row['stock_on_hand']} · Reorder: {row['reorder_point']}</div>
                </div>
                <div style="text-align:right; margin-left:12px;">
                  <div style="color:{color}; font-weight:700; font-size:0.95rem;">{row['days_until_stockout']:.1f}d</div>
                  <div style="color:{COLORS['muted']}; font-size:0.68rem;">until empty</div>
                </div>
              </div>
              <div style="background:#1A2D45; border-radius:4px; height:5px; margin-top:8px;">
                <div style="background:{color}; width:{pct}%; height:5px; border-radius:4px;"></div>
              </div>
            </div>
            """, unsafe_allow_html=True)

    # ── Row 2: Trend + Forecast ────────────────────────────────────────────────
    st.markdown("<br>", unsafe_allow_html=True)
    col_tl, col_tr = st.columns(2)

    with col_tl:
        st.markdown(f'<div class="section-title">Consumption Trend — {supply_sel}</div>', unsafe_allow_html=True)
        st.markdown('<div class="section-sub">90-day daily usage history · Peaks indicate potential demand spikes or bulk orders</div>', unsafe_allow_html=True)

        t_df = trend_df[trend_df["supply"] == supply_sel]

        # Compute 7-day rolling average for trend line
        t_df = t_df.sort_values("date").copy()
        t_df["rolling_7d"] = t_df["units"].rolling(7, min_periods=1).mean()

        # Spike detection (> 1.5x rolling)
        t_df["is_spike"] = t_df["units"] > t_df["rolling_7d"] * 1.4

        fig_t = go.Figure()
        fig_t.add_trace(go.Scatter(
            x=t_df["date"], y=t_df["units"],
            name="Daily Usage",
            line=dict(color=COLORS["cyan"], width=1.5),
            fill="tozeroy",
            fillcolor="rgba(0,212,255,0.06)",
        ))
        fig_t.add_trace(go.Scatter(
            x=t_df["date"], y=t_df["rolling_7d"],
            name="7-Day Avg",
            line=dict(color=COLORS["amber"], width=2, dash="dot"),
        ))
        # Spike markers
        spikes = t_df[t_df["is_spike"]]
        if len(spikes) > 0:
            fig_t.add_trace(go.Scatter(
                x=spikes["date"], y=spikes["units"],
                mode="markers",
                name="Spike Detected",
                marker=dict(color=COLORS["red"], size=8, symbol="x"),
            ))
        apply_layout(fig_t, height=360)
        fig_t.update_layout(
            xaxis_title="Date",
            yaxis_title="Units Consumed",
        )
        st.plotly_chart(fig_t, width="stretch")

    with col_tr:
        st.markdown(f'<div class="section-title">30-Day Demand Forecast — {supply_sel}</div>', unsafe_allow_html=True)
        st.markdown('<div class="section-sub">AI-predicted consumption with confidence band · Plan procurement accordingly</div>', unsafe_allow_html=True)

        fc_df = forecast_df[forecast_df["supply"] == supply_sel]

        fig_f = go.Figure()
        # Confidence band
        fig_f.add_trace(go.Scatter(
            x=list(fc_df["date"]) + list(fc_df["date"][::-1]),
            y=list(fc_df["upper"]) + list(fc_df["lower"][::-1]),
            fill="toself",
            fillcolor="rgba(0,212,255,0.08)",
            line=dict(color="rgba(0,0,0,0)"),
            name="Confidence Interval",
            hoverinfo="skip",
        ))
        # Forecast line
        fig_f.add_trace(go.Scatter(
            x=fc_df["date"], y=fc_df["forecast_units"],
            name="Forecast",
            line=dict(color=COLORS["cyan"], width=2.5),
            mode="lines+markers",
            marker=dict(size=4),
        ))
        # Reorder point
        stock_row = supply_df[supply_df["supply"] == supply_sel]
        if not stock_row.empty:
            reorder = stock_row.iloc[0]["reorder_point"]
            fig_f.add_hline(y=reorder, line_dash="dot", line_color=COLORS["amber"],
                            annotation_text=f"Reorder Point ({reorder} units)",
                            annotation_font_color=COLORS["amber"])

        apply_layout(fig_f, height=360)
        fig_f.update_layout(
            xaxis_title="Forecast Date",
            yaxis_title="Projected Units Needed",
        )
        st.plotly_chart(fig_f, width="stretch")

    # ── Row 3: Dept heatmap + weekly trend ────────────────────────────────────
    st.markdown("<br>", unsafe_allow_html=True)
    col_bl, col_br = st.columns([1.3, 1])

    with col_bl:
        st.markdown('<div class="section-title">Department-wise Supply Utilization</div>', unsafe_allow_html=True)
        st.markdown('<div class="section-sub">Monthly units consumed per supply category per department · Identify high-consumption centers</div>', unsafe_allow_html=True)

        pivot = dept_sup_df.pivot_table(index="supply", columns="department", values="monthly_units", aggfunc="sum", fill_value=0)
        # Show top 8 supplies × top 6 departments
        pivot = pivot.iloc[:8, :6]

        fig_h = go.Figure(go.Heatmap(
            z=pivot.values,
            x=pivot.columns,
            y=pivot.index,
            colorscale=[[0, "#0A1628"], [0.4, "#005599"], [0.7, "#00AADD"], [1, "#00E5FF"]],
            showscale=True,
            colorbar=dict(
                title=dict(text="Units/Month", font=dict(color=COLORS["muted"])),
                tickfont=dict(color=COLORS["muted"]),
            ),
            hovertemplate="Supply: %{y}<br>Dept: %{x}<br>Monthly Units: %{z:,}<extra></extra>",
        ))
        apply_layout(fig_h, height=380)
        fig_h.update_layout(
            xaxis=dict(title="Department", tickangle=-30),
            yaxis=dict(title="Supply Item"),
        )
        st.plotly_chart(fig_h, width="stretch")

    with col_br:
        st.markdown('<div class="section-title">🔔 Supply Alerts & Actions</div>', unsafe_allow_html=True)
        st.markdown('<div class="section-sub">AI-detected consumption anomalies and procurement recommendations</div>', unsafe_allow_html=True)

        critical_items = supply_df[supply_df["risk"] == "Critical"]
        warning_items  = supply_df[supply_df["risk"] == "Warning"]

        for _, row in critical_items.iterrows():
            st.markdown(f"""
            <div class="alert-card alert-critical">
              <span>🚨</span>
              <div>
                <div style="font-size:0.87rem; color:{COLORS['text']};">
                  <b>{row['supply']}</b> — Potential stockout in <b style="color:{COLORS['red']}">{row['days_until_stockout']:.1f} days</b>
                </div>
                <div style="font-size:0.75rem; color:{COLORS['muted']}; margin-top:2px;">
                  Current: {row['stock_on_hand']} units · Weekly use: {row['weekly_units']:,}
                </div>
              </div>
            </div>
            """, unsafe_allow_html=True)

        for _, row in warning_items.head(3).iterrows():
            st.markdown(f"""
            <div class="alert-card alert-warning">
              <span>⚠️</span>
              <div>
                <div style="font-size:0.87rem; color:{COLORS['text']};">
                  <b>{row['supply']}</b> — <b style="color:{COLORS['amber']}">{row['days_until_stockout']:.1f} days</b> remaining stock
                </div>
                <div style="font-size:0.75rem; color:{COLORS['muted']}; margin-top:2px;">
                  Initiate procurement now to avoid disruption
                </div>
              </div>
            </div>
            """, unsafe_allow_html=True)

        # Dynamic spike alerts from trend
        trend_latest = trend_df[trend_df["supply"].isin(supply_df["supply"].head(4).tolist())]
        trend_latest = trend_latest.sort_values("date")
        for sup in trend_latest["supply"].unique():
            s_df = trend_latest[trend_latest["supply"] == sup]
            last_7 = s_df.tail(7)["units"].mean()
            prev_7 = s_df.iloc[-14:-7]["units"].mean() if len(s_df) >= 14 else last_7
            if prev_7 > 0 and (last_7 - prev_7) / prev_7 > 0.25:
                pct = (last_7 - prev_7) / prev_7 * 100
                st.markdown(f"""
                <div class="alert-card alert-warning">
                  <span>📈</span>
                  <span style="font-size:0.87rem; color:{COLORS['text']};">
                    <b>{sup}</b> consumption up <b style="color:{COLORS['amber']}">{pct:.0f}%</b> vs prior week.
                  </span>
                </div>
                """, unsafe_allow_html=True)

        st.markdown(f"""
        <div class="alert-card alert-success">
          <span>✅</span>
          <span style="font-size:0.87rem; color:{COLORS['text']};">
            {(supply_df['risk'] == 'Safe').sum()} supply items are at <b style="color:{COLORS['green']}">safe stock levels</b> for the next 30 days.
          </span>
        </div>
        """, unsafe_allow_html=True)