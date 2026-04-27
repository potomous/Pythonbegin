"""New Issue Pricing tab — fair value estimation and NIC calculation."""

from datetime import date

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from dash import Input, Output, State, callback, dash_table, dcc, html, no_update
import dash_bootstrap_components as dbc

from database import (
    get_session, get_bonds_df, NewIssuePricing,
)
from utils import (
    SECTORS, RATING_ORDER, COUNTRIES, SENIORITIES, CURRENCIES,
    BENCHMARKS, CARD_BG, TEXT_CLR, GRID_CLR, ACCENT,
    POS_CLR, NEG_CLR, WARN_CLR,
    sector_color, base_layout, empty_figure,
    get_adjacent_ratings, rating_to_numeric,
)

# ── helpers ────────────────────────────────────────────────────────────────────

def _fair_value(comps_df: pd.DataFrame, tenor: float) -> float | None:
    """Fit OAS = a + b*spread_duration through comps, interpolate at new tenor."""
    df = comps_df.dropna(subset=["oas", "spread_duration"])
    if df.empty:
        return None
    if len(df) == 1:
        return float(df["oas"].iloc[0])

    # Simple linear interpolation/regression
    x = df["spread_duration"].values.astype(float)
    y = df["oas"].values.astype(float)
    mask = np.isfinite(x) & np.isfinite(y)
    if mask.sum() < 2:
        return float(np.nanmedian(y))
    try:
        coeffs = np.polyfit(x[mask], y[mask], 1)
        # Approx spread duration for new tenor
        approx_sd = min(tenor * 0.92, 12.0)
        fv = np.polyval(coeffs, approx_sd)
        return float(max(0, fv))
    except Exception:
        return float(np.nanmedian(y))


def _nic_badge(nic: float | None):
    if nic is None:
        return html.Span("—", style={"color": TEXT_CLR})
    if nic > 10:
        return html.Span(f"+{nic:.1f} bps (generous concession)",
                         style={"color": POS_CLR, "fontWeight": "bold"})
    elif nic > 3:
        return html.Span(f"+{nic:.1f} bps (modest concession)",
                         style={"color": POS_CLR})
    elif nic > -3:
        return html.Span(f"{nic:+.1f} bps (at fair value)",
                         style={"color": WARN_CLR})
    else:
        return html.Span(f"{nic:+.1f} bps (inside fair value)",
                         style={"color": NEG_CLR})


# ── layout ─────────────────────────────────────────────────────────────────────

_dd = {"backgroundColor": "#1c1c35", "color": TEXT_CLR, "fontSize": "12px"}
_inp = {"backgroundColor": "#0d0d20", "color": TEXT_CLR,
        "border": f"1px solid {GRID_CLR}", "fontSize": "12px"}

_COMPS_COLS = [
    {"name": "Ticker",    "id": "ticker"},
    {"name": "Issuer",    "id": "issuer"},
    {"name": "Rating",    "id": "composite_rating"},
    {"name": "Country",   "id": "country_of_risk"},
    {"name": "Maturity",  "id": "maturity_bucket"},
    {"name": "Sprd Dur",  "id": "spread_duration"},
    {"name": "OAS",       "id": "oas"},
    {"name": "Z-Sprd",    "id": "z_spread"},
    {"name": "Yield %",   "id": "yield_pct"},
    {"name": "iTraxx",    "id": "spread_itraxx"},
    {"name": "Size (mm)", "id": "issue_size_mm"},
]

_lbl = lambda t: dbc.Label(t, style={"fontSize": "11px", "color": "#aabbcc",
                                      "marginBottom": "2px"})


