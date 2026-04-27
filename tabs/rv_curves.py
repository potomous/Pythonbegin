"""Relative Value tab — OAS scatter, sector curves, country spread chart."""

import numpy as np
import plotly.graph_objects as go
from dash import Input, Output, callback, dcc, html
import dash_bootstrap_components as dbc

from database import get_session, get_bonds_df, get_market_curve_df
from utils import (
    SECTORS, RATING_ORDER, COUNTRIES, MATURITY_BUCKETS,
    CARD_BG, TEXT_CLR, GRID_CLR, ACCENT,
    sector_color, base_layout, empty_figure, rating_to_numeric,
)

# ── layout ─────────────────────────────────────────────────────────────────────

_dd_style = {"backgroundColor": "#1c1c35", "color": TEXT_CLR, "fontSize": "12px"}

_controls = dbc.Row([
    dbc.Col(dbc.Select(
        id="rv-sector", options=[{"label": "All Sectors", "value": "ALL"}]
                                + [{"label": s, "value": s} for s in SECTORS],
        value="ALL", style=_dd_style,
    ), width=2),
    dbc.Col(dbc.Select(
        id="rv-currency",
        options=[{"label": "All CCY", "value": "ALL"},
                 {"label": "EUR", "value": "EUR"},
                 {"label": "USD", "value": "USD"},
                 {"label": "GBP", "value": "GBP"}],
        value="ALL", style=_dd_style,
    ), width=2),
    dbc.Col(dbc.Select(
        id="rv-color-by",
        options=[{"label": "Colour by Sector", "value": "sector"},
                 {"label": "Colour by Rating", "value": "composite_rating"},
                 {"label": "Colour by Country", "value": "country_of_risk"}],
        value="sector", style=_dd_style,
    ), width=2),
    dbc.Col(dbc.Select(
        id="rv-y-metric",
        options=[{"label": "Y-axis: OAS", "value": "oas"},
                 {"label": "Y-axis: Z-Spread", "value": "z_spread"},
                 {"label": "Y-axis: BM Spread", "value": "spread_benchmark"},
                 {"label": "Y-axis: Yield %", "value": "yield_pct"}],
        value="oas", style=_dd_style,
    ), width=2),
    dbc.Col(dbc.Select(
        id="rv-maturity-filter",
        options=[{"label": "All Maturities", "value": "ALL"}]
                + [{"label": b, "value": b} for b in MATURITY_BUCKETS],
        value="ALL", style=_dd_style,
    ), width=2),
], className="mb-3 g-2")

layout = html.Div([
    _controls,
    # Row 1 — main scatter + sector bar
    dbc.Row([
        dbc.Col(dbc.Card([
            dbc.CardHeader("OAS / Spread vs Duration",
                           style={"color": ACCENT, "fontSize": "12px",
                                  "backgroundColor": "#16162a", "padding": "6px 12px"}),
            dbc.CardBody(dcc.Graph(id="rv-oas-scatter", config={"displayModeBar": False}),
                         style={"padding": "4px"}),
        ], style={"backgroundColor": CARD_BG, "border": f"1px solid {GRID_CLR}"}),
        width=8),
        dbc.Col(dbc.Card([
            dbc.CardHeader("Median OAS by Sector",
                           style={"color": ACCENT, "fontSize": "12px",
                                  "backgroundColor": "#16162a", "padding": "6px 12px"}),
            dbc.CardBody(dcc.Graph(id="rv-sector-bar", config={"displayModeBar": False}),
                         style={"padding": "4px"}),
        ], style={"backgroundColor": CARD_BG, "border": f"1px solid {GRID_CLR}"}),
        width=4),
    ], className="mb-3"),
    # Row 2 — yield curve + country spread
    dbc.Row([
        dbc.Col(dbc.Card([
            dbc.CardHeader("Yield Curve — EUR Swaps (latest)",
                           style={"color": ACCENT, "fontSize": "12px",
                                  "backgroundColor": "#16162a", "padding": "6px 12px"}),
            dbc.CardBody(dcc.Graph(id="rv-yield-curve", config={"displayModeBar": False}),
                         style={"padding": "4px"}),
        ], style={"backgroundColor": CARD_BG, "border": f"1px solid {GRID_CLR}"}),
        width=5),
        dbc.Col(dbc.Card([
            dbc.CardHeader("Country Risk Spread Premium (bps)",
                           style={"color": ACCENT, "fontSize": "12px",
                                  "backgroundColor": "#16162a", "padding": "6px 12px"}),
            dbc.CardBody(dcc.Graph(id="rv-country-bar", config={"displayModeBar": False}),
                         style={"padding": "4px"}),
        ], style={"backgroundColor": CARD_BG, "border": f"1px solid {GRID_CLR}"}),
        width=4),
        dbc.Col(dbc.Card([
            dbc.CardHeader("OAS by Rating",
                           style={"color": ACCENT, "fontSize": "12px",
                                  "backgroundColor": "#16162a", "padding": "6px 12px"}),
            dbc.CardBody(dcc.Graph(id="rv-rating-box", config={"displayModeBar": False}),
                         style={"padding": "4px"}),
        ], style={"backgroundColor": CARD_BG, "border": f"1px solid {GRID_CLR}"}),
        width=3),
    ]),
])


