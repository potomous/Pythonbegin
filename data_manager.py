"""
European bank metrics data manager.
Provides quarterly seed data (Q1 2019 – Q4 2025) based on publicly reported figures.
"""

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Bank catalogue
# ---------------------------------------------------------------------------

BANKS = {
    "Deutsche Bank":    {"country": "Germany",        "code": "DBK"},
    "Commerzbank":      {"country": "Germany",        "code": "CBK"},
    "BNP Paribas":      {"country": "France",         "code": "BNP"},
    "Société Générale": {"country": "France",         "code": "GLE"},
    "Crédit Agricole":  {"country": "France",         "code": "ACA"},
    "Santander":        {"country": "Spain",          "code": "SAN"},
    "BBVA":             {"country": "Spain",          "code": "BBVA"},
    "UniCredit":        {"country": "Italy",          "code": "UCG"},
    "Intesa Sanpaolo":  {"country": "Italy",          "code": "ISP"},
    "ING Group":        {"country": "Netherlands",    "code": "ING"},
    "ABN AMRO":         {"country": "Netherlands",    "code": "ABN"},
    "Barclays":         {"country": "United Kingdom", "code": "BARC"},
    "UBS":              {"country": "Switzerland",    "code": "UBSG"},
    "Nordea":           {"country": "Finland",        "code": "NDA"},
}

COUNTRIES = sorted({v["country"] for v in BANKS.values()})

# ---------------------------------------------------------------------------
# Metric catalogue
# ---------------------------------------------------------------------------

METRICS = {
    "CET1 Ratio (%)":          {"cat": "Capital",       "better": "high", "fmt": ".1f", "flow": False, "desc": "Common Equity Tier 1 ratio"},
    "Total Capital Ratio (%)": {"cat": "Capital",       "better": "high", "fmt": ".1f", "flow": False, "desc": "Total regulatory capital ratio"},
    "Leverage Ratio (%)":      {"cat": "Capital",       "better": "high", "fmt": ".1f", "flow": False, "desc": "Tier 1 leverage ratio"},
    "ROE (%)":                 {"cat": "Profitability", "better": "high", "fmt": ".1f", "flow": False, "desc": "Return on equity (annualised)"},
    "ROA (%)":                 {"cat": "Profitability", "better": "high", "fmt": ".2f", "flow": False, "desc": "Return on assets (annualised)"},
    "NIM (%)":                 {"cat": "Profitability", "better": "high", "fmt": ".2f", "flow": False, "desc": "Net interest margin"},
    "Cost-to-Income (%)":      {"cat": "Efficiency",   "better": "low",  "fmt": ".1f", "flow": False, "desc": "Cost-to-income ratio"},
    "NPL Ratio (%)":           {"cat": "Asset Quality","better": "low",  "fmt": ".1f", "flow": False, "desc": "Non-performing loans ratio"},
    "LCR (%)":                 {"cat": "Liquidity",    "better": "high", "fmt": ".0f", "flow": False, "desc": "Liquidity coverage ratio (min 100%)"},
    "NSFR (%)":                {"cat": "Liquidity",    "better": "high", "fmt": ".0f", "flow": False, "desc": "Net stable funding ratio (min 100%)"},
    "Total Assets (bn EUR)":   {"cat": "Size",         "better": None,   "fmt": ".0f", "flow": False, "desc": "Total balance sheet assets"},
    "Net Revenue (bn EUR)":    {"cat": "Size",         "better": "high", "fmt": ".1f", "flow": True,  "desc": "Net banking income / total revenue"},
    "Net Profit (bn EUR)":     {"cat": "Size",         "better": "high", "fmt": ".1f", "flow": True,  "desc": "Net profit attributable to shareholders"},
}

METRIC_CATEGORIES = ["Capital", "Profitability", "Efficiency", "Asset Quality", "Liquidity", "Size"]

