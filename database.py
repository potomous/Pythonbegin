import os
from datetime import datetime

from sqlalchemy import (
    create_engine, Column, Integer, Float, String,
    Date, DateTime, ForeignKey, Text, UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, sessionmaker, relationship

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bonds.db")


class Base(DeclarativeBase):
    pass


class Bond(Base):
    __tablename__ = "bonds"

    # ISIN is the natural primary key for a bond
    isin = Column(String(12), primary_key=True)
    ticker = Column(String(20))
    issuer = Column(String(100), nullable=False)
    sector = Column(String(50))
    sub_sector = Column(String(50))
    composite_rating = Column(String(10))
    country_of_risk = Column(String(50))
    currency = Column(String(3), default="EUR")
    coupon = Column(Float)
    maturity_date = Column(Date)
    maturity_bucket = Column(String(20))
    issue_date = Column(Date)
    issue_size_mm = Column(Float)
    seniority = Column(String(30))
    created_at = Column(DateTime, default=datetime.utcnow)

    prices = relationship(
        "BondPrice", back_populates="bond", cascade="all, delete-orphan"
    )


class BondPrice(Base):
    """Time-series table. Primary key is (date, isin)."""
    __tablename__ = "bond_prices"

    date = Column(Date, primary_key=True)
    isin = Column(String(12), ForeignKey("bonds.isin"), primary_key=True)
    price = Column(Float)
    yield_pct = Column(Float)
    oas = Column(Float)
    z_spread = Column(Float)
    spread_benchmark = Column(Float)
    spread_itraxx = Column(Float)
    spread_cdx = Column(Float)
    spread_duration = Column(Float)
    country_spread = Column(Float)

    bond = relationship("Bond", back_populates="prices")


class MarketCurve(Base):
    __tablename__ = "market_curves"
    __table_args__ = (
        UniqueConstraint("date", "curve_type", "tenor", name="uq_curve_point"),
    )

    id = Column(Integer, primary_key=True)
    date = Column(Date, nullable=False)
    curve_type = Column(String(30))
    tenor = Column(Float)
    yield_pct = Column(Float)


class NewIssuePricing(Base):
    __tablename__ = "new_issue_pricings"

    id = Column(Integer, primary_key=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    issuer = Column(String(100))
    sector = Column(String(50))
    rating = Column(String(10))
    country_of_risk = Column(String(50))
    currency = Column(String(3))
    tenor = Column(Float)
    seniority = Column(String(30))
    size_mm = Column(Float)
    benchmark = Column(String(30))
    ipt_spread = Column(Float)
    ipt_yield = Column(Float)
    guidance_spread = Column(Float)
    final_spread = Column(Float)
    final_yield = Column(Float)
    fair_value_spread = Column(Float)
    nic = Column(Float)
    notes = Column(Text)
    status = Column(String(20), default="IPT")


engine = create_engine(
    f"sqlite:///{DB_PATH}",
    echo=False,
    connect_args={"check_same_thread": False},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False)


def init_db():
    Base.metadata.create_all(engine)


def get_session():
    return SessionLocal()


# ── helpers ───────────────────────────────────────────────────────────────────

def get_bonds_df(session):
    """Return all bonds joined with their latest price row as a DataFrame."""
    import pandas as pd
    from sqlalchemy import text

    sql = text(
        """
        SELECT
            b.isin, b.ticker, b.issuer, b.sector, b.sub_sector,
            b.composite_rating, b.country_of_risk, b.currency,
            b.coupon, b.maturity_date, b.maturity_bucket,
            b.issue_size_mm, b.seniority,
            p.date AS price_date, p.price, p.yield_pct, p.oas,
            p.z_spread, p.spread_benchmark, p.spread_itraxx,
            p.spread_cdx, p.spread_duration, p.country_spread
        FROM bonds b
        LEFT JOIN bond_prices p ON p.isin = b.isin
            AND p.date = (
                SELECT MAX(p2.date) FROM bond_prices p2 WHERE p2.isin = b.isin
            )
        ORDER BY b.sector, b.composite_rating, b.issuer
        """
    )
    return pd.read_sql(sql, session.bind)


def get_price_history_df(session, isins=None):
    """Return time-series price data for given ISINs (all bonds if None)."""
    import pandas as pd
    from sqlalchemy import text

    if isins:
        placeholders = ",".join(f"'{i}'" for i in isins)
        sql = text(
            f"""
            SELECT b.isin, b.ticker, b.issuer,
                   b.sector, b.sub_sector, b.composite_rating, b.country_of_risk,
                   p.date, p.yield_pct, p.oas, p.z_spread,
                   p.spread_benchmark, p.spread_itraxx, p.spread_cdx,
                   p.spread_duration, p.country_spread
            FROM bonds b JOIN bond_prices p ON p.isin = b.isin
            WHERE b.isin IN ({placeholders})
            ORDER BY p.date
            """
        )
    else:
        sql = text(
            """
            SELECT b.isin, b.ticker, b.issuer,
                   b.sector, b.sub_sector, b.composite_rating, b.country_of_risk,
                   p.date, p.yield_pct, p.oas, p.z_spread,
                   p.spread_benchmark, p.spread_itraxx, p.spread_cdx,
                   p.spread_duration, p.country_spread
            FROM bonds b JOIN bond_prices p ON p.isin = b.isin
            ORDER BY p.date
            """
        )
    return pd.read_sql(sql, session.bind)


def get_market_curve_df(session):
    import pandas as pd
    from sqlalchemy import text

    sql = text(
        "SELECT date, curve_type, tenor, yield_pct FROM market_curves ORDER BY date, tenor"
    )
    return pd.read_sql(sql, session.bind)