def _form_col():
    return dbc.Card([
        dbc.CardHeader("New Issue Details",
                       style={"color": ACCENT, "fontSize": "13px", "fontWeight": "600",
                              "backgroundColor": "#16162a", "padding": "8px 14px"}),
        dbc.CardBody([
            # Issuer block
            html.P("Issuer", style={"color": ACCENT, "fontSize": "11px",
                                     "marginBottom": "6px", "fontWeight": "600"}),
            dbc.Row([
                dbc.Col([_lbl("Issuer Name"),
                         dbc.Input(id="ni-issuer", placeholder="e.g. BNP Paribas",
                                   size="sm", style=_inp)], width=12, className="mb-2"),
            ]),
            dbc.Row([
                dbc.Col([_lbl("Sector"),
                         dbc.Select(id="ni-sector", size="sm", style=_dd,
                                    options=[{"label": s, "value": s} for s in SECTORS])
                         ], width=6),
                dbc.Col([_lbl("Rating"),
                         dbc.Select(id="ni-rating", size="sm", style=_dd,
                                    options=[{"label": r, "value": r} for r in RATING_ORDER])
                         ], width=6),
            ], className="mb-2"),
            dbc.Row([
                dbc.Col([_lbl("Country of Risk"),
                         dbc.Select(id="ni-country", size="sm", style=_dd,
                                    options=[{"label": c, "value": c} for c in COUNTRIES])
                         ], width=7),
                dbc.Col([_lbl("Seniority"),
                         dbc.Select(id="ni-seniority", size="sm", style=_dd,
                                    options=[{"label": s, "value": s} for s in SENIORITIES])
                         ], width=5),
            ], className="mb-3"),
            html.Hr(style={"borderColor": GRID_CLR, "margin": "8px 0"}),

            # Bond details
            html.P("Bond Structure", style={"color": ACCENT, "fontSize": "11px",
                                             "marginBottom": "6px", "fontWeight": "600"}),
            dbc.Row([
                dbc.Col([_lbl("Tenor (yrs)"),
                         dbc.Input(id="ni-tenor", type="number", value=5, min=0.5,
                                   max=50, step=0.5, size="sm", style=_inp)], width=4),
                dbc.Col([_lbl("Currency"),
                         dbc.Select(id="ni-currency", size="sm", style=_dd,
                                    value="EUR",
                                    options=[{"label": c, "value": c} for c in CURRENCIES])
                         ], width=4),
                dbc.Col([_lbl("Size (mm)"),
                         dbc.Input(id="ni-size", type="number", placeholder="750",
                                   size="sm", style=_inp)], width=4),
            ], className="mb-2"),
            dbc.Row([
                dbc.Col([_lbl("Benchmark"),
                         dbc.Select(id="ni-benchmark", size="sm", style=_dd,
                                    value="MS",
                                    options=[{"label": b, "value": b} for b in BENCHMARKS])
                         ], width=5),
                dbc.Col([_lbl("Benchmark Yield (%)"),
                         dbc.Input(id="ni-bm-yield", type="number", placeholder="2.85",
                                   step=0.001, size="sm", style=_inp)], width=7),
            ], className="mb-3"),
            html.Hr(style={"borderColor": GRID_CLR, "margin": "8px 0"}),

            # Pricing
            html.P("Pricing / IPT", style={"color": ACCENT, "fontSize": "11px",
                                            "marginBottom": "6px", "fontWeight": "600"}),
            dbc.Row([
                dbc.Col([_lbl("IPT Spread (bps)"),
                         dbc.Input(id="ni-ipt-spread", type="number", placeholder="150",
                                   size="sm", style=_inp)], width=6),
                dbc.Col([_lbl("IPT Yield (%)"),
                         dbc.Input(id="ni-ipt-yield", type="number", placeholder="4.35",
                                   step=0.001, size="sm", style=_inp)], width=6),
            ], className="mb-2"),
            dbc.Row([
                dbc.Col([_lbl("Guidance (bps)"),
                         dbc.Input(id="ni-guidance", type="number",
                                   size="sm", style=_inp)], width=6),
                dbc.Col([_lbl("Final Price (bps)"),
                         dbc.Input(id="ni-final", type="number",
                                   size="sm", style=_inp)], width=6),
            ], className="mb-2"),
            dbc.Row([
                dbc.Col([_lbl("IPT Text (free)"),
                         dbc.Input(id="ni-ipt-text", placeholder="MS+150 area",
                                   size="sm", style=_inp)], width=12),
            ], className="mb-3"),
            dbc.Row([
                dbc.Col([_lbl("Comp Search Range (rating notches ±)"),
                         dbc.Input(id="ni-notches", type="number", value=2, min=0, max=5,
                                   size="sm", style=_inp)], width=7),
                dbc.Col([_lbl("Tenor Range (±yrs)"),
                         dbc.Input(id="ni-tenor-range", type="number", value=3, min=1,
                                   max=10, size="sm", style=_inp)], width=5),
            ], className="mb-3"),
            dbc.Button("Calculate Fair Value", id="ni-calc-btn",
                       color="info", size="sm", className="w-100"),
            html.Hr(style={"borderColor": GRID_CLR, "margin": "10px 0"}),
            dbc.Button("Save to Database", id="ni-save-btn",
                       color="secondary", outline=True, size="sm", className="w-100"),
            html.Div(id="ni-save-msg",
                     style={"fontSize": "11px", "color": POS_CLR, "marginTop": "6px"}),
        ], style={"padding": "12px"}),
    ], style={"backgroundColor": CARD_BG, "border": f"1px solid {GRID_CLR}"})