COUNTRY_COLORS = {
    "Germany":        "#1f4e79",
    "France":         "#0055A4",
    "Spain":          "#c60b1e",
    "Italy":          "#009246",
    "Netherlands":    "#FF6B00",
    "United Kingdom": "#012169",
    "Switzerland":    "#e4032e",
    "Finland":        "#003580",
}

# ---------------------------------------------------------------------------
# Seed parameters: (base_Q1_2019, annual_trend)
# ---------------------------------------------------------------------------

_P = {
    "Deutsche Bank": {
        "CET1 Ratio (%)":          (13.7,  0.20),
        "Total Capital Ratio (%)": (18.1,  0.15),
        "Leverage Ratio (%)":      ( 4.1,  0.05),
        "ROE (%)":                 ( 2.1,  0.82),
        "ROA (%)":                 ( 0.10, 0.04),
        "NIM (%)":                 ( 1.20, 0.02),
        "Cost-to-Income (%)":      (87.0, -2.60),
        "NPL Ratio (%)":           ( 3.2, -0.15),
        "LCR (%)":                 (141.0, 0.50),
        "NSFR (%)":                (118.0, 0.50),
        "Total Assets (bn EUR)":   (1340., 3.0),
        "Net Revenue (bn EUR)":    ( 6.3, -0.03),
        "Net Profit (bn EUR)":     ( 0.2,  0.42),
    },
    "Commerzbank": {
        "CET1 Ratio (%)":          (12.9,  0.25),
        "Total Capital Ratio (%)": (17.2,  0.20),
        "Leverage Ratio (%)":      ( 4.3,  0.05),
        "ROE (%)":                 ( 2.8,  0.42),
        "ROA (%)":                 ( 0.13, 0.02),
        "NIM (%)":                 ( 1.35, 0.02),
        "Cost-to-Income (%)":      (82.0, -1.80),
        "NPL Ratio (%)":           ( 1.8, -0.10),
        "LCR (%)":                 (154.0, 0.80),
        "NSFR (%)":                (112.0, 1.00),
        "Total Assets (bn EUR)":   (460.,  2.0),
        "Net Revenue (bn EUR)":    ( 2.2,  0.02),
        "Net Profit (bn EUR)":     ( 0.1,  0.15),
    },
    "BNP Paribas": {
        "CET1 Ratio (%)":          (11.7,  0.22),
        "Total Capital Ratio (%)": (15.5,  0.15),
        "Leverage Ratio (%)":      ( 4.4,  0.05),
        "ROE (%)":                 ( 9.8,  0.30),
        "ROA (%)":                 ( 0.45, 0.02),
        "NIM (%)":                 ( 1.10, 0.02),
        "Cost-to-Income (%)":      (66.5, -0.50),
        "NPL Ratio (%)":           ( 2.4, -0.10),
        "LCR (%)":                 (119.0, 2.00),
        "NSFR (%)":                (116.0, 1.00),
        "Total Assets (bn EUR)":   (2160., 95.0),
        "Net Revenue (bn EUR)":    (11.2,  0.30),
        "Net Profit (bn EUR)":     ( 2.0,  0.32),
    },
    "Société Générale": {
        "CET1 Ratio (%)":          (12.7,  0.18),
        "Total Capital Ratio (%)": (17.9,  0.12),
        "Leverage Ratio (%)":      ( 4.3,  0.04),
        "ROE (%)":                 ( 8.6,  0.08),
        "ROA (%)":                 ( 0.40, 0.01),
        "NIM (%)":                 ( 1.00, 0.02),
        "Cost-to-Income (%)":      (70.0, -0.30),
        "NPL Ratio (%)":           ( 3.2, -0.10),
        "LCR (%)":                 (138.0, 1.00),
        "NSFR (%)":                (114.0, 1.00),
        "Total Assets (bn EUR)":   (1360., -5.0),
        "Net Revenue (bn EUR)":    ( 6.2,  0.05),
        "Net Profit (bn EUR)":     ( 1.0,  0.15),
    },
    "Crédit Agricole": {
        "CET1 Ratio (%)":          (15.0,  0.10),
        "Total Capital Ratio (%)": (19.5,  0.10),
        "Leverage Ratio (%)":      ( 5.0,  0.04),
        "ROE (%)":                 (10.2,  0.40),
        "ROA (%)":                 ( 0.50, 0.02),
        "NIM (%)":                 ( 1.15, 0.03),
        "Cost-to-Income (%)":      (62.0, -0.50),
        "NPL Ratio (%)":           ( 2.8, -0.10),
        "LCR (%)":                 (128.0, 1.50),
        "NSFR (%)":                (120.0, 1.00),
        "Total Assets (bn EUR)":   (1820., 22.0),
        "Net Revenue (bn EUR)":    ( 9.5,  0.30),
        "Net Profit (bn EUR)":     ( 2.2,  0.30),
    },
    "Santander": {
        "CET1 Ratio (%)":          (11.3,  0.20),
        "Total Capital Ratio (%)": (15.3,  0.15),
        "Leverage Ratio (%)":      ( 5.2,  0.05),
        "ROE (%)":                 (11.3,  0.42),
        "ROA (%)":                 ( 0.65, 0.03),
        "NIM (%)":                 ( 2.80, 0.05),
        "Cost-to-Income (%)":      (49.0, -0.30),
        "NPL Ratio (%)":           ( 3.5, -0.10),
        "LCR (%)":                 (155.0, 1.00),
        "NSFR (%)":                (112.0, 1.00),
        "Total Assets (bn EUR)":   (1460., 50.0),
        "Net Revenue (bn EUR)":    (11.0,  0.50),
        "Net Profit (bn EUR)":     ( 2.8,  0.42),
    },
    "BBVA": {
        "CET1 Ratio (%)":          (11.6,  0.20),
        "Total Capital Ratio (%)": (15.6,  0.15),
        "Leverage Ratio (%)":      ( 6.0,  0.05),
        "ROE (%)":                 (11.2,  0.62),
        "ROA (%)":                 ( 0.75, 0.04),
        "NIM (%)":                 ( 2.90, 0.06),
        "Cost-to-Income (%)":      (49.5, -0.40),
        "NPL Ratio (%)":           ( 3.8, -0.12),
        "LCR (%)":                 (145.0, 1.00),
        "NSFR (%)":                (110.0, 1.00),
        "Total Assets (bn EUR)":   (690.,  15.0),
        "Net Revenue (bn EUR)":    ( 5.5,  0.30),
        "Net Profit (bn EUR)":     ( 1.6,  0.30),
    },
    "UniCredit": {
        "CET1 Ratio (%)":          (12.3,  0.48),
        "Total Capital Ratio (%)": (16.8,  0.38),
        "Leverage Ratio (%)":      ( 5.2,  0.10),
        "ROE (%)":                 ( 8.8,  1.15),
        "ROA (%)":                 ( 0.45, 0.06),
        "NIM (%)":                 ( 1.30, 0.08),
        "Cost-to-Income (%)":      (61.0, -2.60),
        "NPL Ratio (%)":           ( 7.0, -0.58),
        "LCR (%)":                 (130.0, 2.00),
        "NSFR (%)":                (113.0, 1.50),
        "Total Assets (bn EUR)":   (860.,  5.0),
        "Net Revenue (bn EUR)":    ( 5.0,  0.22),
        "Net Profit (bn EUR)":     ( 1.3,  0.52),
    },
    "Intesa Sanpaolo": {
        "CET1 Ratio (%)":          (14.3,  0.05),
        "Total Capital Ratio (%)": (18.2,  0.05),
        "Leverage Ratio (%)":      ( 6.1,  0.05),
        "ROE (%)":                 ( 8.7,  0.82),
        "ROA (%)":                 ( 0.55, 0.04),
        "NIM (%)":                 ( 1.70, 0.05),
        "Cost-to-Income (%)":      (51.0, -0.20),
        "NPL Ratio (%)":           ( 6.2, -0.58),
        "LCR (%)":                 (135.0, 1.50),
        "NSFR (%)":                (118.0, 1.50),
        "Total Assets (bn EUR)":   (820.,  10.0),
        "Net Revenue (bn EUR)":    ( 5.2,  0.25),
        "Net Profit (bn EUR)":     ( 1.3,  0.42),
    },
    "ING Group": {
        "CET1 Ratio (%)":          (14.6,  0.05),
        "Total Capital Ratio (%)": (17.9,  0.05),
        "Leverage Ratio (%)":      ( 4.0,  0.02),
        "ROE (%)":                 (10.5,  0.52),
        "ROA (%)":                 ( 0.55, 0.03),
        "NIM (%)":                 ( 1.40, 0.03),
        "Cost-to-Income (%)":      (56.0, -0.20),
        "NPL Ratio (%)":           ( 1.7, -0.05),
        "LCR (%)":                 (132.0, 1.00),
        "NSFR (%)":                (122.0, 1.00),
        "Total Assets (bn EUR)":   (960.,  10.0),
        "Net Revenue (bn EUR)":    ( 4.5,  0.10),
        "Net Profit (bn EUR)":     ( 1.7,  0.32),
    },
    "ABN AMRO": {
        "CET1 Ratio (%)":          (18.0, -0.30),
        "Total Capital Ratio (%)": (21.5, -0.25),
        "Leverage Ratio (%)":      ( 4.2,  0.00),
        "ROE (%)":                 (10.5,  0.02),
        "ROA (%)":                 ( 0.55, 0.00),
        "NIM (%)":                 ( 1.40, 0.02),
        "Cost-to-Income (%)":      (59.0,  0.00),
        "NPL Ratio (%)":           ( 3.1, -0.10),
        "LCR (%)":                 (194.0, -3.0),
        "NSFR (%)":                (117.0,  0.50),
        "Total Assets (bn EUR)":   (400.,  5.0),
        "Net Revenue (bn EUR)":    ( 1.9,  0.05),
        "Net Profit (bn EUR)":     ( 0.8,  0.05),
    },
    "Barclays": {
        "CET1 Ratio (%)":          (13.1,  0.10),
        "Total Capital Ratio (%)": (17.3,  0.08),
        "Leverage Ratio (%)":      ( 4.1,  0.02),
        "ROE (%)":                 ( 9.0,  0.22),
        "ROA (%)":                 ( 0.35, 0.01),
        "NIM (%)":                 ( 2.60, 0.05),
        "Cost-to-Income (%)":      (64.0, -0.20),
        "NPL Ratio (%)":           ( 2.4, -0.05),
        "LCR (%)":                 (158.0, 0.50),
        "NSFR (%)":                (121.0, 0.50),
        "Total Assets (bn EUR)":   (1390., 5.0),
        "Net Revenue (bn EUR)":    ( 5.8,  0.20),
        "Net Profit (bn EUR)":     ( 1.5,  0.25),
    },
    "UBS": {
        "CET1 Ratio (%)":          (13.8,  0.08),
        "Total Capital Ratio (%)": (20.1,  0.08),
        "Leverage Ratio (%)":      ( 4.7,  0.03),
        "ROE (%)":                 (14.0,  0.10),
        "ROA (%)":                 ( 0.65, 0.01),
        "NIM (%)":                 ( 0.90, 0.05),
        "Cost-to-Income (%)":      (82.0, -0.50),
        "NPL Ratio (%)":           ( 0.5, -0.02),
        "LCR (%)":                 (170.0, 1.00),
        "NSFR (%)":                (115.0, 0.50),
        "Total Assets (bn EUR)":   (940.,  10.0),
        "Net Revenue (bn EUR)":    ( 7.5,  0.30),
        "Net Profit (bn EUR)":     ( 4.5,  0.10),
    },
    "Nordea": {
        "CET1 Ratio (%)":          (16.0,  0.15),
        "Total Capital Ratio (%)": (20.3,  0.10),
        "Leverage Ratio (%)":      ( 5.2,  0.05),
        "ROE (%)":                 ( 9.6,  0.72),
        "ROA (%)":                 ( 0.55, 0.04),
        "NIM (%)":                 ( 1.10, 0.05),
        "Cost-to-Income (%)":      (52.0, -1.00),
        "NPL Ratio (%)":           ( 1.6, -0.05),
        "LCR (%)":                 (160.0, 1.00),
        "NSFR (%)":                (114.0, 0.50),
        "Total Assets (bn EUR)":   (580.,  10.0),
        "Net Revenue (bn EUR)":    ( 2.4,  0.10),
        "Net Profit (bn EUR)":     ( 1.1,  0.15),
    },
}

