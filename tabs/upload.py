"""Data Import tab — upload file, map columns to DB fields, preview, import."""

import base64
import io
from datetime import date

import pandas as pd
from dash import (
    ALL, Input, Output, State, callback, dash_table, dcc, html, no_update,
)
import dash_bootstrap_components as dbc

from database import Bond, BondPrice, get_session, get_bonds_df
from utils import (
    CARD_BG, TEXT_CLR, GRID_CLR, ACCENT, POS_CLR, NEG_CLR, WARN_CLR,
    get_maturity_bucket,
)

# ── DB field definitions ───────────────────────────────────────────────────────
# Each entry: label, required, table, dtype

BOND_FIELDS = {
    "isin":             ("ISIN",             True,  "str"),
    "ticker":           ("Ticker",           False, "str"),
    "issuer":           ("Issuer",           True,  "str"),
    "sector":           ("Sector",           False, "str"),
    "sub_sector":       ("Sub-Sector",       False, "str"),
    "composite_rating": ("Rating",           False, "str"),
    "country_of_risk":  ("Country of Risk",  False, "str"),
    "currency":         ("Currency",         False, "str"),
    "coupon":           ("Coupon (%)",        False, "float"),
    "maturity_date":    ("Maturity Date",    False, "date"),
    "issue_date":       ("Issue Date",       False, "date"),
    "issue_size_mm":    ("Issue Size (mm)",  False, "float"),
    "seniority":        ("Seniority",        False, "str"),
}

PRICE_FIELDS = {
    "date":             ("Date",             True,  "date"),
    "price":            ("Price",            False, "float"),
    "yield_pct":        ("Yield (%)",        False, "float"),
    "oas":              ("OAS (bps)",        False, "float"),
    "z_spread":         ("Z-Spread (bps)",   False, "float"),
    "spread_benchmark": ("Benchmark Spread", False, "float"),
    "spread_itraxx":    ("iTraxx Spread",    False, "float"),
    "spread_cdx":       ("CDX Spread",       False, "float"),
    "spread_duration":  ("Spread Duration",  False, "float"),
    "country_spread":   ("Country Spread",   False, "float"),
}

ALL_FIELDS = {**BOND_FIELDS, **PRICE_FIELDS}

