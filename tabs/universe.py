"""Bond Universe tab — filterable table + add-bond modal + CSV upload."""

import base64
import io
from datetime import date, datetime

import pandas as pd
from dash import (
    Input, Output, State, callback, dash_table, dcc, html, no_update,
)
import dash_bootstrap_components as dbc

from database import Bond, BondPrice, get_session, get_bonds_df
from utils import (
    SECTORS, RATING_ORDER, COUNTRIES, MATURITY_BUCKETS,
    SENIORITIES, CURRENCIES, SUB_SECTORS,
    CARD_BG, TEXT_CLR, GRID_CLR, ACCENT, POS_CLR, NEG_CLR,
    sector_color, get_maturity_bucket,
)

# ── layout ─────────────────────────────────────────────────────────────────────

def _filter_bar():
    dd_style = {"backgroundColor": "#1c1c35", "color": TEXT_CLR, "fontSize": "12px"}
    return dbc.Row([
        dbc.Col(dbc.Select(
            id="univ-sector-filter",
            options=[{"label": "All Sectors", "value": "ALL"}]
                   + [{"label": s, "value": s} for s in SECTORS],
            value="ALL", style=dd_style,
        ), width=2),
        dbc.Col(dbc.Select(
            id="univ-rating-filter",
            options=[{"label": "All Ratings", "value": "ALL"}]
                   + [{"label": r, "value": r} for r in RATING_ORDER],
            value="ALL", style=dd_style,
        ), width=2),
        dbc.Col(dbc.Select(
            id="univ-country-filter",
            options=[{"label": "All Countries", "value": "ALL"}]
                   + [{"label": c, "value": c} for c in COUNTRIES],
            value="ALL", style=dd_style,
        ), width=2),
        dbc.Col(dbc.Select(
            id="univ-bucket-filter",
            options=[{"label": "All Maturities", "value": "ALL"}]
                   + [{"label": b, "value": b} for b in MATURITY_BUCKETS],
            value="ALL", style=dd_style,
        ), width=2),
        dbc.Col(dbc.Input(
            id="univ-search", placeholder="Search issuer / ticker…",
            type="text", debounce=True, size="sm",
            style={"backgroundColor": "#1c1c35", "color": TEXT_CLR,
                   "border": f"1px solid {GRID_CLR}", "fontSize": "12px"},
        ), width=2),
        dbc.Col([
            dbc.Button("+ Add Bond", id="open-add-modal-btn", size="sm",
                       color="info", outline=True, className="me-2"),
            dbc.Button("Load Sample Data", id="load-sample-btn", size="sm",
                       color="secondary", outline=True),
        ], width=2, className="d-flex align-items-center"),
    ], className="mb-3 g-2")


_TABLE_COLS = [
    {"name": "Ticker",    "id": "ticker"},
    {"name": "Issuer",    "id": "issuer"},
    {"name": "Sector",    "id": "sector"},
    {"name": "Rating",    "id": "composite_rating"},
    {"name": "Country",   "id": "country_of_risk"},
    {"name": "Maturity",  "id": "maturity_bucket"},
    {"name": "CCY",       "id": "currency"},
    {"name": "Cpn %",     "id": "coupon"},
    {"name": "Size (mm)", "id": "issue_size_mm"},
    {"name": "Px",        "id": "price"},
    {"name": "Yld %",     "id": "yield_pct"},
    {"name": "OAS",       "id": "oas"},
    {"name": "Z-Sprd",    "id": "z_spread"},
    {"name": "BM Sprd",   "id": "spread_benchmark"},
    {"name": "iTraxx",    "id": "spread_itraxx"},
    {"name": "CDX",       "id": "spread_cdx"},
    {"name": "Sprd Dur",  "id": "spread_duration"},
    {"name": "Ctry Sprd", "id": "country_spread"},
    {"name": "Date",      "id": "price_date"},
]