# Economic event impacts (at full intensity)
_COVID = {
    "CET1 Ratio (%)":          -0.30,
    "Total Capital Ratio (%)": -0.20,
    "Leverage Ratio (%)":      -0.15,
    "ROE (%)":                 -6.50,
    "ROA (%)":                 -0.30,
    "NIM (%)":                 -0.10,
    "Cost-to-Income (%)":       6.00,
    "NPL Ratio (%)":            1.20,
    "LCR (%)":                 18.00,
    "NSFR (%)":                 5.00,
    "Total Assets (bn EUR)":    0.00,
    "Net Revenue (bn EUR)":    -0.60,
    "Net Profit (bn EUR)":     -1.50,
}

_RATE = {
    "CET1 Ratio (%)":           0.20,
    "Total Capital Ratio (%)":  0.15,
    "Leverage Ratio (%)":       0.05,
    "ROE (%)":                  3.50,
    "ROA (%)":                  0.15,
    "NIM (%)":                  0.45,
    "Cost-to-Income (%)":      -5.00,
    "NPL Ratio (%)":            0.20,
    "LCR (%)":                 -8.00,
    "NSFR (%)":                -3.00,
    "Total Assets (bn EUR)":    0.00,
    "Net Revenue (bn EUR)":     0.70,
    "Net Profit (bn EUR)":      0.80,
}