# Common aliases: lower-stripped source column → db field
ALIASES: dict[str, str] = {
    # ISIN
    "isin": "isin", "bond_isin": "isin", "identifier": "isin", "bond_id": "isin",
    "security_id": "isin",
    # Ticker
    "ticker": "ticker", "bbg": "ticker", "bloomberg": "ticker",
    "bbg_ticker": "ticker", "symbol": "ticker",
    # Issuer
    "issuer": "issuer", "name": "issuer", "company": "issuer",
    "issuer_name": "issuer", "entity": "issuer",
    # Sector
    "sector": "sector", "industry": "sector", "asset_class": "sector",
    # Sub-sector
    "sub_sector": "sub_sector", "sub-sector": "sub_sector",
    "industry_group": "sub_sector", "subsector": "sub_sector",
    # Rating
    "rating": "composite_rating", "composite_rating": "composite_rating",
    "credit_rating": "composite_rating", "rtg": "composite_rating",
    "sp": "composite_rating", "s&p": "composite_rating",
    "moodys": "composite_rating", "fitch": "composite_rating",
    # Country
    "country": "country_of_risk", "country_of_risk": "country_of_risk",
    "cor": "country_of_risk", "risk_country": "country_of_risk",
    "domicile": "country_of_risk",
    # Currency
    "currency": "currency", "ccy": "currency", "curr": "currency",
    "denomination": "currency",
    # Coupon
    "coupon": "coupon", "cpn": "coupon", "coupon_rate": "coupon",
    "coupon_pct": "coupon", "rate": "coupon",
    # Maturity
    "maturity": "maturity_date", "maturity_date": "maturity_date",
    "mat": "maturity_date", "mat_date": "maturity_date",
    "expiry": "maturity_date", "redemption_date": "maturity_date",
    # Issue date
    "issue_date": "issue_date", "settlement": "issue_date",
    "settlement_date": "issue_date", "dated_date": "issue_date",
    # Size
    "size": "issue_size_mm", "issue_size_mm": "issue_size_mm",
    "amount": "issue_size_mm", "notional": "issue_size_mm",
    "face_value": "issue_size_mm", "issue_amount": "issue_size_mm",
    "outstanding": "issue_size_mm",
    # Seniority
    "seniority": "seniority", "rank": "seniority", "priority": "seniority",
    "debt_type": "seniority", "tier": "seniority",
    # Date (price)
    "date": "date", "price_date": "date", "as_of": "date",
    "asof": "date", "val_date": "date", "pricing_date": "date",
    "trade_date": "date",
    # Price
    "price": "price", "px": "price", "clean_price": "price",
    "mid": "price", "mid_price": "price", "close": "price",
    # Yield
    "yield": "yield_pct", "yield_pct": "yield_pct", "ytm": "yield_pct",
    "yield_to_maturity": "yield_pct", "yld": "yield_pct",
    # OAS
    "oas": "oas", "option_adjusted_spread": "oas", "oas_bps": "oas",
    # Z-spread
    "z_spread": "z_spread", "zspread": "z_spread", "z-spread": "z_spread",
    "z_sprd": "z_spread",
    # BM spread
    "spread": "spread_benchmark", "bm_spread": "spread_benchmark",
    "benchmark_spread": "spread_benchmark", "govt_spread": "spread_benchmark",
    "asw": "spread_benchmark", "asset_swap": "spread_benchmark",
    # iTraxx
    "itraxx": "spread_itraxx", "itraxx_spread": "spread_itraxx",
    "cdsitraxx": "spread_itraxx",
    # CDX
    "cdx": "spread_cdx", "cdx_spread": "spread_cdx", "cdx_ig": "spread_cdx",
    # Spread duration
    "spread_duration": "spread_duration", "sdur": "spread_duration",
    "dur": "spread_duration", "modified_duration": "spread_duration",
    "dv01": "spread_duration",
    # Country spread
    "country_spread": "country_spread", "sovereign_spread": "country_spread",
    "em_spread": "country_spread",
}


def _normalise(col: str) -> str:
    return col.lower().strip().replace(" ", "_").replace("-", "_").replace("/", "_")


def auto_map(file_cols: list[str]) -> dict[str, str]:
    """Return {db_field: file_col} best-guess from aliases + exact match."""
    norm = {_normalise(c): c for c in file_cols}
    mapping: dict[str, str] = {}
    for nc, orig in norm.items():
        db_field = ALIASES.get(nc)
        if db_field and db_field not in mapping:
            mapping[db_field] = orig
    return mapping


# ── shared styles ──────────────────────────────────────────────────────────────

_DD_STYLE = {"backgroundColor": "#1c1c35", "color": TEXT_CLR, "fontSize": "11px",
             "border": f"1px solid {GRID_CLR}", "minWidth": "160px"}
_REQ_BADGE = dbc.Badge("required", color="danger", className="ms-1",
                        style={"fontSize": "9px", "verticalAlign": "middle"})
_OPT_BADGE = dbc.Badge("optional", color="secondary", className="ms-1",
                        style={"fontSize": "9px", "verticalAlign": "middle",
                               "opacity": "0.6"})

_TH = {"backgroundColor": "#16162a", "color": ACCENT, "fontWeight": "600",
       "fontSize": "11px", "padding": "6px 10px",
       "border": f"1px solid {GRID_CLR}", "textAlign": "left"}
_TD = {"backgroundColor": CARD_BG, "color": TEXT_CLR, "fontSize": "11px",
       "padding": "5px 10px", "border": f"1px solid {GRID_CLR}",
       "verticalAlign": "middle"}