_TABLE_STYLE_CELL = {
    "backgroundColor": CARD_BG,
    "color": TEXT_CLR,
    "border": f"1px solid {GRID_CLR}",
    "fontSize": "11px",
    "padding": "4px 8px",
    "fontFamily": "Inter, Arial, monospace",
}

_TABLE_STYLE_HEADER = {
    "backgroundColor": "#1c1c35",
    "color": ACCENT,
    "fontWeight": "600",
    "fontSize": "11px",
    "border": f"1px solid {GRID_CLR}",
    "padding": "6px 8px",
}


def _bond_table():
    return dash_table.DataTable(
        id="bond-table",
        columns=_TABLE_COLS,
        data=[],
        page_size=20,
        sort_action="native",
        filter_action="native",
        row_selectable="single",
        style_cell=_TABLE_STYLE_CELL,
        style_header=_TABLE_STYLE_HEADER,
        style_table={"overflowX": "auto"},
        style_data_conditional=[
            {"if": {"state": "selected"},
             "backgroundColor": "#1e2a4a", "border": f"1px solid {ACCENT}"},
        ],
        tooltip_delay=0,
        tooltip_duration=None,
    )


def _add_bond_modal():
    lbl = lambda t: dbc.Label(t, style={"fontSize": "11px", "color": TEXT_CLR})
    inp = lambda **kw: dbc.Input(size="sm", style={"backgroundColor": "#0d0d20",
                                                    "color": TEXT_CLR,
                                                    "border": f"1px solid {GRID_CLR}",
                                                    "fontSize": "12px"}, **kw)
    sel = lambda opt, **kw: dbc.Select(options=opt, size="sm",
                                        style={"backgroundColor": "#0d0d20",
                                               "color": TEXT_CLR,
                                               "border": f"1px solid {GRID_CLR}",
                                               "fontSize": "12px"}, **kw)
    return dbc.Modal([
        dbc.ModalHeader(dbc.ModalTitle("Add Bond", style={"color": ACCENT}),
                        close_button=True),
        dbc.ModalBody([
            dbc.Row([
                dbc.Col([lbl("ISIN"), inp(id="ab-isin", placeholder="XS…")], width=4),
                dbc.Col([lbl("Ticker"), inp(id="ab-ticker")], width=4),
                dbc.Col([lbl("Issuer"), inp(id="ab-issuer")], width=4),
            ], className="mb-2"),
            dbc.Row([
                dbc.Col([lbl("Sector"), sel(
                    [{"label": s, "value": s} for s in SECTORS], id="ab-sector",
                )], width=3),
                dbc.Col([lbl("Sub-Sector"), sel(
                    [{"label": ss, "value": ss}
                     for ss in sum(SUB_SECTORS.values(), [])],
                    id="ab-sub-sector",
                )], width=3),
                dbc.Col([lbl("Rating"), sel(
                    [{"label": r, "value": r} for r in RATING_ORDER],
                    id="ab-rating",
                )], width=3),
                dbc.Col([lbl("Currency"), sel(
                    [{"label": c, "value": c} for c in CURRENCIES],
                    id="ab-currency", value="EUR",
                )], width=3),
            ], className="mb-2"),
            dbc.Row([
                dbc.Col([lbl("Country of Risk"), sel(
                    [{"label": c, "value": c} for c in COUNTRIES],
                    id="ab-country",
                )], width=4),
                dbc.Col([lbl("Seniority"), sel(
                    [{"label": s, "value": s} for s in SENIORITIES],
                    id="ab-seniority",
                )], width=4),
                dbc.Col([lbl("Coupon %"), inp(id="ab-coupon", type="number", step=0.125)], width=4),
            ], className="mb-2"),
            dbc.Row([
                dbc.Col([lbl("Maturity (YYYY-MM-DD)"), inp(id="ab-maturity", placeholder="2030-06-15")], width=4),
                dbc.Col([lbl("Issue Size (mm)"), inp(id="ab-size", type="number")], width=4),
                dbc.Col([lbl("Issue Date"), inp(id="ab-issue-date", placeholder="2023-06-15")], width=4),
            ], className="mb-2"),
            html.Hr(style={"borderColor": GRID_CLR}),
            html.P("Latest Price Data (optional)", style={"color": ACCENT, "fontSize": "11px", "marginBottom": "8px"}),
            dbc.Row([
                dbc.Col([lbl("OAS (bps)"), inp(id="ab-oas", type="number")], width=2),
                dbc.Col([lbl("Yield %"), inp(id="ab-yield", type="number", step=0.001)], width=2),
                dbc.Col([lbl("Z-Sprd"), inp(id="ab-zsprd", type="number")], width=2),
                dbc.Col([lbl("BM Sprd"), inp(id="ab-bmsprd", type="number")], width=2),
                dbc.Col([lbl("iTraxx"), inp(id="ab-itraxx", type="number")], width=2),
                dbc.Col([lbl("CDX"), inp(id="ab-cdx", type="number")], width=2),
            ], className="mb-2"),
            dbc.Row([
                dbc.Col([lbl("Sprd Duration"), inp(id="ab-sdur", type="number", step=0.01)], width=3),
                dbc.Col([lbl("Ctry Spread"), inp(id="ab-ctry", type="number")], width=3),
            ], className="mb-2"),
            html.Div(id="ab-error", style={"color": NEG_CLR, "fontSize": "11px"}),
        ]),
        dbc.ModalFooter([
            dbc.Button("Cancel", id="close-add-modal-btn", size="sm",
                       color="secondary", outline=True, className="me-2"),
            dbc.Button("Save Bond", id="save-bond-btn", size="sm", color="info"),
        ]),
    ], id="add-bond-modal", is_open=False, size="xl",
       backdrop="static", style={"color": TEXT_CLR})