_SENSITIVITY = {
    "Deutsche Bank":    {"covid": 1.1, "rate": 0.8},
    "Commerzbank":      {"covid": 1.0, "rate": 0.9},
    "BNP Paribas":      {"covid": 0.9, "rate": 0.9},
    "Société Générale": {"covid": 1.1, "rate": 0.8},
    "Crédit Agricole":  {"covid": 0.8, "rate": 0.9},
    "Santander":        {"covid": 1.2, "rate": 1.1},
    "BBVA":             {"covid": 1.2, "rate": 1.2},
    "UniCredit":        {"covid": 1.1, "rate": 1.2},
    "Intesa Sanpaolo":  {"covid": 1.0, "rate": 1.1},
    "ING Group":        {"covid": 0.9, "rate": 1.0},
    "ABN AMRO":         {"covid": 1.0, "rate": 0.9},
    "Barclays":         {"covid": 1.0, "rate": 1.1},
    "UBS":              {"covid": 0.7, "rate": 0.6},
    "Nordea":           {"covid": 0.8, "rate": 1.2},
}

_NOISE = {
    "CET1 Ratio (%)":          0.12,
    "Total Capital Ratio (%)": 0.18,
    "Leverage Ratio (%)":      0.04,
    "ROE (%)":                 0.35,
    "ROA (%)":                 0.015,
    "NIM (%)":                 0.025,
    "Cost-to-Income (%)":      0.70,
    "NPL Ratio (%)":           0.06,
    "LCR (%)":                 2.5,
    "NSFR (%)":                1.8,
    "Total Assets (bn EUR)":   8.0,
    "Net Revenue (bn EUR)":    0.12,
    "Net Profit (bn EUR)":     0.18,
}