def _results_col():
    return html.Div([
        # Summary KPIs
        dbc.Row([
            dbc.Col(dbc.Card([
                dbc.CardBody([
                    html.P("Fair Value Spread", className="mb-0",
                           style={"fontSize": "10px", "color": "#aaa"}),
                    html.H4(id="ni-fv-badge", children="—",
                            style={"color": ACCENT, "fontSize": "20px",
                                   "marginBottom": "0"}),
                    html.Small("bps (from comps)", style={"color": "#888"}),
                ])
            ], style={"backgroundColor": "#16162a", "border": f"1px solid {GRID_CLR}",
                      "textAlign": "center"}), width=4),
            dbc.Col(dbc.Card([
                dbc.CardBody([
                    html.P("NIC vs Fair Value", className="mb-0",
                           style={"fontSize": "10px", "color": "#aaa"}),
                    html.Div(id="ni-nic-badge",
                             style={"fontSize": "14px", "marginTop": "4px"}),
                ])
            ], style={"backgroundColor": "#16162a", "border": f"1px solid {GRID_CLR}",
                      "textAlign": "center"}), width=5),
            dbc.Col(dbc.Card([
                dbc.CardBody([
                    html.P("Comps Found", className="mb-0",
                           style={"fontSize": "10px", "color": "#aaa"}),
                    html.H4(id="ni-comps-count", children="—",
                            style={"color": WARN_CLR, "fontSize": "20px",
                                   "marginBottom": "0"}),
                    html.Small("matching bonds", style={"color": "#888"}),
                ])
            ], style={"backgroundColor": "#16162a", "border": f"1px solid {GRID_CLR}",
                      "textAlign": "center"}), width=3),
        ], className="mb-3"),

        # Comp chart
        dbc.Card([
            dbc.CardHeader("Comparable Bonds — OAS vs Spread Duration",
                           style={"color": ACCENT, "fontSize": "12px",
                                  "backgroundColor": "#16162a", "padding": "6px 12px"}),
            dbc.CardBody(dcc.Graph(id="ni-comp-chart",
                                   config={"displayModeBar": False}),
                         style={"padding": "4px"}),
        ], style={"backgroundColor": CARD_BG, "border": f"1px solid {GRID_CLR}",
                  "marginBottom": "12px"}),

        # Comps table
        dbc.Card([
            dbc.CardHeader("Comparable Bonds Detail",
                           style={"color": ACCENT, "fontSize": "12px",
                                  "backgroundColor": "#16162a", "padding": "6px 12px"}),
            dbc.CardBody(
                dash_table.DataTable(
                    id="ni-comps-table",
                    columns=_COMPS_COLS,
                    data=[],
                    page_size=10,
                    sort_action="native",
                    style_cell={
                        "backgroundColor": CARD_BG,
                        "color": TEXT_CLR,
                        "border": f"1px solid {GRID_CLR}",
                        "fontSize": "11px",
                        "padding": "4px 8px",
                    },
                    style_header={
                        "backgroundColor": "#1c1c35",
                        "color": ACCENT,
                        "fontWeight": "600",
                        "fontSize": "11px",
                        "border": f"1px solid {GRID_CLR}",
                    },
                    style_table={"overflowX": "auto"},
                ),
                style={"padding": "4px"},
            ),
        ], style={"backgroundColor": CARD_BG, "border": f"1px solid {GRID_CLR}"}),
    ])


layout = html.Div([
    dbc.Row([
        dbc.Col(_form_col(), width=4),
        dbc.Col(_results_col(), width=8),
    ]),
    dcc.Store(id="ni-comps-store"),
])


# ── callbacks ──────────────────────────────────────────────────────────────────

