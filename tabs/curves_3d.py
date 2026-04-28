"""3D Curve History tab — spread surface and stacked historical curves."""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from dash import Input, Output, callback, dcc, html
import dash_bootstrap_components as dbc

from database import get_session, get_price_history_df, get_bonds_df
from utils import (
    SECTORS, RATING_ORDER, CARD_BG, TEXT_CLR, GRID_CLR, ACCENT,
    sector_color, base_layout, empty_figure,
)

# ── layout ─────────────────────────────────────────────────────────────────────

_dd = {"backgroundColor": "#1c1c35", "color": TEXT_CLR, "fontSize": "12px"}

layout = html.Div([
    dbc.Row([
        dbc.Col(dbc.Select(
            id="c3d-sector",
            options=[{"label": "All Sectors", "value": "ALL"}]
                   + [{"label": s, "value": s} for s in SECTORS],
            value="Financial", style=_dd,
        ), width=2),
        dbc.Col(dbc.Select(
            id="c3d-rating",
            options=[{"label": "All Ratings", "value": "ALL"}]
                   + [{"label": r, "value": r} for r in RATING_ORDER],
            value="ALL", style=_dd,
        ), width=2),
        dbc.Col(dbc.Select(
            id="c3d-metric",
            options=[
                {"label": "OAS (bps)",      "value": "oas"},
                {"label": "Z-Spread (bps)", "value": "z_spread"},
                {"label": "BM Spread",      "value": "spread_benchmark"},
                {"label": "Yield (%)",      "value": "yield_pct"},
                {"label": "iTraxx Spread",  "value": "spread_itraxx"},
                {"label": "CDX Spread",     "value": "spread_cdx"},
            ],
            value="oas", style=_dd,
        ), width=2),
        dbc.Col(dbc.Select(
            id="c3d-view",
            options=[
                {"label": "Surface (interpolated)", "value": "surface"},
                {"label": "Stacked Lines",          "value": "lines"},
            ],
            value="surface", style=_dd,
        ), width=2),
        dbc.Col([
            dbc.Label("History (days):", style={"fontSize": "11px", "color": TEXT_CLR}),
            dbc.Input(id="c3d-days", type="number", value=60, min=10, max=90,
                      size="sm",
                      style={"backgroundColor": "#1c1c35", "color": TEXT_CLR,
                             "border": f"1px solid {GRID_CLR}", "fontSize": "12px",
                             "width": "80px"}),
        ], width=2, className="d-flex align-items-center gap-2"),
    ], className="mb-3 g-2"),

    dbc.Row([
        dbc.Col(dbc.Card([
            dbc.CardHeader(
                html.Span(id="c3d-title",
                          style={"color": ACCENT, "fontSize": "12px"}),
                style={"backgroundColor": "#16162a", "padding": "6px 12px"},
            ),
            dbc.CardBody(
                dcc.Graph(
                    id="c3d-main",
                    config={"displayModeBar": True, "modeBarButtonsToRemove": ["toImage"]},
                    style={"height": "520px"},
                ),
                style={"padding": "4px"},
            ),
        ], style={"backgroundColor": CARD_BG, "border": f"1px solid {GRID_CLR}"}),
        width=8),
        dbc.Col([
            dbc.Card([
                dbc.CardHeader("Latest Curve Snapshot",
                               style={"color": ACCENT, "fontSize": "12px",
                                      "backgroundColor": "#16162a", "padding": "6px 12px"}),
                dbc.CardBody(
                    dcc.Graph(id="c3d-latest", config={"displayModeBar": False},
                              style={"height": "240px"}),
                    style={"padding": "4px"},
                ),
            ], style={"backgroundColor": CARD_BG, "border": f"1px solid {GRID_CLR}",
                      "marginBottom": "12px"}),
            dbc.Card([
                dbc.CardHeader("Curve Change (first → last date)",
                               style={"color": ACCENT, "fontSize": "12px",
                                      "backgroundColor": "#16162a", "padding": "6px 12px"}),
                dbc.CardBody(
                    dcc.Graph(id="c3d-change", config={"displayModeBar": False},
                              style={"height": "240px"}),
                    style={"padding": "4px"},
                ),
            ], style={"backgroundColor": CARD_BG, "border": f"1px solid {GRID_CLR}"}),
        ], width=4),
    ]),
])


# ── helpers ────────────────────────────────────────────────────────────────────

def _fetch(sector, rating, days):
    session = get_session()
    try:
        bonds_df = get_bonds_df(session)
        if bonds_df.empty:
            return pd.DataFrame(), pd.DataFrame()

        isins = bonds_df["isin"].tolist()
        history = get_price_history_df(session, isins)

        if sector != "ALL":
            history = history[history["sector"] == sector]
        if rating != "ALL":
            history = history[history["composite_rating"] == rating]

        if history.empty:
            return pd.DataFrame(), pd.DataFrame()

        history["date"] = pd.to_datetime(history["date"])
        cutoff = history["date"].max() - pd.Timedelta(days=days)
        history = history[history["date"] >= cutoff]

        # Attach spread_duration from bonds_df (it's in price history already)
        return history, bonds_df
    finally:
        session.close()