_CLAMPS = {
    "CET1 Ratio (%)":          (8.0,  28.0),
    "Total Capital Ratio (%)": (12.0, 35.0),
    "Leverage Ratio (%)":      (3.0,  12.0),
    "ROE (%)":                 (-12., 30.0),
    "ROA (%)":                 (-0.5,  3.0),
    "NIM (%)":                 (0.3,   5.0),
    "Cost-to-Income (%)":      (30.0, 115.0),
    "NPL Ratio (%)":           (0.2,  15.0),
    "LCR (%)":                 (100., 280.0),
    "NSFR (%)":                (100., 170.0),
    "Total Assets (bn EUR)":   (50., 5000.0),
    "Net Revenue (bn EUR)":    (0.0,  60.0),
    "Net Profit (bn EUR)":     (-8.0, 40.0),
}


def _covid_factor(year: int, quarter: int) -> float:
    table = {
        (2020, 1): 0.40, (2020, 2): 1.00, (2020, 3): 0.65, (2020, 4): 0.35,
        (2021, 1): 0.20, (2021, 2): 0.15, (2021, 3): 0.10, (2021, 4): 0.05,
    }
    return table.get((year, quarter), 0.0)


def _rate_factor(year: int, quarter: int) -> float:
    table = {
        (2022, 3): 0.18, (2022, 4): 0.38,
        (2023, 1): 0.55, (2023, 2): 0.68, (2023, 3): 0.78, (2023, 4): 0.85,
        (2024, 1): 0.85, (2024, 2): 0.80, (2024, 3): 0.73, (2024, 4): 0.67,
        (2025, 1): 0.62, (2025, 2): 0.57, (2025, 3): 0.53, (2025, 4): 0.50,
    }
    return table.get((year, quarter), 0.0)


