"""
Bond Relative Value Dashboard
Run: python app.py  →  http://localhost:8050
"""

import dash
import dash_bootstrap_components as dbc
from dash import dcc, html, Input, Output, callback

from database import init_db, get_session
from utils import CARD_BG, TEXT_CLR, GRID_CLR, ACCENT

# ── Dash app ───────────────────────────────────────────────────────────────────

app = dash.Dash(
    __name__,
    external_stylesheets=[
        dbc.themes.CYBORG,
        dbc.icons.BOOTSTRAP,
        "https://fonts.googleapis.com/css2?family=Inter:wght@400;600&display=swap",
    ],
    suppress_callback_exceptions=True,
    title="Bond RV Dashboard",
    meta_tags=[{"name": "viewport", "content": "width=device-width, initial-scale=1"}],
)

# Initialise DB (creates tables if absent)
init_db()

# Import tabs AFTER app is created so their @callback decorators register
import tabs.universe as universe_tab   # noqa: E402
import tabs.rv_curves as rv_tab        # noqa: E402
import tabs.curves_3d as c3d_tab       # noqa: E402
import tabs.new_issue as ni_tab        # noqa: E402

# ── layout ─────────────────────────────────────────────────────────────────────

_HEADER = dbc.Navbar(
    dbc.Container([
        dbc.Row([
            dbc.Col([
                html.Span("BOND  ", style={"color": ACCENT, "fontWeight": "700",
                                           "fontSize": "18px", "letterSpacing": "2px"}),
                html.Span("RELATIVE VALUE", style={"color": TEXT_CLR,
                                                    "fontWeight": "300",
                                                    "fontSize": "18px",
                                                    "letterSpacing": "1px"}),
                html.Span("  DASHBOARD", style={"color": "#666",
                                                  "fontSize": "12px",
                                                  "marginLeft": "4px"}),
            ], width="auto"),
            dbc.Col(html.Div(id="header-status"), width="auto",
                    className="ms-auto"),
        ], align="center", className="w-100"),
    ], fluid=True),
    color="#0a0a18",
    dark=True,
    className="mb-0 py-2 border-bottom",
    style={"borderColor": GRID_CLR + " !important"},
)

_TABS = dbc.Tabs(
    [
        dbc.Tab(universe_tab.layout,
                label="Bond Universe",
                tab_id="tab-universe",
                label_style={"fontSize": "12px"},
                active_label_style={"color": ACCENT, "fontSize": "12px"}),
        dbc.Tab(rv_tab.layout,
                label="Relative Value",
                tab_id="tab-rv",
                label_style={"fontSize": "12px"},
                active_label_style={"color": ACCENT, "fontSize": "12px"}),
        dbc.Tab(c3d_tab.layout,
                label="Curve History (3D)",
                tab_id="tab-3d",
                label_style={"fontSize": "12px"},
                active_label_style={"color": ACCENT, "fontSize": "12px"}),
        dbc.Tab(ni_tab.layout,
                label="New Issue Pricing",
                tab_id="tab-ni",
                label_style={"fontSize": "12px"},
                active_label_style={"color": ACCENT, "fontSize": "12px"}),
    ],
    id="main-tabs",
    active_tab="tab-universe",
    className="mt-0",
)

app.layout = html.Div(
    [
        _HEADER,
        dbc.Container(
            [
                _TABS,
                dcc.Interval(id="status-interval", interval=10_000, n_intervals=0),
            ],
            fluid=True,
            className="pt-3 px-3",
            style={"minHeight": "calc(100vh - 56px)",
                   "backgroundColor": "#0d0d14"},
        ),
    ],
    style={"backgroundColor": "#0d0d14", "minHeight": "100vh",
           "fontFamily": "Inter, Arial, sans-serif"},
)

# ── header status callback ─────────────────────────────────────────────────────

@callback(
    Output("header-status", "children"),
    Input("status-interval", "n_intervals"),
)
def update_status(_n):
    session = get_session()
    try:
        from database import Bond, BondPrice
        bonds = session.query(Bond).count()
        prices = session.query(BondPrice).count()
        last_date = None
        if prices:
            from sqlalchemy import func
            last_date = session.query(func.max(BondPrice.date)).scalar()
    finally:
        session.close()

    color = ACCENT if bonds > 0 else "#666"
    txt = (
        f"{bonds} bonds · {prices:,} price obs"
        + (f" · latest {last_date}" if last_date else "")
        if bonds > 0
        else "No data loaded"
    )
    return html.Span(
        [html.I(className="bi bi-database me-1"), txt],
        style={"fontSize": "11px", "color": color},
    )


# ── entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=8050, use_reloader=False)