layout = html.Div([
    html.Div(id="load-sample-toast"),
    _filter_bar(),
    dbc.Row([
        dbc.Col(html.Span(id="univ-count",
                          style={"fontSize": "11px", "color": "#aaa"}), width=6),
        dbc.Col(
            dcc.Upload(
                id="upload-bonds-csv",
                children=html.Span(["Drag & Drop or ", html.A("Select CSV")],
                                   style={"fontSize": "11px", "color": ACCENT}),
                style={"border": f"1px dashed {GRID_CLR}", "borderRadius": "4px",
                       "padding": "4px 12px", "cursor": "pointer",
                       "backgroundColor": CARD_BG},
                multiple=False,
            ), width=6, className="d-flex justify-content-end",
        ),
    ], className="mb-2"),
    html.Div(id="csv-upload-status",
             style={"fontSize": "11px", "color": POS_CLR, "marginBottom": "4px"}),
    _bond_table(),
    _add_bond_modal(),
    dcc.Store(id="universe-refresh", data=0),
])


# ── callbacks ──────────────────────────────────────────────────────────────────

@callback(
    Output("bond-table", "data"),
    Output("univ-count", "children"),
    Input("univ-sector-filter", "value"),
    Input("univ-rating-filter", "value"),
    Input("univ-country-filter", "value"),
    Input("univ-bucket-filter", "value"),
    Input("univ-search", "value"),
    Input("universe-refresh", "data"),
)
def update_table(sector, rating, country, bucket, search, _refresh):
    session = get_session()
    try:
        df = get_bonds_df(session)
    finally:
        session.close()

    if df.empty:
        return [], "No bonds in database. Click 'Load Sample Data' to begin."

    if sector and sector != "ALL":
        df = df[df["sector"] == sector]
    if rating and rating != "ALL":
        df = df[df["composite_rating"] == rating]
    if country and country != "ALL":
        df = df[df["country_of_risk"] == country]
    if bucket and bucket != "ALL":
        df = df[df["maturity_bucket"] == bucket]
    if search:
        mask = (
            df["issuer"].str.contains(search, case=False, na=False)
            | df["ticker"].str.contains(search, case=False, na=False)
            | df["isin"].str.contains(search, case=False, na=False)
        )
        df = df[mask]

    for col in ["yield_pct", "oas", "z_spread", "spread_benchmark",
                "spread_itraxx", "spread_cdx", "spread_duration",
                "country_spread", "price", "coupon"]:
        if col in df.columns:
            df[col] = df[col].apply(
                lambda x: f"{x:.2f}" if pd.notna(x) else ""
            )

    count_txt = f"{len(df)} bond{'s' if len(df) != 1 else ''} shown"
    return df.to_dict("records"), count_txt