def _section_header(title: str, subtitle: str = ""):
    return html.Tr([
        html.Td(
            [html.Span(title, style={"color": ACCENT, "fontWeight": "700",
                                      "fontSize": "12px"}),
             html.Span(f"  {subtitle}", style={"color": "#666", "fontSize": "10px"})],
            colSpan=4,
            style={"backgroundColor": "#0d0d1e", "padding": "8px 10px",
                   "border": f"1px solid {GRID_CLR}"},
        )
    ])


def _mapping_row(db_key: str, label: str, required: bool,
                 col_options: list[dict], auto_val, sample_val: str):
    req_badge = _REQ_BADGE if required else _OPT_BADGE
    opts = [{"label": "— not mapped —", "value": ""}] + col_options
    return html.Tr([
        html.Td([
            html.Span(label, style={"fontWeight": "600" if required else "400"}),
            req_badge,
            html.Br(),
            html.Small(db_key, style={"color": "#555", "fontFamily": "monospace",
                                       "fontSize": "9px"}),
        ], style=_TD),
        html.Td(
            dbc.Select(
                id={"type": "map-dd", "field": db_key},
                options=opts,
                value=auto_val or "",
                style=_DD_STYLE,
            ),
            style=_TD,
        ),
        html.Td(
            html.Span(sample_val or "—",
                      style={"color": "#aaa", "fontFamily": "monospace",
                             "fontSize": "10px"}),
            style=_TD,
        ),
    ])


def _build_mapping_table(file_cols: list[str],
                          mapping: dict[str, str],
                          preview_rows: list[dict]) -> html.Div:
    opts = [{"label": c, "value": c} for c in file_cols]

    def sample(db_key: str) -> str:
        src = mapping.get(db_key, "")
        if not src or not preview_rows:
            return ""
        val = preview_rows[0].get(src, "")
        return str(val)[:30] if val is not None else ""

    bond_rows = []
    for db_key, (label, req, _dtype) in BOND_FIELDS.items():
        bond_rows.append(
            _mapping_row(db_key, label, req, opts,
                         mapping.get(db_key), sample(db_key))
        )

    price_rows = []
    for db_key, (label, req, _dtype) in PRICE_FIELDS.items():
        price_rows.append(
            _mapping_row(db_key, label, req, opts,
                         mapping.get(db_key), sample(db_key))
        )

    table = html.Table([
        html.Thead(html.Tr([
            html.Th("Database Field", style=_TH),
            html.Th("Source Column", style=_TH),
            html.Th("Sample Value", style={**_TH, "color": "#888"}),
        ])),
        html.Tbody([
            _section_header("BOND REFERENCE DATA",
                             "→ bonds table (isin required)"),
            *bond_rows,
            _section_header("PRICE / SPREAD TIME SERIES",
                             "→ bond_prices table (date + isin required)"),
            *price_rows,
        ]),
    ], style={"width": "100%", "borderCollapse": "collapse"})

    return html.Div(table, style={"overflowX": "auto"})


# ── layout ─────────────────────────────────────────────────────────────────────

