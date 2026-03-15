"""Shared Plotly chart theme and helpers."""
import plotly.graph_objects as go
import plotly.express as px

# ── Color palette ──────────────────────────────────────────────────────────────
COLORS = {
    "bg": "#050D1A",
    "card": "#0D1F38",
    "border": "#1E3558",
    "text": "#E8EDF5",
    "muted": "#5A7A9A",
    "cyan": "#00D4FF",
    "blue": "#0066FF",
    "green": "#00E5A0",
    "amber": "#FFB547",
    "red": "#FF4D6A",
    "purple": "#9B6DFF",
    "pink": "#FF6DB6",
}

DEPT_COLORS = [
    "#00D4FF", "#0066FF", "#00E5A0", "#FFB547", "#FF4D6A",
    "#9B6DFF", "#FF6DB6", "#38E8C5", "#FF9142", "#7AABFF",
]

STATUS_COLORS = {
    "Overloaded": COLORS["red"],
    "Optimal": COLORS["green"],
    "Underutilized": COLORS["amber"],
    "Critical": COLORS["red"],
    "Warning": COLORS["amber"],
    "Safe": COLORS["green"],
}

# ── Base layout ────────────────────────────────────────────────────────────────
def base_layout(title="", height=380, showlegend=True):
    return dict(
        title=dict(text=title, font=dict(family="Space Grotesk", size=15, color=COLORS["text"]), x=0.01),
        height=height,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="DM Sans", color=COLORS["muted"], size=12),
        showlegend=showlegend,
        legend=dict(
            bgcolor="rgba(0,0,0,0)",
            bordercolor=COLORS["border"],
            borderwidth=1,
            font=dict(color=COLORS["text"], size=11),
        ),
        margin=dict(l=16, r=16, t=44, b=16),
        xaxis=dict(
            gridcolor="#1A2D45",
            linecolor=COLORS["border"],
            tickcolor=COLORS["border"],
            tickfont=dict(color=COLORS["muted"]),
            title_font=dict(color=COLORS["muted"]),
        ),
        yaxis=dict(
            gridcolor="#1A2D45",
            linecolor=COLORS["border"],
            tickcolor=COLORS["border"],
            tickfont=dict(color=COLORS["muted"]),
            title_font=dict(color=COLORS["muted"]),
        ),
        hoverlabel=dict(
            bgcolor="#0D1F38",
            bordercolor=COLORS["border"],
            font=dict(color=COLORS["text"], family="DM Sans"),
        ),
    )

def apply_layout(fig, title="", height=380, showlegend=True):
    fig.update_layout(**base_layout(title, height, showlegend))
    return fig

# ── Chart wrappers ─────────────────────────────────────────────────────────────
def bar_chart(df, x, y, color=None, color_map=None, title="", height=380,
              orientation="v", text=None, barmode="group"):
    if orientation == "h":
        fig = px.bar(df, x=y, y=x, color=color, color_discrete_map=color_map,
                     orientation="h", text=text, barmode=barmode)
    else:
        fig = px.bar(df, x=x, y=y, color=color, color_discrete_map=color_map,
                     text=text, barmode=barmode)
    apply_layout(fig, title, height)
    fig.update_traces(marker_line_width=0)
    return fig

def line_chart(df, x, y, color=None, title="", height=380, markers=False):
    fig = px.line(df, x=x, y=y, color=color, markers=markers,
                  color_discrete_sequence=DEPT_COLORS)
    apply_layout(fig, title, height)
    fig.update_traces(line_width=2)
    return fig

def scatter_chart(df, x, y, color=None, size=None, hover_data=None, title="", height=380):
    fig = px.scatter(df, x=x, y=y, color=color, size=size,
                     hover_data=hover_data, color_discrete_sequence=DEPT_COLORS)
    apply_layout(fig, title, height)
    return fig

def gauge(value, min_val, max_val, title="", threshold=None):
    steps = [
        dict(range=[min_val, max_val * 0.5], color="#0D2A1A"),
        dict(range=[max_val * 0.5, max_val * 0.8], color="#1A2A10"),
        dict(range=[max_val * 0.8, max_val], color="#2A1A10"),
    ]
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=value,
        title=dict(text=title, font=dict(color=COLORS["muted"], size=13)),
        number=dict(font=dict(color=COLORS["text"], size=28, family="Space Grotesk")),
        gauge=dict(
            axis=dict(range=[min_val, max_val], tickcolor=COLORS["muted"],
                      tickfont=dict(color=COLORS["muted"])),
            bar=dict(color=COLORS["cyan"], thickness=0.25),
            bgcolor=COLORS["card"],
            borderwidth=1,
            bordercolor=COLORS["border"],
            steps=steps,
            threshold=dict(
                line=dict(color=COLORS["amber"], width=2),
                thickness=0.75,
                value=threshold or max_val * 0.8,
            ),
        ),
    ))
    apply_layout(fig, height=240, showlegend=False)
    return fig

def donut_chart(labels, values, title="", height=320, colors=None):
    fig = go.Figure(go.Pie(
        labels=labels, values=values,
        hole=0.6,
        marker=dict(colors=colors or DEPT_COLORS,
                    line=dict(color=COLORS["bg"], width=2)),
        textfont=dict(color=COLORS["text"]),
    ))
    apply_layout(fig, title, height)
    return fig

def heatmap(z, x, y, title="", height=380):
    fig = go.Figure(go.Heatmap(
        z=z, x=x, y=y,
        colorscale=[[0, "#0A1628"], [0.5, "#0066FF"], [1, "#00D4FF"]],
        showscale=True,
        hoverongaps=False,
    ))
    apply_layout(fig, title, height)
    return fig