@callback(
    Output("ni-comps-store", "data"),
    Output("ni-comps-table", "data"),
    Output("ni-comps-count", "children"),
    Output("ni-comp-chart", "figure"),
    Output("ni-fv-badge", "children"),
    Output("ni-nic-badge", "children"),
    Input("ni-calc-btn", "n_clicks"),
    State("ni-sector", "value"),
    State("ni-rating", "value"),
    State("ni-country", "value"),
    State("ni-currency", "value"),
    State("ni-tenor", "value"),
    State("ni-notches", "value"),
    State("ni-tenor-range", "value"),
    State("ni-ipt-spread", "value"),
    State("ni-ipt-yield", "value"),
    State("ni-issuer", "value"),
    State("ni-seniority", "value"),
    State("ni-benchmark", "value"),
    State("ni-bm-yield", "value"),
    prevent_initial_call=True,
)
def calculate(
    n_clicks, sector, rating, country, currency, tenor,
    notches, tenor_range, ipt_spread, ipt_yield,
    issuer, seniority, benchmark, bm_yield,
):
    session = get_session()
    try:
        df = get_bonds_df(session)
    finally:
        session.close()

    if df.empty:
        return None, [], "0", empty_figure("Load sample data first."), "—", "—"

    tenor = float(tenor or 5)
    notches = int(notches or 2)
    tenor_range = float(tenor_range or 3)

    # Build comparable set
    comps = df.copy()

    if sector:
        comps = comps[comps["sector"] == sector]
    if currency:
        comps = comps[comps["currency"] == currency]
    if rating:
        adj = get_adjacent_ratings(rating, notches)
        comps = comps[comps["composite_rating"].isin(adj)]

    # Tenor filter via spread_duration proxy
    approx_sd = min(tenor * 0.92, 12.0)
    sd_lo = max(0, approx_sd - tenor_range * 0.92)
    sd_hi = approx_sd + tenor_range * 0.92
    comps = comps[
        comps["spread_duration"].between(sd_lo, sd_hi, inclusive="both")
    ]

    comps = comps.dropna(subset=["oas", "spread_duration"])

    if comps.empty:
        # Widen search
        comps = df.copy()
        if sector:
            comps = comps[comps["sector"] == sector]

    count = len(comps)

    # Fair value
    fv = _fair_value(comps, tenor)
    ipt_s = float(ipt_spread) if ipt_spread else None
    nic = (ipt_s - fv) if (ipt_s is not None and fv is not None) else None

    fv_txt = f"{fv:.1f}" if fv is not None else "—"
    nic_badge = _nic_badge(nic)

    # Format table
    for col in ["yield_pct", "oas", "z_spread", "spread_benchmark",
                "spread_itraxx", "spread_duration"]:
        if col in comps.columns:
            comps[col] = comps[col].apply(
                lambda x: f"{x:.2f}" if pd.notna(x) else ""
            )

    # Chart
    fig = _comp_chart(comps, tenor, approx_sd, fv, ipt_s, issuer, sector)

    return comps.to_dict("records"), comps.to_dict("records"), str(count), fig, fv_txt, nic_badge