layout = html.Div([
    dcc.Store(id="upload-raw-store"),

    # Upload zone
    dbc.Row([
        dbc.Col(
            dcc.Upload(
                id="upload-file",
                children=html.Div([
                    html.I(className="bi bi-cloud-upload me-2",
                           style={"fontSize": "24px", "color": ACCENT}),
                    html.Div("Drag & Drop or click to select file",
                             style={"fontSize": "13px", "color": TEXT_CLR}),
                    html.Small("CSV or Excel (.xlsx / .xls)",
                               style={"color": "#666"}),
                ], style={"textAlign": "center", "padding": "12px 0"}),
                style={
                    "border": f"2px dashed {GRID_CLR}",
                    "borderRadius": "8px",
                    "padding": "16px",
                    "cursor": "pointer",
                    "backgroundColor": CARD_BG,
                    "transition": "border-color 0.2s",
                },
                multiple=False,
            ),
            width=12,
        ),
    ], className="mb-3"),

    # File info bar (hidden until upload)
    html.Div(id="upload-file-info", style={"display": "none"},
             className="mb-3"),

    # Mapping table (hidden until upload)
    dbc.Card([
        dbc.CardHeader(
            dbc.Row([
                dbc.Col(html.Span("Column Mapping",
                                   style={"color": ACCENT, "fontWeight": "600",
                                          "fontSize": "13px"}), width="auto"),
                dbc.Col(
                    dbc.Button("Reset to Auto-Map", id="reset-mapping-btn",
                               size="sm", color="secondary", outline=True,
                               style={"fontSize": "11px"}),
                    width="auto", className="ms-auto",
                ),
            ], align="center"),
            style={"backgroundColor": "#16162a", "padding": "8px 14px"},
        ),
        dbc.CardBody(
            html.Div(id="upload-mapping-container",
                     children=html.P("Upload a file to begin mapping.",
                                      style={"color": "#555", "fontSize": "12px"})),
            style={"padding": "8px"},
        ),
    ], id="mapping-card",
       style={"backgroundColor": CARD_BG, "border": f"1px solid {GRID_CLR}",
              "display": "none"},
       className="mb-3"),

    # Import controls + status
    html.Div(id="import-controls-row", style={"display": "none"},
             children=dbc.Row([
                 dbc.Col(
                     dbc.Button("Import Data", id="import-btn",
                                color="info", size="sm",
                                style={"minWidth": "120px"}),
                     width="auto",
                 ),
                 dbc.Col(
                     html.Div(id="import-status",
                              style={"fontSize": "12px", "paddingTop": "4px"}),
                     width="auto",
                 ),
             ], align="center", className="mb-3")),

    # Preview section
    dbc.Card([
        dbc.CardHeader("Data Preview (first 10 rows, mapped columns)",
                        style={"color": ACCENT, "fontSize": "12px",
                               "backgroundColor": "#16162a", "padding": "6px 14px"}),
        dbc.CardBody(
            dash_table.DataTable(
                id="upload-preview-table",
                columns=[],
                data=[],
                page_size=10,
                style_cell={
                    "backgroundColor": CARD_BG,
                    "color": TEXT_CLR,
                    "border": f"1px solid {GRID_CLR}",
                    "fontSize": "11px",
                    "padding": "4px 8px",
                    "fontFamily": "Inter, monospace",
                    "maxWidth": "160px",
                    "overflow": "hidden",
                    "textOverflow": "ellipsis",
                },
                style_header={
                    "backgroundColor": "#1c1c35",
                    "color": ACCENT,
                    "fontWeight": "600",
                    "fontSize": "11px",
                    "border": f"1px solid {GRID_CLR}",
                },
                style_table={"overflowX": "auto"},
                tooltip_delay=0,
                tooltip_duration=None,
            ),
            style={"padding": "4px"},
        ),
    ], id="preview-card",
       style={"backgroundColor": CARD_BG, "border": f"1px solid {GRID_CLR}",
              "display": "none"}),
])


# ── callbacks ──────────────────────────────────────────────────────────────────

def _parse_upload(contents: str, filename: str):
    """Decode upload and return (df, error_str)."""
    _ctype, b64 = contents.split(",", 1)
    raw = base64.b64decode(b64)
    try:
        if filename.lower().endswith((".xlsx", ".xls")):
            df = pd.read_excel(io.BytesIO(raw))
        else:
            try:
                df = pd.read_csv(io.StringIO(raw.decode("utf-8")))
            except UnicodeDecodeError:
                df = pd.read_csv(io.StringIO(raw.decode("latin-1")))
        return df, None
    except Exception as e:
        return None, str(e)