@callback(
    Output("add-bond-modal", "is_open"),
    Output("ab-error", "children"),
    Output("universe-refresh", "data"),
    Input("open-add-modal-btn", "n_clicks"),
    Input("close-add-modal-btn", "n_clicks"),
    Input("save-bond-btn", "n_clicks"),
    State("add-bond-modal", "is_open"),
    State("ab-isin", "value"),
    State("ab-ticker", "value"),
    State("ab-issuer", "value"),
    State("ab-sector", "value"),
    State("ab-sub-sector", "value"),
    State("ab-rating", "value"),
    State("ab-currency", "value"),
    State("ab-country", "value"),
    State("ab-seniority", "value"),
    State("ab-coupon", "value"),
    State("ab-maturity", "value"),
    State("ab-size", "value"),
    State("ab-issue-date", "value"),
    State("ab-oas", "value"),
    State("ab-yield", "value"),
    State("ab-zsprd", "value"),
    State("ab-bmsprd", "value"),
    State("ab-itraxx", "value"),
    State("ab-cdx", "value"),
    State("ab-sdur", "value"),
    State("ab-ctry", "value"),
    State("universe-refresh", "data"),
    prevent_initial_call=True,
)
def handle_modal(open_n, close_n, save_n, is_open,
                 isin, ticker, issuer, sector, sub_sector, rating,
                 currency, country, seniority, coupon, maturity,
                 size, issue_dt,
                 oas, yld, zsprd, bmsprd, itraxx, cdx, sdur, ctry,
                 refresh_cnt):
    from dash import ctx
    triggered = ctx.triggered_id

    if triggered == "open-add-modal-btn":
        return True, "", refresh_cnt
    if triggered == "close-add-modal-btn":
        return False, "", refresh_cnt

    if triggered == "save-bond-btn":
        if not isin or not issuer:
            return True, "ISIN and Issuer are required.", refresh_cnt
        try:
            mat_date = datetime.strptime(maturity, "%Y-%m-%d").date() if maturity else None
        except ValueError:
            return True, "Maturity must be YYYY-MM-DD.", refresh_cnt

        session = get_session()
        try:
            bond = Bond(
                isin=isin.strip().upper(),
                ticker=(ticker or "").strip(),
                issuer=issuer.strip(),
                sector=sector,
                sub_sector=sub_sector,
                composite_rating=rating,
                country_of_risk=country,
                currency=currency or "EUR",
                coupon=float(coupon) if coupon else None,
                maturity_date=mat_date,
                maturity_bucket=get_maturity_bucket(mat_date) if mat_date else None,
                issue_date=(datetime.strptime(issue_dt, "%Y-%m-%d").date()
                            if issue_dt else None),
                issue_size_mm=float(size) if size else None,
                seniority=seniority,
            )
            session.add(bond)

            price_fields = [oas, yld, zsprd, bmsprd, itraxx, cdx, sdur, ctry]
            if any(f is not None for f in price_fields):
                bp = BondPrice(
                    date=date.today(),
                    isin=bond.isin,
                    oas=float(oas) if oas else None,
                    yield_pct=float(yld) if yld else None,
                    z_spread=float(zsprd) if zsprd else None,
                    spread_benchmark=float(bmsprd) if bmsprd else None,
                    spread_itraxx=float(itraxx) if itraxx else None,
                    spread_cdx=float(cdx) if cdx else None,
                    spread_duration=float(sdur) if sdur else None,
                    country_spread=float(ctry) if ctry else None,
                )
                session.add(bp)

            session.commit()
            return False, "", (refresh_cnt or 0) + 1
        except Exception as e:
            session.rollback()
            return True, f"Error: {e}", refresh_cnt
        finally:
            session.close()

    return is_open, "", refresh_cnt


