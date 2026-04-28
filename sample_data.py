"""
Generate a realistic sample bond universe with 90 days of spread history.
Run: python sample_data.py
"""

from datetime import date, timedelta

import numpy as np
import pandas as pd

from database import (
    Bond, BondPrice, MarketCurve, init_db, get_session,
)
from utils import (
    RATING_BASE_OAS, COUNTRY_SPREAD, get_maturity_bucket,
)

RNG = np.random.default_rng(42)

# ── static bond definitions ────────────────────────────────────────────────────
BOND_DEFS = [
    # Financial — Bank Senior / SNP
    dict(isin="XS2100000001", ticker="BFCM 3¾ 29",  issuer="BNP Paribas",
         sector="Financial", sub_sector="Bank Senior",
         rating="A+",   country="France",      ccy="EUR", cpn=3.75,
         mat="2029-03-15", sz=1500, sen="Senior Preferred"),
    dict(isin="XS2100000002", ticker="SOCGEN 4 30",   issuer="Societe Generale",
         sector="Financial", sub_sector="Bank Senior",
         rating="A-",   country="France",      ccy="EUR", cpn=4.00,
         mat="2030-06-20", sz=1000, sen="Senior Preferred"),
    dict(isin="XS2100000003", ticker="DBK 4¼ SNP 31", issuer="Deutsche Bank",
         sector="Financial", sub_sector="Bank Sub / SNP",
         rating="BBB+", country="Germany",     ccy="EUR", cpn=4.25,
         mat="2031-09-10", sz=1250, sen="Senior Non-Preferred"),
    dict(isin="XS2100000004", ticker="HSBC 3⅞ 28",   issuer="HSBC Holdings",
         sector="Financial", sub_sector="Bank Senior",
         rating="A",    country="UK",          ccy="EUR", cpn=3.875,
         mat="2028-11-05", sz=2000, sen="Senior"),
    dict(isin="XS2100000005", ticker="SANTAN 4⅛ 32",  issuer="Banco Santander",
         sector="Financial", sub_sector="Bank Senior",
         rating="A-",   country="Spain",       ccy="EUR", cpn=4.125,
         mat="2032-04-18", sz=1000, sen="Senior Preferred"),
    dict(isin="XS2100000006", ticker="UNIMT 4½ SNP 30",issuer="UniCredit",
         sector="Financial", sub_sector="Bank Sub / SNP",
         rating="BBB",  country="Italy",       ccy="EUR", cpn=4.50,
         mat="2030-07-22", sz=1000, sen="Senior Non-Preferred"),
    dict(isin="XS2100000007", ticker="INTESA 4⅜ 29",  issuer="Intesa Sanpaolo",
         sector="Financial", sub_sector="Bank Senior",
         rating="BBB",  country="Italy",       ccy="EUR", cpn=4.375,
         mat="2029-10-14", sz=1250, sen="Senior Preferred"),
    dict(isin="XS2100000008", ticker="CSGN T2 34",    issuer="UBS Group",
         sector="Financial", sub_sector="Bank Sub / SNP",
         rating="BBB+", country="Switzerland", ccy="EUR", cpn=4.75,
         mat="2034-03-15", sz=750,  sen="Tier 2"),
    dict(isin="XS2100000009", ticker="BBVASM 4 31",   issuer="BBVA",
         sector="Financial", sub_sector="Bank Senior",
         rating="A-",   country="Spain",       ccy="EUR", cpn=4.00,
         mat="2031-06-10", sz=1000, sen="Senior Preferred"),
    # Insurance
    dict(isin="XS2100000010", ticker="AXA 3½ 31",     issuer="AXA SA",
         sector="Financial", sub_sector="Insurance",
         rating="A+",   country="France",      ccy="EUR", cpn=3.50,
         mat="2031-06-01", sz=1000, sen="Senior"),
    dict(isin="XS2100000011", ticker="ALVGR 3¼ 33",   issuer="Allianz SE",
         sector="Financial", sub_sector="Insurance",
         rating="AA",   country="Germany",     ccy="EUR", cpn=3.25,
         mat="2033-05-08", sz=500,  sen="Senior"),
    # Sovereign
    dict(isin="DE000BU22028", ticker="DBR 2.3 33",    issuer="Germany",
         sector="Sovereign", sub_sector="Core",
         rating="AAA",  country="Germany",     ccy="EUR", cpn=2.30,
         mat="2033-02-15", sz=25000, sen="Senior"),
    dict(isin="FR0014004Z75", ticker="FRTR 2¾ 32",    issuer="France",
         sector="Sovereign", sub_sector="Core",
         rating="AA-",  country="France",      ccy="EUR", cpn=2.75,
         mat="2032-11-25", sz=30000, sen="Senior"),
    dict(isin="IT0005518128", ticker="BTPS 4 35",     issuer="Italy",
         sector="Sovereign", sub_sector="Peripheral",
         rating="BBB",  country="Italy",       ccy="EUR", cpn=4.00,
         mat="2035-04-01", sz=35000, sen="Senior"),
    dict(isin="ES0000012H14", ticker="SPGB 3.45 34",  issuer="Spain",
         sector="Sovereign", sub_sector="Semi-Core",
         rating="A",    country="Spain",       ccy="EUR", cpn=3.45,
         mat="2034-07-30", sz=20000, sen="Senior"),
    dict(isin="PT0000000010", ticker="PGB 3⅝ 33",     issuer="Portugal",
         sector="Sovereign", sub_sector="Semi-Core",
         rating="A-",   country="Portugal",    ccy="EUR", cpn=3.625,
         mat="2033-10-15", sz=5000, sen="Senior"),
    # Supranational
    dict(isin="EU000A3KWKL1", ticker="EU 2⅞ 32",      issuer="European Union",
         sector="Supranational", sub_sector="AAA Supra",
         rating="AAA",  country="Supranational", ccy="EUR", cpn=2.875,
         mat="2032-10-04", sz=20000, sen="Senior"),
    dict(isin="XS2345670001", ticker="EIB 2⅝ 31",     issuer="European Invest. Bank",
         sector="Supranational", sub_sector="AAA Supra",
         rating="AAA",  country="Supranational", ccy="EUR", cpn=2.625,
         mat="2031-04-15", sz=5000, sen="Senior"),
    # Covered
    dict(isin="XS2456780001", ticker="DZHYP 3 30",    issuer="DZ HYP",
         sector="Covered", sub_sector="Pfandbriefe",
         rating="AAA",  country="Germany",     ccy="EUR", cpn=3.00,
         mat="2030-06-15", sz=500,  sen="Covered"),
    dict(isin="XS2456780002", ticker="CDSFP 3⅛ 31",   issuer="Credit Agricole CIB",
         sector="Covered", sub_sector="Obligations Foncières",
         rating="AAA",  country="France",      ccy="EUR", cpn=3.125,
         mat="2031-02-25", sz=750,  sen="Covered"),
    # Corporate — TMT
    dict(isin="XS2100000020", ticker="DTE 3⅞ 30",     issuer="Deutsche Telekom",
         sector="Corporate", sub_sector="TMT",
         rating="BBB+", country="Germany",     ccy="EUR", cpn=3.875,
         mat="2030-02-20", sz=1000, sen="Senior"),
    dict(isin="XS2100000021", ticker="VOD 4¼ 29",     issuer="Vodafone Group",
         sector="Corporate", sub_sector="TMT",
         rating="BBB-", country="UK",          ccy="EUR", cpn=4.25,
         mat="2029-07-15", sz=750,  sen="Senior"),
    dict(isin="XS2100000022", ticker="ORANA 3⅝ 31",   issuer="Orange SA",
         sector="Corporate", sub_sector="TMT",
         rating="BBB+", country="France",      ccy="EUR", cpn=3.625,
         mat="2031-03-04", sz=1000, sen="Senior"),
    # Corporate — Utilities
    dict(isin="XS2100000023", ticker="ENELIM 4 32",   issuer="Enel SpA",
         sector="Corporate", sub_sector="Utilities",
         rating="BBB+", country="Italy",       ccy="EUR", cpn=4.00,
         mat="2032-09-12", sz=1250, sen="Senior"),
    dict(isin="XS2100000024", ticker="ENGI 3½ 30",    issuer="Engie SA",
         sector="Corporate", sub_sector="Utilities",
         rating="A-",   country="France",      ccy="EUR", cpn=3.50,
         mat="2030-01-18", sz=750,  sen="Senior"),
    dict(isin="XS2100000025", ticker="IBERDR 3⅞ 31",  issuer="Iberdrola",
         sector="Corporate", sub_sector="Utilities",
         rating="BBB+", country="Spain",       ccy="EUR", cpn=3.875,
         mat="2031-11-24", sz=1000, sen="Senior"),
    # Corporate — Energy
    dict(isin="XS2100000026", ticker="TOTFP 3¼ 29",   issuer="TotalEnergies",
         sector="Corporate", sub_sector="Energy",
         rating="A+",   country="France",      ccy="EUR", cpn=3.25,
         mat="2029-09-29", sz=1500, sen="Senior"),
    dict(isin="XS2100000027", ticker="SHELLY 3⅛ 28",  issuer="Shell Int'l Finance",
         sector="Corporate", sub_sector="Energy",
         rating="AA-",  country="Netherlands", ccy="EUR", cpn=3.125,
         mat="2028-06-07", sz=2000, sen="Senior"),
    # Corporate — Automotive
    dict(isin="XS2100000028", ticker="VWAGY 4⅛ 30",   issuer="Volkswagen AG",
         sector="Corporate", sub_sector="Automotive",
         rating="BBB+", country="Germany",     ccy="EUR", cpn=4.125,
         mat="2030-05-13", sz=1000, sen="Senior"),
    dict(isin="XS2100000029", ticker="BMWFP 3⅝ 29",   issuer="BMW AG",
         sector="Corporate", sub_sector="Automotive",
         rating="A",    country="Germany",     ccy="EUR", cpn=3.625,
         mat="2029-08-26", sz=1250, sen="Senior"),
    dict(isin="XS2100000030", ticker="STLA 4½ 31",    issuer="Stellantis NV",
         sector="Corporate", sub_sector="Automotive",
         rating="BBB",  country="Netherlands", ccy="EUR", cpn=4.50,
         mat="2031-07-14", sz=750,  sen="Senior"),
    # Corporate — Industrials / Consumer
    dict(isin="XS2100000031", ticker="AIRFP 3⅜ 31",   issuer="Air Liquide",
         sector="Corporate", sub_sector="Industrials",
         rating="A",    country="France",      ccy="EUR", cpn=3.375,
         mat="2031-05-20", sz=750,  sen="Senior"),
    dict(isin="XS2100000032", ticker="SIEMENS 3 29",   issuer="Siemens AG",
         sector="Corporate", sub_sector="Industrials",
         rating="A+",   country="Germany",     ccy="EUR", cpn=3.00,
         mat="2029-04-11", sz=1000, sen="Senior"),
    dict(isin="XS2100000033", ticker="ABIBB 3¾ 32",   issuer="AB InBev",
         sector="Corporate", sub_sector="Consumer",
         rating="BBB+", country="Belgium",     ccy="EUR", cpn=3.75,
         mat="2032-03-17", sz=2000, sen="Senior"),
    dict(isin="XS2100000034", ticker="NESTLE 3 28",   issuer="Nestle SA",
         sector="Corporate", sub_sector="Consumer",
         rating="AA-",  country="Switzerland", ccy="EUR", cpn=3.00,
         mat="2028-07-14", sz=1500, sen="Senior"),
    dict(isin="XS2100000035", ticker="SANOFI 2⅞ 30",  issuer="Sanofi SA",
         sector="Corporate", sub_sector="Healthcare",
         rating="AA-",  country="France",      ccy="EUR", cpn=2.875,
         mat="2030-09-21", sz=1000, sen="Senior"),
    dict(isin="XS2100000036", ticker="PHIA 4¼ 30",    issuer="Philips",
         sector="Corporate", sub_sector="Healthcare",
         rating="BBB",  country="Netherlands", ccy="EUR", cpn=4.25,
         mat="2030-08-03", sz=750,  sen="Senior"),
    # EM
    dict(isin="XS2567890001", ticker="PETBRA 6⅞ 33",  issuer="Petrobras",
         sector="EM Corporate", sub_sector="EM Energy",
         rating="BB",   country="Brazil",      ccy="USD", cpn=6.875,
         mat="2033-01-17", sz=2000, sen="Senior"),
    dict(isin="XS2567890002", ticker="MEXSOV 5¾ 31",  issuer="Mexico",
         sector="EM Sovereign", sub_sector="LATAM",
         rating="BBB-", country="Mexico",      ccy="USD", cpn=5.75,
         mat="2031-10-12", sz=5000, sen="Senior"),
    dict(isin="XS2567890003", ticker="VALE 6 32",     issuer="Vale SA",
         sector="EM Corporate", sub_sector="EM Energy",
         rating="BBB-", country="Brazil",      ccy="USD", cpn=6.00,
         mat="2032-06-10", sz=1000, sen="Senior"),
]