@callback(
    Output("upload-mapping-container", "children"),
    Output("upload-raw-store", "data"),
    Output("upload-file-info", "children"),
    Output("upload-file-info", "style"),
    Output("mapping-card", "style"),
    Output("import-controls-row", "style"),
    Output("preview-card", "style"),
    Input("upload-file", "contents"),
    State("upload-file", "filename"),
    prevent_initial_call=True,
)
def on_upload(contents, filename):
    if not contents:
        return no_update, no_update, no_update, no_update, no_update, no_update, no_update

    df, err = _parse_upload(contents, filename)
    if err:
        msg = dbc.Alert(f"Could not parse file: {err}", color="danger",
                        style={"fontSize": "12px"})
        return (msg, no_update, no_update,
                {"display": "none"}, {"display": "none"},
                {"display": "none"}, {"display": "none"})

    file_cols = df.columns.tolist()
    mapping = auto_map(file_cols)
    preview = df.head(3).astype(str).to_dict("records")

    mapping_ui = _build_mapping_table(file_cols, mapping, preview)

    mapped_count = len(mapping)
    info = dbc.Alert([
        html.I(className="bi bi-file-earmark-spreadsheet me-2"),
        html.Strong(filename),
        html.Span(f"   {len(df):,} rows · {len(file_cols)} columns detected · "
                  f"{mapped_count} fields auto-mapped",
                  style={"fontSize": "11px", "marginLeft": "8px"}),
    ], color="info", className="py-2 mb-0",
       style={"fontSize": "12px", "backgroundColor": "#0d2035",
              "border": f"1px solid {ACCENT}40", "color": TEXT_CLR})

    card_style = {"backgroundColor": CARD_BG, "border": f"1px solid {GRID_CLR}",
                  "display": "block", "marginBottom": "12px"}

    return (
        mapping_ui,
        {"contents": contents, "filename": filename,
         "cols": file_cols, "nrows": len(df)},
        info,
        {"display": "block", "marginBottom": "12px"},
        card_style,
        {"display": "block", "marginBottom": "12px"},
        {"backgroundColor": CARD_BG, "border": f"1px solid {GRID_CLR}",
         "display": "block"},
    )


@callback(
    Output("upload-mapping-container", "children", allow_duplicate=True),
    Output("upload-file-info", "children", allow_duplicate=True),
    Input("reset-mapping-btn", "n_clicks"),
    State("upload-raw-store", "data"),
    State("upload-file", "filename"),
    prevent_initial_call=True,
)
def reset_mapping(n_clicks, store, filename):
    if not n_clicks or not store:
        return no_update, no_update
    file_cols = store.get("cols", [])
    mapping = auto_map(file_cols)

    contents = store.get("contents")
    if contents:
        df, _ = _parse_upload(contents, filename or "")
        preview = df.head(3).astype(str).to_dict("records") if df is not None else []
    else:
        preview = []

    mapped_count = len(mapping)
    info = dbc.Alert([
        html.I(className="bi bi-file-earmark-spreadsheet me-2"),
        html.Strong(filename or ""),
        html.Span(f"   {store.get('nrows', 0):,} rows · {len(file_cols)} columns · "
                  f"{mapped_count} fields auto-mapped (reset)",
                  style={"fontSize": "11px", "marginLeft": "8px"}),
    ], color="info", className="py-2 mb-0",
       style={"fontSize": "12px", "backgroundColor": "#0d2035",
              "border": f"1px solid {ACCENT}40", "color": TEXT_CLR})

    return _build_mapping_table(file_cols, mapping, preview), info