# ── shared data loader ─────────────────────────────────────────────────────────

def _load(sector, currency, maturity):
    session = get_session()
    try:
        df = get_bonds_df(session)
    finally:
        session.close()

    if df.empty:
        return df

    if sector != "ALL":
        df = df[df["sector"] == sector]
    if currency != "ALL":
        df = df[df["currency"] == currency]
    if maturity != "ALL":
        df = df[df["maturity_bucket"] == maturity]

    df = df.dropna(subset=["oas", "spread_duration"])
    return df


# ── OAS scatter ────────────────────────────────────────────────────────────────

@callback(
    Output("rv-oas-scatter", "figure"),
    Input("rv-sector", "value"),
    Input("rv-currency", "value"),
    Input("rv-maturity-filter", "value"),
    Input("rv-color-by", "value"),
    Input("rv-y-metric", "value"),
)
def oas_scatter(sector, currency, maturity, color_by, y_metric):
    df = _load(sector, currency, maturity)
    if df.empty:
        return empty_figure("No data — load sample data first.")

    df = df.dropna(subset=[y_metric, "spread_duration"])

    y_labels = {"oas": "OAS (bps)", "z_spread": "Z-Spread (bps)",
                 "spread_benchmark": "BM Spread (bps)", "yield_pct": "Yield (%)"}
    y_lbl = y_labels.get(y_metric, y_metric)

    groups = df[color_by].unique()
    fig = go.Figure()

    for grp in sorted(groups, key=lambda x: rating_to_numeric(x) if color_by == "composite_rating" else x):
        sub = df[df[color_by] == grp]
        if sub.empty:
            continue
        col = sector_color(grp) if color_by == "sector" else None

        # Bubble size proportional to issue size, capped
        sizes = sub["issue_size_mm"].fillna(500)
        sizes = (sizes / sizes.max() * 22 + 6).clip(6, 28)

        fig.add_trace(go.Scatter(
            x=sub["spread_duration"],
            y=sub[y_metric],
            mode="markers+text",
            name=str(grp),
            text=sub["ticker"],
            textposition="top center",
            textfont=dict(size=8),
            marker=dict(
                size=sizes,
                color=col,
                opacity=0.82,
                line=dict(width=0.5, color="#ffffff30"),
            ),
            customdata=sub[["issuer", "composite_rating", "oas",
                             "yield_pct", "spread_duration", "maturity_bucket"]].values,
            hovertemplate=(
                "<b>%{text}</b><br>%{customdata[0]}<br>"
                "Rating: %{customdata[1]}<br>"
                "OAS: %{customdata[2]:.0f} bps<br>"
                "Yield: %{customdata[3]:.3f}%<br>"
                "Sprd Dur: %{customdata[4]:.1f}y<br>"
                "Bucket: %{customdata[5]}<extra></extra>"
            ),
        ))

    # Regression trendline (all filtered data)
    try:
        x_arr = df["spread_duration"].values.astype(float)
        y_arr = df[y_metric].values.astype(float)
        mask = np.isfinite(x_arr) & np.isfinite(y_arr)
        if mask.sum() > 2:
            coeffs = np.polyfit(x_arr[mask], y_arr[mask], 1)
            xs = np.linspace(x_arr[mask].min(), x_arr[mask].max(), 50)
            fig.add_trace(go.Scatter(
                x=xs, y=np.polyval(coeffs, xs),
                mode="lines", name="Trend",
                line=dict(color="#ffffff40", width=1.5, dash="dot"),
                hoverinfo="skip",
            ))
    except Exception:
        pass

    layout = base_layout(f"{y_lbl} vs Spread Duration", height=380)
    layout["xaxis"]["title"] = "Spread Duration (yrs)"
    layout["yaxis"]["title"] = y_lbl
    fig.update_layout(**layout)
    return fig


# ── sector bar ────────────────────────────────────────────────────────────────