def _comp_chart(comps_df, tenor, new_sd, fv, ipt_spread, new_issuer, sector):
    fig = go.Figure()

    if comps_df.empty:
        return empty_figure("No comparables found.")

    def _num(v):
        try:
            return float(v)
        except Exception:
            return np.nan

    x_vals = comps_df["spread_duration"].apply(_num)
    y_vals = comps_df["oas"].apply(_num)
    mask = x_vals.notna() & y_vals.notna()
    x_arr = x_vals[mask].values
    y_arr = y_vals[mask].values

    col = sector_color(sector or "")

    # Comparable bonds
    fig.add_trace(go.Scatter(
        x=x_arr, y=y_arr,
        mode="markers+text",
        text=comps_df[mask]["ticker"].tolist(),
        textposition="top center",
        textfont=dict(size=8),
        name="Comps",
        marker=dict(color=col, size=9, opacity=0.85,
                    line=dict(width=0.5, color="#ffffff30")),
        hovertemplate=(
            "<b>%{text}</b><br>Sprd Dur: %{x:.1f}y<br>OAS: %{y:.0f}<extra></extra>"
        ),
    ))

    # Regression through comps
    if len(x_arr) >= 2:
        try:
            coeffs = np.polyfit(x_arr, y_arr, 1)
            xs = np.linspace(x_arr.min(), max(x_arr.max(), new_sd + 0.5), 60)
            fig.add_trace(go.Scatter(
                x=xs, y=np.polyval(coeffs, xs),
                mode="lines", name="Comp curve",
                line=dict(color="#ffffff40", width=1.5, dash="dot"),
                hoverinfo="skip",
            ))
        except Exception:
            pass

    # Fair value marker
    if fv is not None:
        fig.add_trace(go.Scatter(
            x=[new_sd], y=[fv],
            mode="markers",
            name="Fair Value",
            marker=dict(symbol="diamond", color=WARN_CLR, size=14,
                        line=dict(width=1.5, color="#fff")),
            hovertemplate=(
                f"<b>Fair Value</b><br>Sprd Dur: {new_sd:.1f}y<br>"
                f"FV OAS: {fv:.1f} bps<extra></extra>"
            ),
        ))

    # IPT marker
    if ipt_spread is not None:
        fig.add_trace(go.Scatter(
            x=[new_sd], y=[float(ipt_spread)],
            mode="markers",
            name=f"IPT: {float(ipt_spread):.0f}",
            marker=dict(symbol="star", color=ACCENT, size=16,
                        line=dict(width=1.5, color="#fff")),
            hovertemplate=(
                f"<b>{new_issuer or 'New Issue'} IPT</b><br>"
                f"Sprd Dur: {new_sd:.1f}y<br>"
                f"IPT: {float(ipt_spread):.0f} bps<extra></extra>"
            ),
        ))
        # NIC annotation
        if fv is not None:
            nic = float(ipt_spread) - fv
            fig.add_annotation(
                x=new_sd, y=float(ipt_spread),
                text=f" NIC: {nic:+.1f}",
                showarrow=False,
                font=dict(color=POS_CLR if nic > 0 else NEG_CLR, size=11),
                xshift=50,
            )

    layout = base_layout("", height=320)
    layout["xaxis"]["title"] = "Spread Duration (yrs)"
    layout["yaxis"]["title"] = "OAS (bps)"
    layout["margin"] = dict(l=55, r=20, t=20, b=40)
    fig.update_layout(**layout)
    return fig


# ── save to DB ─────────────────────────────────────────────────────────────────

@callback(
    Output("ni-save-msg", "children"),
    Input("ni-save-btn", "n_clicks"),
    State("ni-issuer", "value"),
    State("ni-sector", "value"),
    State("ni-rating", "value"),
    State("ni-country", "value"),
    State("ni-currency", "value"),
    State("ni-tenor", "value"),
    State("ni-seniority", "value"),
    State("ni-size", "value"),
    State("ni-benchmark", "value"),
    State("ni-ipt-spread", "value"),
    State("ni-ipt-yield", "value"),
    State("ni-guidance", "value"),
    State("ni-final", "value"),
    State("ni-fv-badge", "children"),
    State("ni-ipt-text", "value"),
    prevent_initial_call=True,
)
def save_new_issue(
    n, issuer, sector, rating, country, currency, tenor, seniority,
    size, benchmark, ipt_spread, ipt_yield, guidance, final,
    fv_txt, notes,
):
    if not n:
        return no_update

    session = get_session()
    try:
        fv = None
        try:
            fv = float(fv_txt) if fv_txt and fv_txt != "—" else None
        except Exception:
            pass

        ipt_s = float(ipt_spread) if ipt_spread else None
        nic = (ipt_s - fv) if (ipt_s is not None and fv is not None) else None

        rec = NewIssuePricing(
            issuer=issuer or "",
            sector=sector,
            rating=rating,
            country_of_risk=country,
            currency=currency or "EUR",
            tenor=float(tenor) if tenor else None,
            seniority=seniority,
            size_mm=float(size) if size else None,
            benchmark=benchmark,
            ipt_spread=ipt_s,
            ipt_yield=float(ipt_yield) if ipt_yield else None,
            guidance_spread=float(guidance) if guidance else None,
            final_spread=float(final) if final else None,
            fair_value_spread=fv,
            nic=nic,
            notes=notes or "",
            status="IPT" if not guidance else ("Guidance" if not final else "Priced"),
        )
        session.add(rec)
        session.commit()
        return "Saved to database."
    except Exception as e:
        session.rollback()
        return f"Error: {e}"
    finally:
        session.close()