@callback(
    Output("upload-preview-table", "data"),
    Output("upload-preview-table", "columns"),
    Output("upload-preview-table", "tooltip_data"),
    Input({"type": "map-dd", "field": ALL}, "value"),
    State({"type": "map-dd", "field": ALL}, "id"),
    State("upload-raw-store", "data"),
    State("upload-file", "filename"),
    prevent_initial_call=True,
)
def update_preview(dd_values, dd_ids, store, filename):
    if not store or not store.get("contents"):
        return [], [], []

    mapping = {
        id_dict["field"]: val
        for id_dict, val in zip(dd_ids, dd_values)
        if val
    }
    if not mapping:
        return [], [], []

    df, err = _parse_upload(store["contents"], filename or "")
    if err or df is None:
        return [], [], []

    # Build preview with only mapped columns, renamed to DB field names
    cols_present = [f for f, src in mapping.items() if src in df.columns]
    if not cols_present:
        return [], [], []

    rename = {mapping[f]: f for f in cols_present}
    preview_df = df[list(rename.keys())].rename(columns=rename).head(10)

    # Format columns header: show DB field name + original column in tooltip
    columns = []
    for db_f in preview_df.columns:
        label_info = ALL_FIELDS.get(db_f)
        lbl = label_info[0] if label_info else db_f
        columns.append({"name": lbl, "id": db_f})

    tooltip_data = [
        {col: {"value": str(val), "type": "markdown"}
         for col, val in row.items()}
        for row in preview_df.astype(str).to_dict("records")
    ]

    return preview_df.astype(str).to_dict("records"), columns, tooltip_data


# ── import ─────────────────────────────────────────────────────────────────────

