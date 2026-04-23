"""European Bank Metrics Dashboard — Streamlit app."""

import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import numpy as np
import streamlit as st

from data_manager import (
    aggregate_annual,
    BANKS,
    COUNTRIES,
    COUNTRY_COLORS,
    METRIC_CATEGORIES,
    METRICS,
    generate_data,
)

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="European Bank Metrics",
    page_icon="🏦",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    .block-container { padding-top: 1.5rem; }
    .stTabs [data-baseweb="tab"] { font-size: 14px; font-weight: 600; }
    div[data-testid="metric-container"] { background:#f0f2f6; border-radius:8px; padding:10px; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Colour helpers
# ---------------------------------------------------------------------------

_PALETTE = px.colors.qualitative.Dark24
_BANK_LIST = list(BANKS.keys())
BANK_COLORS = {b: _PALETTE[i % len(_PALETTE)] for i, b in enumerate(_BANK_LIST)}


def bank_color_map(banks):
    return {b: BANK_COLORS[b] for b in banks}


# ---------------------------------------------------------------------------
# Data loading (cached)
# ---------------------------------------------------------------------------

@st.cache_data(show_spinner="Generating bank data…")
def load_data() -> pd.DataFrame:
    return generate_data()


# ---------------------------------------------------------------------------
# Sidebar controls → returns filter state
# ---------------------------------------------------------------------------

def render_sidebar(all_periods):
    st.sidebar.title("🏦 Filters")

    # Country filter
    sel_countries = st.sidebar.multiselect(
        "Country", COUNTRIES, default=COUNTRIES, key="countries"
    )

    # Bank filter
    avail_banks = [b for b, v in BANKS.items() if v["country"] in sel_countries]
    col1, col2 = st.sidebar.columns(2)
    if col1.button("All", key="sel_all"):
        st.session_state["banks"] = avail_banks
    if col2.button("None", key="sel_none"):
        st.session_state["banks"] = []

    sel_banks = st.sidebar.multiselect(
        "Banks", avail_banks,
        default=st.session_state.get("banks", avail_banks),
        key="banks",
    )

    # Time range
    st.sidebar.subheader("Time Range")
    c1, c2 = st.sidebar.columns(2)
    start = c1.selectbox("From", all_periods, index=0, key="start")
    end = c2.selectbox("To", all_periods, index=len(all_periods) - 1, key="end")

    # Periodicity
    periodicity = st.sidebar.radio(
        "Periodicity", ["Quarterly", "Annual"], horizontal=True, key="period_type"
    )

    # Primary metric
    st.sidebar.subheader("Primary Metric")
    cat = st.sidebar.selectbox("Category", ["All"] + METRIC_CATEGORIES, key="cat")
    avail_metrics = (
        list(METRICS.keys())
        if cat == "All"
        else [m for m, v in METRICS.items() if v["cat"] == cat]
    )
    metric = st.sidebar.selectbox("Metric", avail_metrics, key="metric")

    st.sidebar.markdown("---")
    st.sidebar.caption(
        "Data is approximate and based on publicly reported figures, EBA "
        "transparency exercises, and regulatory filings. Not for investment use."
    )

    return sel_banks, sel_countries, start, end, periodicity, metric


# ---------------------------------------------------------------------------
# Tab: Overview
# ---------------------------------------------------------------------------

def tab_overview(df: pd.DataFrame, metric: str, banks: list):
    latest = df["Period"].max()
    st.subheader(f"Latest Snapshot — {latest}")

    df_latest = df[(df["Period"] == latest) & (df["Bank"].isin(banks))]
    if df_latest.empty:
        st.warning("No data for selected banks.")
        return

    # KPI row for primary metric
    col_data = df_latest[df_latest["Metric"] == metric].set_index("Bank")["Value"]
    better = METRICS[metric]["better"]
    fmt = METRICS[metric]["fmt"]

    if not col_data.empty:
        best_bank = col_data.idxmax() if better == "high" else col_data.idxmin()
        worst_bank = col_data.idxmin() if better == "high" else col_data.idxmax()
        avg_val = col_data.mean()

        k1, k2, k3 = st.columns(3)
        k1.metric("Best performer", best_bank, f"{col_data[best_bank]:{fmt}}")
        k2.metric("Peer average", "", f"{avg_val:{fmt}}")
        k3.metric("Weakest performer", worst_bank, f"{col_data[worst_bank]:{fmt}}")

    st.markdown("---")

    # Full heatmap
    st.markdown("**Peer Heatmap — all metrics** (green = better relative to peers)")
    pivot = df_latest.pivot_table(index="Bank", columns="Metric", values="Value")
    pivot = pivot.reindex(columns=list(METRICS.keys()))

    # Normalise each column for colouring
    norm = pivot.copy()
    for col in norm.columns:
        lo, hi = norm[col].min(), norm[col].max()
        if hi > lo:
            n = (norm[col] - lo) / (hi - lo)
            if METRICS.get(col, {}).get("better") == "low":
                n = 1 - n
            norm[col] = n
        else:
            norm[col] = 0.5

    text_vals = pivot.applymap(lambda v: f"{v:.1f}" if pd.notna(v) else "")

    fig = go.Figure(
        go.Heatmap(
            z=norm.values,
            x=[c.replace(" (%)", "").replace(" (bn EUR)", "") for c in norm.columns],
            y=norm.index.tolist(),
            colorscale="RdYlGn",
            zmin=0, zmax=1,
            showscale=False,
            text=text_vals.values,
            texttemplate="%{text}",
            hovertemplate="<b>%{y}</b><br>%{x}: %{text}<extra></extra>",
        )
    )
    fig.update_layout(
        height=max(350, len(banks) * 35 + 120),
        margin=dict(l=10, r=10, t=30, b=80),
        xaxis_tickangle=-40,
    )
    st.plotly_chart(fig, use_container_width=True)


# ---------------------------------------------------------------------------
# Tab: Time Series
# ---------------------------------------------------------------------------

def tab_time_series(df: pd.DataFrame, metric: str, banks: list):
    st.subheader(f"Time Series — {metric}")

    df_m = df[(df["Metric"] == metric) & (df["Bank"].isin(banks))].copy()
    if df_m.empty:
        st.warning("No data.")
        return

    color_map = bank_color_map(banks)

    fig = px.line(
        df_m.sort_values("Period"),
        x="Period", y="Value", color="Bank",
        color_discrete_map=color_map,
        markers=True,
        labels={"Value": metric, "Period": ""},
        title=f"{metric} — {df_m['Period'].min()} to {df_m['Period'].max()}",
    )

    # Event annotations
    events = [
        ("2020-Q1", "COVID‑19", "rgba(220,50,50,0.15)"),
        ("2022-Q3", "ECB hikes", "rgba(50,100,220,0.12)"),
        ("2024-Q2", "ECB cuts", "rgba(50,180,80,0.12)"),
    ]
    for xval, label, color in events:
        if xval in df_m["Period"].values:
            fig.add_vline(
                x=xval, line_dash="dot", line_color="grey", line_width=1,
                annotation_text=label, annotation_position="top",
                annotation_font_size=10,
            )

    fig.update_layout(
        height=480,
        legend=dict(orientation="h", yanchor="bottom", y=-0.35),
        hovermode="x unified",
        xaxis_tickangle=-45,
    )
    st.plotly_chart(fig, use_container_width=True)

    # YoY change toggle
    if st.checkbox("Show year-on-year change", key="yoy"):
        df_yoy = (
            df_m.sort_values(["Bank", "Period"])
            .assign(YoY=lambda d: d.groupby("Bank")["Value"].pct_change(4) * 100)
            .dropna(subset=["YoY"])
        )
        fig2 = px.bar(
            df_yoy.sort_values("Period"),
            x="Period", y="YoY", color="Bank",
            color_discrete_map=color_map,
            barmode="group",
            labels={"YoY": "YoY change (%)", "Period": ""},
            title=f"{metric} — Year-on-Year Change (%)",
        )
        fig2.update_layout(height=380, xaxis_tickangle=-45)
        st.plotly_chart(fig2, use_container_width=True)


# ---------------------------------------------------------------------------
# Tab: Compare
# ---------------------------------------------------------------------------

def tab_compare(df: pd.DataFrame, metric: str, banks: list, all_periods: list):
    st.subheader(f"Cross-Sectional Comparison — {metric}")

    sel_period = st.selectbox(
        "Select period", all_periods, index=len(all_periods) - 1, key="cmp_period"
    )

    df_c = df[
        (df["Metric"] == metric)
        & (df["Bank"].isin(banks))
        & (df["Period"] == sel_period)
    ].copy()

    if df_c.empty:
        st.warning("No data for that period.")
        return

    better = METRICS[metric]["better"]
    df_c = df_c.sort_values("Value", ascending=(better == "low"))

    df_c["Color"] = df_c["Country"].map(COUNTRY_COLORS)

    fig = go.Figure(
        go.Bar(
            x=df_c["Value"],
            y=df_c["Bank"],
            orientation="h",
            marker_color=df_c["Color"],
            text=df_c["Value"].apply(lambda v: f"{v:{METRICS[metric]['fmt']}}"),
            textposition="outside",
            hovertemplate="<b>%{y}</b><br>" + metric + ": %{x:.2f}<extra></extra>",
        )
    )

    # Regulatory minimums for capital ratios
    minimums = {
        "CET1 Ratio (%)": 4.5,
        "Total Capital Ratio (%)": 8.0,
        "Leverage Ratio (%)": 3.0,
        "LCR (%)": 100.0,
        "NSFR (%)": 100.0,
    }
    if metric in minimums:
        fig.add_vline(
            x=minimums[metric], line_dash="dash", line_color="red",
            annotation_text=f"Min {minimums[metric]}%",
            annotation_position="top right",
        )

    fig.update_layout(
        title=f"{metric} — {sel_period}",
        height=max(350, len(banks) * 32 + 80),
        margin=dict(l=10, r=80, t=50, b=30),
        xaxis_title=metric,
        yaxis_title="",
    )
    st.plotly_chart(fig, use_container_width=True)

    # Country legend
    countries_shown = df_c["Country"].unique()
    legend_items = " &nbsp;&nbsp; ".join(
        f'<span style="color:{COUNTRY_COLORS[c]};font-weight:600">■ {c}</span>'
        for c in sorted(countries_shown)
    )
    st.markdown(legend_items, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Tab: Rankings
# ---------------------------------------------------------------------------

def tab_rankings(df: pd.DataFrame, metric: str, banks: list):
    st.subheader(f"Rankings — {metric}")

    latest = df["Period"].max()
    df_r = df[
        (df["Period"] == latest)
        & (df["Metric"] == metric)
        & (df["Bank"].isin(banks))
    ].copy()

    if df_r.empty:
        st.warning("No data.")
        return

    better = METRICS[metric]["better"]
    df_r = df_r.sort_values("Value", ascending=False).reset_index(drop=True)
    df_r["Rank"] = df_r.index + 1
    df_r["Color"] = df_r.apply(
        lambda r: ("#27ae60" if (better == "high") else "#c0392b")
        if r["Rank"] == 1
        else ("#c0392b" if (better == "high") else "#27ae60")
        if r["Rank"] == len(df_r)
        else "#95a5a6",
        axis=1,
    )

    fig = go.Figure(
        go.Bar(
            x=df_r["Bank"],
            y=df_r["Value"],
            marker_color=df_r["Color"],
            text=df_r["Value"].apply(lambda v: f"{v:{METRICS[metric]['fmt']}}"),
            textposition="outside",
            hovertemplate="<b>%{x}</b><br>Rank %{customdata}<br>"
            + metric
            + ": %{y:.2f}<extra></extra>",
            customdata=df_r["Rank"],
        )
    )
    fig.update_layout(
        title=f"{metric} — {latest} (ranked)",
        height=420,
        yaxis_title=metric,
        xaxis_tickangle=-30,
    )
    st.plotly_chart(fig, use_container_width=True)

    # Summary table
    st.dataframe(
        df_r[["Rank", "Bank", "Country", "Value"]]
        .rename(columns={"Value": metric})
        .set_index("Rank"),
        use_container_width=True,
    )


# ---------------------------------------------------------------------------
# Tab: Multi-metric scatter
# ---------------------------------------------------------------------------

def tab_scatter(df: pd.DataFrame, banks: list, all_metrics: list):
    st.subheader("Metric Scatter — compare two metrics")

    c1, c2 = st.columns(2)
    mx = c1.selectbox("X axis", all_metrics, index=0, key="sc_x")
    my = c2.selectbox("Y axis", all_metrics, index=3, key="sc_y")  # default ROE

    latest = df["Period"].max()
    sel_period = st.selectbox(
        "Period", sorted(df["Period"].unique()), index=len(df["Period"].unique()) - 1, key="sc_period"
    )

    df_x = df[(df["Metric"] == mx) & (df["Bank"].isin(banks)) & (df["Period"] == sel_period)][["Bank", "Country", "Value"]].rename(columns={"Value": "x"})
    df_y = df[(df["Metric"] == my) & (df["Bank"].isin(banks)) & (df["Period"] == sel_period)][["Bank", "Value"]].rename(columns={"Value": "y"})
    merged = df_x.merge(df_y, on="Bank")

    if merged.empty:
        st.warning("No data.")
        return

    fig = px.scatter(
        merged, x="x", y="y", color="Country",
        color_discrete_map=COUNTRY_COLORS,
        text="Bank",
        labels={"x": mx, "y": my},
        title=f"{mx} vs {my} — {sel_period}",
    )
    fig.update_traces(textposition="top center", marker_size=12)
    fig.update_layout(height=500)
    st.plotly_chart(fig, use_container_width=True)


# ---------------------------------------------------------------------------
# Tab: Data table
# ---------------------------------------------------------------------------

def tab_data(df: pd.DataFrame, banks: list):
    st.subheader("Raw Data")

    sel_metrics = st.multiselect(
        "Metrics", list(METRICS.keys()), default=list(METRICS.keys())[:6], key="dt_metrics"
    )

    df_d = df[(df["Bank"].isin(banks)) & (df["Metric"].isin(sel_metrics))].copy()

    pivot = df_d.pivot_table(
        index=["Bank", "Country", "Period"], columns="Metric", values="Value"
    ).reset_index()
    pivot = pivot.sort_values(["Bank", "Period"])

    st.dataframe(pivot, use_container_width=True, height=420)

    csv = pivot.to_csv(index=False).encode()
    st.download_button(
        "⬇ Download CSV", csv, "european_bank_metrics.csv", "text/csv"
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    st.title("🏦 European Bank Metrics Dashboard")
    st.caption(
        "Compare capital, profitability, efficiency, asset quality, and liquidity "
        "metrics for 14 major European banks — Q1 2019 to Q4 2025."
    )

    df_raw = load_data()
    all_periods = sorted(df_raw["Period"].unique())

    sel_banks, sel_countries, start, end, periodicity, metric = render_sidebar(all_periods)

    if not sel_banks:
        st.info("Select at least one bank in the sidebar.")
        return

    # Filter by time range
    period_range = all_periods[all_periods.index(start): all_periods.index(end) + 1]
    df = df_raw[df_raw["Period"].isin(period_range)].copy()

    # Apply periodicity
    if periodicity == "Annual":
        df = aggregate_annual(df)

    all_periods_filtered = sorted(df["Period"].unique())

    # Tabs
    t1, t2, t3, t4, t5, t6 = st.tabs([
        "📊 Overview",
        "📈 Time Series",
        "📊 Compare",
        "🏆 Rankings",
        "🔵 Scatter",
        "📋 Data",
    ])

    with t1:
        tab_overview(df, metric, sel_banks)
    with t2:
        tab_time_series(df, metric, sel_banks)
    with t3:
        tab_compare(df, metric, sel_banks, all_periods_filtered)
    with t4:
        tab_rankings(df, metric, sel_banks)
    with t5:
        tab_scatter(df, sel_banks, list(METRICS.keys()))
    with t6:
        tab_data(df, sel_banks)


if __name__ == "__main__":
    main()
