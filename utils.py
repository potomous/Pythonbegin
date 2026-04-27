from datetime import date

import pandas as pd

# ── colour palette ─────────────────────────────────────────────────────────────

CHART_BG  = "#0d0d14"
CARD_BG   = "#141428"
TEXT_CLR  = "#dde0f0"
GRID_CLR  = "#1e2040"
ACCENT    = "#00c8ff"
POS_CLR   = "#00e676"   # tight / positive
NEG_CLR   = "#ff1744"   # wide / negative
WARN_CLR  = "#ffab40"

SECTOR_COLORS = {
    "Financial":    "#1e90ff",
    "Corporate":    "#ffa040",
    "Sovereign":    "#00e676",
    "Supranational": "#da70d6",
    "Covered":      "#40e0d0",
    "EM Sovereign": "#ff6347",
    "EM Corporate": "#ff8c00",
    "Real Estate":  "#9370db",
}

RATING_ORDER = [
    "AAA", "AA+", "AA", "AA-",
    "A+",  "A",   "A-",
    "BBB+","BBB", "BBB-",
    "BB+", "BB",  "BB-",
    "B+",  "B",   "B-",
    "CCC",
]

MATURITY_BUCKETS = ["0-3Y", "3-5Y", "5-7Y", "7-10Y", "10-15Y", "15Y+"]

SECTORS = [
    "Financial", "Corporate", "Sovereign", "Supranational",
    "Covered", "EM Sovereign", "EM Corporate",
]

SUB_SECTORS = {
    "Financial":     ["Bank Senior", "Bank Sub / SNP", "Insurance", "Leasing"],
    "Corporate":     ["TMT", "Utilities", "Energy", "Automotive", "Industrials",
                      "Consumer", "Healthcare", "Real Estate"],
    "Sovereign":     ["Core", "Semi-Core", "Peripheral"],
    "Supranational": ["AAA Supra", "AA Supra"],
    "Covered":       ["Pfandbriefe", "Obligations Foncières", "RMBS"],
    "EM Sovereign":  ["LATAM", "EMEA", "Asia"],
    "EM Corporate":  ["EM Energy", "EM Financial", "EM TMT"],
}

SENIORITIES = [
    "Senior", "Senior Preferred", "Senior Non-Preferred",
    "Tier 2", "Additional Tier 1", "Covered",
]

BENCHMARKS = ["MS", "T+", "UKT+", "DBR+", "FRTR+", "OBL+"]

CURRENCIES = ["EUR", "USD", "GBP", "CHF", "SEK", "NOK"]

COUNTRIES = [
    "Germany", "France", "Netherlands", "Belgium", "Austria", "Finland",
    "Sweden", "Switzerland", "Norway", "Denmark",
    "Spain", "Italy", "Portugal",
    "UK", "Ireland",
    "Supranational",
    "USA", "Canada", "Japan", "Australia",
    "Brazil", "Mexico", "Colombia", "Chile",
    "South Africa", "Turkey", "Saudi Arabia", "UAE",
    "China", "India", "Indonesia",
]


# ── rating helpers ──────────────────────────────────────────────────────────────

def rating_to_numeric(rating: str) -> float:
    try:
        return RATING_ORDER.index(rating)
    except ValueError:
        return len(RATING_ORDER)


def numeric_to_rating(n: int) -> str:
    n = max(0, min(n, len(RATING_ORDER) - 1))
    return RATING_ORDER[int(n)]


def get_adjacent_ratings(rating: str, notches: int = 2) -> list[str]:
    idx = rating_to_numeric(rating)
    lo = max(0, idx - notches)
    hi = min(len(RATING_ORDER) - 1, idx + notches)
    return RATING_ORDER[lo : hi + 1]


# ── maturity helpers ────────────────────────────────────────────────────────────

def get_maturity_bucket(maturity_date, ref_date=None) -> str:
    if ref_date is None:
        ref_date = date.today()
    if isinstance(maturity_date, str):
        maturity_date = pd.to_datetime(maturity_date).date()
    if hasattr(maturity_date, "date"):
        maturity_date = maturity_date.date()
    years = (maturity_date - ref_date).days / 365.25
    if years <= 3:
        return "0-3Y"
    elif years <= 5:
        return "3-5Y"
    elif years <= 7:
        return "5-7Y"
    elif years <= 10:
        return "7-10Y"
    elif years <= 15:
        return "10-15Y"
    return "15Y+"


# ── country spread premia (bps vs Germany) ──────────────────────────────────────

COUNTRY_SPREAD = {
    "Germany": 0, "Netherlands": 6, "Finland": 4, "Austria": 10,
    "France": 18, "Belgium": 22, "Sweden": 12, "Denmark": 8,
    "Switzerland": 5, "Norway": 6,
    "Spain": 45, "Italy": 95, "Portugal": 55, "Ireland": 15,
    "UK": 28,
    "Supranational": -2,
    "USA": 5, "Canada": 8, "Japan": 2, "Australia": 12,
    "Brazil": 210, "Mexico": 130, "Colombia": 180, "Chile": 90,
    "South Africa": 195, "Turkey": 280, "Saudi Arabia": 80, "UAE": 70,
    "China": 60, "India": 110, "Indonesia": 120,
}

RATING_BASE_OAS = {
    "AAA": 12,  "AA+": 22,  "AA": 35,   "AA-": 52,
    "A+":  72,  "A":   92,  "A-":  115,
    "BBB+": 145, "BBB": 178, "BBB-": 225,
    "BB+": 305,  "BB":  385, "BB-":  470,
    "B+":  580,  "B":   700, "B-":   850,
    "CCC": 1100,
}


def sector_color(sector: str) -> str:
    for key, col in SECTOR_COLORS.items():
        if key.lower() in (sector or "").lower():
            return col
    return "#888888"


# ── plotly layout factory ───────────────────────────────────────────────────────

def base_layout(title="", height=420, **extra):
    layout = dict(
        title=dict(text=title, font=dict(color=TEXT_CLR, size=13), x=0.01),
        paper_bgcolor=CARD_BG,
        plot_bgcolor=CHART_BG,
        font=dict(color=TEXT_CLR, family="Inter, Arial, sans-serif", size=11),
        height=height,
        margin=dict(l=55, r=18, t=38, b=42),
        xaxis=dict(
            gridcolor=GRID_CLR, showgrid=True, zeroline=False,
            linecolor=GRID_CLR, tickfont=dict(size=10),
        ),
        yaxis=dict(
            gridcolor=GRID_CLR, showgrid=True, zeroline=False,
            linecolor=GRID_CLR, tickfont=dict(size=10),
        ),
        legend=dict(
            bgcolor="rgba(0,0,0,0)", bordercolor=GRID_CLR, borderwidth=1,
            font=dict(size=10),
        ),
        hoverlabel=dict(bgcolor=CARD_BG, font_size=11),
    )
    layout.update(extra)
    return layout


def empty_figure(message="No data available"):
    import plotly.graph_objects as go

    fig = go.Figure()
    fig.add_annotation(
        text=message,
        xref="paper", yref="paper",
        x=0.5, y=0.5, showarrow=False,
        font=dict(color=TEXT_CLR, size=14),
    )
    fig.update_layout(**base_layout(height=400))
    return fig