@callback(
    Output("rv-sector-bar", "figure"),
    Input("rv-sector", "value"),
    Input("rv-currency", "value"),
    Input("rv-maturity-filter", "value"),
    Input("rv-y-metric", "value"),
)
def sector_bar(sector, currency, maturity, y_metric):
    df = _load(sector, currency, maturity)
    if df.empty:
        return empty_figure()

    df = df.dropna(subset=[y_metric])
    grp = df.groupby("sector")[y_metric].median().sort_values()
    colors = [sector_color(s) for s in grp.index]

    fig = go.Figure(go.Bar(
        x=grp.values, y=grp.index,
        orientation="h",
        marker_color=colors,
        text=[f"{v:.0f}" for v in grp.values],
        textposition="outside",
        textfont=dict(size=9),
        hovertemplate="<b>%{y}</b><br>Median: %{x:.0f} bps<extra></extra>",
    ))
    layout = base_layout("", height=380)
    layout["margin"] = dict(l=110, r=40, t=10, b=30)
    layout["xaxis"]["title"] = "bps"
    fig.update_layout(**layout)
    return fig


# ── yield curve ───────────────────────────────────────────────────────────────

@callback(
    Output("rv-yield-curve", "figure"),
    Input("rv-sector", "value"),   # dummy trigger to re-load
)
def yield_curve(_dummy):
    session = get_session()
    try:
        curve_df = get_market_curve_df(session)
    finally:
        session.close()

    if curve_df.empty:
        return empty_figure("No yield curve data.")

    latest = curve_df["date"].max()
    # Show last 5 distinct dates for context
    dates = sorted(curve_df["date"].unique())[-5:]

    fig = go.Figure()
    for d in dates:
        sub = curve_df[(curve_df["date"] == d) & (curve_df["curve_type"] == "EUR_SWAPS")]
        sub = sub.sort_values("tenor")
        alpha = 0.3 + 0.7 * (dates.index(d) / max(len(dates) - 1, 1))
        is_latest = d == latest
        fig.add_trace(go.Scatter(
            x=sub["tenor"], y=sub["yield_pct"],
            mode="lines+markers",
            name=str(d),
            line=dict(
                color=ACCENT if is_latest else "#3a5080",
                width=2 if is_latest else 1,
                dash="solid" if is_latest else "dot",
            ),
            marker=dict(size=4 if is_latest else 2),
            opacity=alpha,
        ))

    layout = base_layout("", height=320)
    layout["xaxis"]["title"] = "Tenor (yrs)"
    layout["yaxis"]["title"] = "Yield (%)"
    fig.update_layout(**layout)
    return fig


# ── country spread bar ────────────────────────────────────────────────────────

@callback(
    Output("rv-country-bar", "figure"),
    Input("rv-sector", "value"),
    Input("rv-currency", "value"),
    Input("rv-maturity-filter", "value"),
)
def country_bar(sector, currency, maturity):
    df = _load(sector, currency, maturity)
    if df.empty:
        return empty_figure()

    df = df.dropna(subset=["country_spread"])
    grp = df.groupby("country_of_risk")["country_spread"].median().sort_values()

    colors = [
        "#ff4444" if v > 100 else "#ffab40" if v > 30 else "#00e676"
        for v in grp.values
    ]

    fig = go.Figure(go.Bar(
        x=grp.values, y=grp.index,
        orientation="h",
        marker_color=colors,
        text=[f"{v:.0f}" for v in grp.values],
        textposition="outside",
        textfont=dict(size=9),
        hovertemplate="<b>%{y}</b><br>Spread: %{x:.0f} bps<extra></extra>",
    ))
    layout = base_layout("", height=320)
    layout["margin"] = dict(l=120, r=50, t=10, b=30)
    layout["xaxis"]["title"] = "bps"
    fig.update_layout(**layout)
    return fig


# ── OAS rating box ────────────────────────────────────────────────────────────

@callback(
    Output("rv-rating-box", "figure"),
    Input("rv-sector", "value"),
    Input("rv-currency", "value"),
    Input("rv-maturity-filter", "value"),
)
def rating_box(sector, currency, maturity):
    df = _load(sector, currency, maturity)
    if df.empty:
        return empty_figure()

    df = df.dropna(subset=["oas"])
    present = [r for r in RATING_ORDER if r in df["composite_rating"].values]
    fig = go.Figure()
    for rtg in present:
        sub = df[df["composite_rating"] == rtg]["oas"]
        fig.add_trace(go.Box(
            y=sub, name=rtg,
            marker_color=ACCENT,
            boxmean=True,
            hovertemplate=f"<b>{rtg}</b><br>OAS: %{{y:.0f}} bps<extra></extra>",
        ))
    layout = base_layout("", height=320)
    layout["xaxis"]["title"] = "Rating"
    layout["yaxis"]["title"] = "OAS (bps)"
    layout["showlegend"] = False
    fig.update_layout(**layout)
    return fig