def _sample_dates(dates, n=15):
    """Select ~n evenly-spaced dates."""
    dates = sorted(set(dates))
    if len(dates) <= n:
        return dates
    idx = np.linspace(0, len(dates) - 1, n, dtype=int)
    return [dates[i] for i in idx]


# ── main 3d chart ──────────────────────────────────────────────────────────────

@callback(
    Output("c3d-main", "figure"),
    Output("c3d-title", "children"),
    Input("c3d-sector", "value"),
    Input("c3d-rating", "value"),
    Input("c3d-metric", "value"),
    Input("c3d-view", "value"),
    Input("c3d-days", "value"),
)
def main_3d(sector, rating, metric, view, days):
    history, _ = _fetch(sector, rating, int(days or 60))
    if history.empty:
        return empty_figure("No data — load sample data first."), "No data"

    history = history.dropna(subset=[metric, "spread_duration"])
    lbl_map = {"oas": "OAS", "z_spread": "Z-Sprd", "spread_benchmark": "BM Sprd",
               "yield_pct": "Yield%", "spread_itraxx": "iTraxx", "spread_cdx": "CDX"}
    metric_lbl = lbl_map.get(metric, metric)
    title_txt = f"{metric_lbl} Curve History — {sector} / {rating}"

    dates = sorted(history["date"].unique())

    if view == "lines":
        fig = _stacked_lines(history, dates, metric, metric_lbl)
    else:
        fig = _surface(history, dates, metric, metric_lbl)

    return fig, title_txt


def _stacked_lines(history, dates, metric, metric_lbl):
    """Each date is a separate 3D line, coloured from old (blue) to new (cyan)."""
    sampled = _sample_dates(dates, n=20)
    fig = go.Figure()

    n = len(sampled)
    for i, d in enumerate(sampled):
        sub = history[history["date"] == d].sort_values("spread_duration")
        if sub.empty:
            continue
        frac = i / max(n - 1, 1)
        # Interpolate color: dark blue → bright cyan
        r = int(0 + frac * 0)
        g = int(100 + frac * 156)
        b = int(180 + frac * 75)
        col = f"rgb({r},{g},{b})"

        fig.add_trace(go.Scatter3d(
            x=sub["spread_duration"],
            y=[str(d.date() if hasattr(d, "date") else d)] * len(sub),
            z=sub[metric],
            mode="lines+markers",
            name=str(d.date() if hasattr(d, "date") else d),
            line=dict(color=col, width=3),
            marker=dict(size=3, color=col),
            showlegend=(i == n - 1 or i == 0),
            hovertemplate=(
                "Dur: %{x:.1f}y<br>Date: %{y}<br>"
                f"{metric_lbl}: %{{z:.1f}}<extra></extra>"
            ),
        ))

    fig.update_layout(
        scene=dict(
            xaxis=dict(title="Spread Dur (y)", backgroundcolor="#0d0d14",
                       gridcolor=GRID_CLR, showbackground=True),
            yaxis=dict(title="Date", backgroundcolor="#0d0d14",
                       gridcolor=GRID_CLR, showbackground=True,
                       tickangle=-30, tickfont=dict(size=7)),
            zaxis=dict(title=metric_lbl, backgroundcolor="#0d0d14",
                       gridcolor=GRID_CLR, showbackground=True),
            bgcolor="#0d0d14",
            camera=dict(eye=dict(x=1.8, y=-1.8, z=0.9)),
        ),
        paper_bgcolor=CARD_BG,
        font=dict(color=TEXT_CLR, size=10),
        height=520,
        margin=dict(l=0, r=0, t=10, b=0),
        showlegend=False,
    )
    return fig