# ── market curve base (EUR swaps, %) ──────────────────────────────────────────
EUR_SWAP_BASE = {
    0.25: 3.20, 0.5: 3.15, 1: 3.05, 2: 2.95, 3: 2.88,
    5: 2.85, 7: 2.90, 10: 3.00, 15: 3.10, 20: 3.15, 30: 3.05,
}


def _ou_path(n: int, mean: float, kappa: float, sigma: float, s0: float) -> np.ndarray:
    """Ornstein-Uhlenbeck path (daily steps)."""
    path = np.empty(n)
    path[0] = s0
    dt = 1.0
    noise = RNG.standard_normal(n - 1)
    for i in range(1, n):
        path[i] = (
            path[i - 1]
            + kappa * (mean - path[i - 1]) * dt
            + sigma * np.sqrt(dt) * noise[i - 1]
        )
    return path


def _spread_duration(maturity_str: str, ref: date) -> float:
    mat = pd.to_datetime(maturity_str).date()
    yrs = max((mat - ref).days / 365.25, 0.0)
    # Approx modified duration for a par bond
    return min(yrs * 0.92, 12.0)


def load_sample_data():
    init_db()
    session = get_session()

    try:
        existing = session.query(Bond).count()
        if existing > 0:
            print(f"DB already contains {existing} bonds — skipping sample load.")
            return

        end_date = date(2026, 4, 27)
        start_date = end_date - timedelta(days=89)
        dates = [start_date + timedelta(days=i) for i in range(90)]
        n = len(dates)

        # Sector-level common factor paths (mean-reverting shock in bps)
        sector_names = list({b["sector"] for b in BOND_DEFS})
        sector_factors: dict[str, np.ndarray] = {}
        for s in sector_names:
            sector_factors[s] = _ou_path(n, 0, 0.03, 3.0, RNG.uniform(-5, 5))

        # ── bonds ─────────────────────────────────────────────────────────────
        for bd in BOND_DEFS:
            b = Bond(
                isin=bd["isin"],
                ticker=bd["ticker"],
                issuer=bd["issuer"],
                sector=bd["sector"],
                sub_sector=bd["sub_sector"],
                composite_rating=bd["rating"],
                country_of_risk=bd["country"],
                currency=bd["ccy"],
                coupon=bd["cpn"],
                maturity_date=pd.to_datetime(bd["mat"]).date(),
                maturity_bucket=get_maturity_bucket(bd["mat"], end_date),
                issue_date=pd.to_datetime(bd["mat"]).date() - timedelta(days=int(5 * 365)),
                issue_size_mm=bd["sz"],
                seniority=bd["sen"],
            )
            session.add(b)

            base_oas = RATING_BASE_OAS.get(bd["rating"], 150)
            ctry_prem = COUNTRY_SPREAD.get(bd["country"], 50)

            # Idiosyncratic OAS path
            oas_path = _ou_path(
                n,
                mean=base_oas + ctry_prem * 0.3,
                kappa=0.04,
                sigma=max(3.0, base_oas * 0.04),
                s0=base_oas + ctry_prem * 0.3 + RNG.uniform(-15, 15),
            ) + sector_factors[bd["sector"]]

            base_yld = _ou_path(
                n,
                mean=3.0 + base_oas / 100,
                kappa=0.02,
                sigma=0.04,
                s0=3.0 + base_oas / 100,
            )

            for i, d in enumerate(dates):
                oas = float(max(1, oas_path[i]))
                yld = float(base_yld[i])
                sd = _spread_duration(bd["mat"], d)
                bp = BondPrice(
                    date=d,
                    isin=b.isin,
                    price=round(100 - (yld - bd["cpn"]) * sd * 100, 4),
                    yield_pct=round(yld, 4),
                    oas=round(oas, 2),
                    z_spread=round(oas * 1.02, 2),
                    spread_benchmark=round(oas + 5, 2),
                    spread_itraxx=round(oas * 0.85 + RNG.uniform(-5, 5), 2),
                    spread_cdx=round(oas * 0.88 + RNG.uniform(-5, 5), 2),
                    spread_duration=round(sd, 3),
                    country_spread=float(ctry_prem) + float(_ou_path(3, ctry_prem, 0.05, 2.0, ctry_prem)[1]),
                )
                session.add(bp)

        # ── yield curve ───────────────────────────────────────────────────────
        curve_shift = _ou_path(n, 0, 0.01, 0.04, 0.0)
        for i, d in enumerate(dates):
            for tenor, yld_base in EUR_SWAP_BASE.items():
                mc = MarketCurve(
                    date=d,
                    curve_type="EUR_SWAPS",
                    tenor=tenor,
                    yield_pct=round(yld_base + curve_shift[i], 4),
                )
                session.add(mc)

        session.commit()
        print(f"Loaded {len(BOND_DEFS)} bonds × {n} days + yield curve.")

    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    load_sample_data()