@callback(
    Output("import-status", "children"),
    Input("import-btn", "n_clicks"),
    State({"type": "map-dd", "field": ALL}, "value"),
    State({"type": "map-dd", "field": ALL}, "id"),
    State("upload-raw-store", "data"),
    State("upload-file", "filename"),
    prevent_initial_call=True,
)
def do_import(n_clicks, dd_values, dd_ids, store, filename):
    if not n_clicks or not store or not store.get("contents"):
        return no_update

    mapping = {
        id_dict["field"]: val
        for id_dict, val in zip(dd_ids, dd_values)
        if val
    }

    # Validate minimums
    errors = []
    has_bond_data  = "isin" in mapping and "issuer" in mapping
    has_price_data = "isin" in mapping and "date" in mapping

    if not has_bond_data and not has_price_data:
        return dbc.Alert(
            "Map at least ISIN + Issuer (bond data) or ISIN + Date (price data).",
            color="warning", style={"fontSize": "12px"},
        )

    df, err = _parse_upload(store["contents"], filename or "")
    if err or df is None:
        return dbc.Alert(f"Could not re-parse file: {err}", color="danger",
                         style={"fontSize": "12px"})

    # Rename to DB field names
    rename = {src: db_f for db_f, src in mapping.items() if src in df.columns}
    df = df.rename(columns=rename)

    bonds_added = bonds_skipped = prices_added = prices_skipped = 0
    session = get_session()

    try:
        # ── bond static data ──────────────────────────────────────────────────
        if has_bond_data:
            bond_cols = [c for c in BOND_FIELDS if c in df.columns]
            bond_df = df[bond_cols].drop_duplicates(subset=["isin"])

            for _, row in bond_df.iterrows():
                isin = str(row.get("isin", "")).strip().upper()
                if not isin:
                    continue
                existing = session.query(Bond).filter_by(isin=isin).first()
                if existing:
                    bonds_skipped += 1
                    continue
                try:
                    mat_raw = row.get("maturity_date")
                    mat_date = (pd.to_datetime(mat_raw).date()
                                if mat_raw is not None and str(mat_raw) not in ("", "nan", "NaT")
                                else None)
                    iss_raw = row.get("issue_date")
                    iss_date = (pd.to_datetime(iss_raw).date()
                                if iss_raw is not None and str(iss_raw) not in ("", "nan", "NaT")
                                else None)
                    bond = Bond(
                        isin=isin,
                        ticker=_safe_str(row.get("ticker")),
                        issuer=_safe_str(row.get("issuer")) or isin,
                        sector=_safe_str(row.get("sector")),
                        sub_sector=_safe_str(row.get("sub_sector")),
                        composite_rating=_safe_str(row.get("composite_rating")),
                        country_of_risk=_safe_str(row.get("country_of_risk")),
                        currency=_safe_str(row.get("currency")) or "EUR",
                        coupon=_safe_float(row.get("coupon")),
                        maturity_date=mat_date,
                        maturity_bucket=get_maturity_bucket(mat_date) if mat_date else None,
                        issue_date=iss_date,
                        issue_size_mm=_safe_float(row.get("issue_size_mm")),
                        seniority=_safe_str(row.get("seniority")),
                    )
                    session.add(bond)
                    bonds_added += 1
                except Exception as e:
                    errors.append(f"Bond {isin}: {e}")

            session.flush()

        # ── price / spread time series ────────────────────────────────────────
        if has_price_data:
            price_cols = ["isin", "date"] + [
                c for c in PRICE_FIELDS if c != "date" and c in df.columns
            ]
            price_df = df[[c for c in price_cols if c in df.columns]].copy()

            for _, row in price_df.iterrows():
                isin = str(row.get("isin", "")).strip().upper()
                if not isin:
                    continue
                date_raw = row.get("date")
                try:
                    d = pd.to_datetime(date_raw).date()
                except Exception:
                    continue

                # Ensure bond exists
                if not session.query(Bond).filter_by(isin=isin).first():
                    if not has_bond_data:
                        errors.append(f"ISIN {isin} not in DB; skipping price row.")
                    prices_skipped += 1
                    continue

                # Upsert: delete existing (date, isin) then insert
                existing_bp = session.query(BondPrice).filter_by(
                    date=d, isin=isin
                ).first()
                if existing_bp:
                    prices_skipped += 1
                    continue

                try:
                    bp = BondPrice(
                        date=d,
                        isin=isin,
                        price=_safe_float(row.get("price")),
                        yield_pct=_safe_float(row.get("yield_pct")),
                        oas=_safe_float(row.get("oas")),
                        z_spread=_safe_float(row.get("z_spread")),
                        spread_benchmark=_safe_float(row.get("spread_benchmark")),
                        spread_itraxx=_safe_float(row.get("spread_itraxx")),
                        spread_cdx=_safe_float(row.get("spread_cdx")),
                        spread_duration=_safe_float(row.get("spread_duration")),
                        country_spread=_safe_float(row.get("country_spread")),
                    )
                    session.add(bp)
                    prices_added += 1
                except Exception as e:
                    errors.append(f"Price {isin}/{d}: {e}")

        session.commit()

        parts = []
        if bonds_added:
            parts.append(f"{bonds_added} bonds added")
        if bonds_skipped:
            parts.append(f"{bonds_skipped} bonds skipped (already exist)")
        if prices_added:
            parts.append(f"{prices_added} price rows added")
        if prices_skipped:
            parts.append(f"{prices_skipped} price rows skipped (duplicate date/isin)")
        summary = " · ".join(parts) if parts else "Nothing imported (check mapping)."

        color = "success" if (bonds_added + prices_added) > 0 else "warning"
        msg = dbc.Alert([
            html.Strong("Import complete. "),
            summary,
            (html.Div([html.Br(), html.Small("; ".join(errors[:5]),
                                              style={"color": WARN_CLR})])
             if errors else ""),
        ], color=color, style={"fontSize": "12px"})
        return msg

    except Exception as e:
        session.rollback()
        return dbc.Alert(f"Import failed: {e}", color="danger",
                         style={"fontSize": "12px"})
    finally:
        session.close()


# ── type coercion helpers ──────────────────────────────────────────────────────

def _safe_float(v) -> float | None:
    if v is None:
        return None
    try:
        f = float(v)
        return None if pd.isna(f) else f
    except (ValueError, TypeError):
        return None


def _safe_str(v) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    return None if s in ("", "nan", "None", "NaT") else s