def _surface(history, dates, metric, metric_lbl):
    """Interpolated 3D surface: X=spread_dur, Y=date_index, Z=metric."""
    from scipy.interpolate import griddata

    sampled = _sample_dates(dates, n=25)
    rows = []
    for i, d in enumerate(sampled):
        sub = history[history["date"] == d].dropna(subset=[metric, "spread_duration"])
        for _, r in sub.iterrows():
            rows.append((r["spread_duration"], i, r[metric]))

    if len(rows) < 6:
        return empty_figure("Not enough data for surface.")

    pts = np.array(rows)
    xs, ys, zs = pts[:, 0], pts[:, 1], pts[:, 2]

    xg = np.linspace(xs.min(), xs.max(), 40)
    yg = np.linspace(ys.min(), ys.max(), len(sampled))
    Xg, Yg = np.meshgrid(xg, yg)

    Zg = griddata((xs, ys), zs, (Xg, Yg), method="linear")
    Zg_nn = griddata((xs, ys), zs, (Xg, Yg), method="nearest")
    Zg = np.where(np.isnan(Zg), Zg_nn, Zg)

    date_labels = [str(d.date() if hasattr(d, "date") else d) for d in sampled]
    tick_step = max(1, len(sampled) // 6)

    fig = go.Figure(go.Surface(
        x=xg,
        y=list(range(len(sampled))),
        z=Zg,
        colorscale=[
            [0.0, "#1a0040"], [0.2, "#003580"], [0.4, "#0070c0"],
            [0.6, "#00c8ff"], [0.8, "#ffab40"], [1.0, "#ff1744"],
        ],
        reversescale=False,
        opacity=0.9,
        showscale=True,
        colorbar=dict(title=metric_lbl, tickfont=dict(size=9, color=TEXT_CLR),
                      titlefont=dict(size=10, color=TEXT_CLR)),
        hovertemplate=(
            "Sprd Dur: %{x:.1f}y<br>"
            f"{metric_lbl}: %{{z:.1f}}<extra></extra>"
        ),
    ))

    fig.update_layout(
        scene=dict(
            xaxis=dict(title="Spread Dur (y)", backgroundcolor="#0d0d14",
                       gridcolor=GRID_CLR, showbackground=True),
            yaxis=dict(
                title="Date",
                backgroundcolor="#0d0d14",
                gridcolor=GRID_CLR,
                showbackground=True,
                tickvals=list(range(0, len(sampled), tick_step)),
                ticktext=[date_labels[i] for i in range(0, len(sampled), tick_step)],
                tickfont=dict(size=7),
                tickangle=-25,
            ),
            zaxis=dict(title=metric_lbl, backgroundcolor="#0d0d14",
                       gridcolor=GRID_CLR, showbackground=True),
            bgcolor="#0d0d14",
            camera=dict(eye=dict(x=1.7, y=-1.7, z=0.8)),
        ),
        paper_bgcolor=CARD_BG,
        font=dict(color=TEXT_CLR, size=10),
        height=520,
        margin=dict(l=0, r=0, t=10, b=0),
    )
    return fig


# ── latest snapshot ────────────────────────────────────────────────────────────

@callback(
    Output("c3d-latest", "figure"),
    Input("c3d-sector", "value"),
    Input("c3d-rating", "value"),
    Input("c3d-metric", "value"),
    Input("c3d-days", "value"),
)
def latest_curve(sector, rating, metric, days):
    history, _ = _fetch(sector, rating, int(days or 60))
    if history.empty:
        return empty_figure()

    history = history.dropna(subset=[metric, "spread_duration"])
    latest_date = history["date"].max()
    sub = history[history["date"] == latest_date].sort_values("spread_duration")

    lbl_map = {"oas": "OAS (bps)", "z_spread": "Z-Sprd (bps)",
               "spread_benchmark": "BM Sprd (bps)", "yield_pct": "Yield (%)",
               "spread_itraxx": "iTraxx", "spread_cdx": "CDX"}

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=sub["spread_duration"],
        y=sub[metric],
        mode="markers+lines",
        text=sub["ticker"],
        textposition="top center",
        textfont=dict(size=7),
        marker=dict(color=ACCENT, size=7),
        line=dict(color=ACCENT, width=1.5),
        hovertemplate=(
            "<b>%{text}</b><br>Dur: %{x:.1f}y<br>"
            f"{lbl_map.get(metric, metric)}: %{{y:.1f}}<extra></extra>"
        ),
    ))
    layout = base_layout(f"Latest: {str(latest_date)[:10]}", height=240)
    layout["xaxis"]["title"] = "Sprd Dur (y)"
    layout["yaxis"]["title"] = lbl_map.get(metric, metric)
    layout["margin"] = dict(l=50, r=10, t=32, b=36)
    fig.update_layout(**layout)
    return fig


# ── curve change bar ───────────────────────────────────────────────────────────

@callback(
    Output("c3d-change", "figure"),
    Input("c3d-sector", "value"),
    Input("c3d-rating", "value"),
    Input("c3d-metric", "value"),
    Input("c3d-days", "value"),
)
def curve_change(sector, rating, metric, days):
    history, _ = _fetch(sector, rating, int(days or 60))
    if history.empty:
        return empty_figure()

    history = history.dropna(subset=[metric])
    dates = sorted(history["date"].unique())
    if len(dates) < 2:
        return empty_figure("Need ≥ 2 dates.")

    first, last = dates[0], dates[-1]
    first_df = history[history["date"] == first].set_index("ticker")[metric]
    last_df = history[history["date"] == last].set_index("ticker")[metric]
    change = (last_df - first_df).dropna().sort_values()

    lbl_map = {"oas": "OAS Δ (bps)", "z_spread": "Z-Sprd Δ", "yield_pct": "Yield Δ (%)"}
    colors = ["#ff1744" if v > 0 else "#00e676" for v in change.values]

    fig = go.Figure(go.Bar(
        x=change.values,
        y=change.index,
        orientation="h",
        marker_color=colors,
        text=[f"{v:+.1f}" for v in change.values],
        textposition="outside",
        textfont=dict(size=8),
        hovertemplate="<b>%{y}</b><br>Change: %{x:+.1f}<extra></extra>",
    ))
    layout = base_layout(
        f"Change {str(first)[:10]} → {str(last)[:10]}", height=240
    )
    layout["margin"] = dict(l=80, r=40, t=32, b=28)
    layout["xaxis"]["title"] = lbl_map.get(metric, "Δ")
    layout["showlegend"] = False
    fig.update_layout(**layout)
    return fig