def generate_data() -> pd.DataFrame:
    quarters = [(y, q) for y in range(2019, 2026) for q in range(1, 5)]
    rows = []

    for bank, info in BANKS.items():
        params = _P[bank]
        sens = _SENSITIVITY[bank]
        rng = np.random.default_rng(abs(hash(bank)) % 2**31)

        for metric, (base, trend_yr) in params.items():
            lo, hi = _CLAMPS[metric]
            covid_mag = _COVID[metric] * sens["covid"]
            rate_mag = _RATE[metric] * sens["rate"]
            noise = _NOISE[metric]

            for year, quarter in quarters:
                t = (year - 2019) + (quarter - 1) / 4.0
                val = base + trend_yr * t
                val += covid_mag * _covid_factor(year, quarter)
                val += rate_mag * _rate_factor(year, quarter)
                val += rng.normal(0, noise)
                val = float(np.clip(val, lo, hi))

                rows.append({
                    "Bank": bank,
                    "Country": info["country"],
                    "Year": year,
                    "Quarter": quarter,
                    "Period": f"{year}-Q{quarter}",
                    "Metric": metric,
                    "Value": round(val, 3),
                })

    return pd.DataFrame(rows)


def aggregate_annual(df: pd.DataFrame) -> pd.DataFrame:
    flow_metrics = {m for m, v in METRICS.items() if v["flow"]}
    grp = ["Bank", "Country", "Year", "Metric"]

    df_flow = (
        df[df["Metric"].isin(flow_metrics)]
        .groupby(grp, as_index=False)["Value"].sum()
    )
    df_stock = (
        df[~df["Metric"].isin(flow_metrics)]
        .groupby(grp, as_index=False)["Value"].mean()
    )
    out = pd.concat([df_flow, df_stock], ignore_index=True)
    out["Period"] = out["Year"].astype(str)
    out["Quarter"] = 0
    return out