@callback(
    Output("load-sample-toast", "children"),
    Output("universe-refresh", "data", allow_duplicate=True),
    Input("load-sample-btn", "n_clicks"),
    State("universe-refresh", "data"),
    prevent_initial_call=True,
)
def load_sample(n_clicks, refresh_cnt):
    if not n_clicks:
        return no_update, no_update
    from sample_data import load_sample_data
    load_sample_data()
    toast = dbc.Toast(
        "Sample data loaded successfully.",
        header="Done", is_open=True, duration=3000,
        icon="success", dismissable=True,
        style={"position": "fixed", "top": 60, "right": 20, "zIndex": 9999,
               "backgroundColor": CARD_BG, "color": TEXT_CLR},
    )
    return toast, (refresh_cnt or 0) + 1


@callback(
    Output("csv-upload-status", "children"),
    Output("universe-refresh", "data", allow_duplicate=True),
    Input("upload-bonds-csv", "contents"),
    State("upload-bonds-csv", "filename"),
    State("universe-refresh", "data"),
    prevent_initial_call=True,
)
def upload_csv(contents, filename, refresh_cnt):
    if not contents:
        return no_update, no_update

    _content_type, content_string = contents.split(",")
    decoded = base64.b64decode(content_string)
    try:
        df = pd.read_csv(io.StringIO(decoded.decode("utf-8")))
    except Exception as e:
        return f"Could not parse CSV: {e}", refresh_cnt

    required = {"isin", "issuer"}
    missing = required - set(df.columns.str.lower())
    if missing:
        return f"CSV missing required columns: {missing}", refresh_cnt

    df.columns = df.columns.str.lower().str.strip()
    session = get_session()
    added = 0
    errors = []
    try:
        for _, row in df.iterrows():
            isin = str(row.get("isin", "")).strip().upper()
            if not isin:
                continue
            existing = session.query(Bond).filter_by(isin=isin).first()
            if existing:
                continue
            try:
                mat_date = (pd.to_datetime(row["maturity_date"]).date()
                            if "maturity_date" in row and pd.notna(row["maturity_date"])
                            else None)
                bond = Bond(
                    isin=isin,
                    ticker=str(row.get("ticker", "")),
                    issuer=str(row.get("issuer", isin)),
                    sector=str(row.get("sector", "")),
                    sub_sector=str(row.get("sub_sector", "")),
                    composite_rating=str(row.get("composite_rating", row.get("rating", ""))),
                    country_of_risk=str(row.get("country_of_risk", row.get("country", ""))),
                    currency=str(row.get("currency", "EUR")),
                    coupon=float(row["coupon"]) if "coupon" in row and pd.notna(row["coupon"]) else None,
                    maturity_date=mat_date,
                    maturity_bucket=get_maturity_bucket(mat_date) if mat_date else None,
                    issue_size_mm=float(row["issue_size_mm"]) if "issue_size_mm" in row and pd.notna(row["issue_size_mm"]) else None,
                    seniority=str(row.get("seniority", "")),
                )
                session.add(bond)
                added += 1
            except Exception as e:
                errors.append(str(e))
        session.commit()
    except Exception as e:
        session.rollback()
        return f"DB error: {e}", refresh_cnt
    finally:
        session.close()

    msg = f"Imported {added} bonds from {filename}."
    if errors:
        msg += f" {len(errors)} row(s) skipped."
    return msg, (refresh_cnt or 0) + 1
