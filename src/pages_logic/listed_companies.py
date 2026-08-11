"""Pure logic for the Listed Companies page."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import duckdb
import pandas as pd

from src.config import WATCHLIST
from src.data_model import DataStatus, SourceMeta

FINANCIAL_PLACEHOLDERS = [
    ("revenue", "Revenue"),
    ("ebitda", "EBITDA"),
    ("net_debt", "Net debt"),
    ("cash", "Cash"),
    ("dividend_per_share", "Dividend per share"),
    ("fleet_size", "Fleet size"),
    ("contract_coverage_pct", "Contract coverage %"),
    ("spot_exposure_pct", "Spot exposure %"),
]


@dataclass
class CompanyView:
    name: str
    segment: str
    ticker: str
    listed: bool = True
    status_note: str = ""
    latest_price: Optional[float] = None
    currency: Optional[str] = None
    price_date: Optional[str] = None
    price_source_meta: Optional[SourceMeta] = None
    price_history: pd.DataFrame = field(default_factory=pd.DataFrame)
    financials: dict = field(default_factory=dict)
    nav_status: str = "Requires vessel-value assumptions (see docs/source_register.md) -- not calculated."


def get_company_views(conn: duckdb.DuckDBPyConnection) -> list[CompanyView]:
    price_df = conn.execute(
        "SELECT * FROM company_market_data WHERE metric = 'close_price' ORDER BY observation_date ASC"
    ).df()
    fin_df = conn.execute(
        "SELECT * FROM company_financials ORDER BY observation_date DESC"
    ).df()

    views = []
    for co in WATCHLIST:
        cv = CompanyView(name=co["name"], segment=co["segment"], ticker=co["ticker"],
                          listed=co.get("listed", True), status_note=co.get("status_note", ""))

        if not cv.listed:
            cv.price_source_meta = SourceMeta(
                source="Company no longer publicly listed",
                observation_date=None, frequency="n/a", status=DataStatus.UNAVAILABLE,
            )
        else:
            co_prices = price_df[price_df["company"] == co["name"]] if not price_df.empty else pd.DataFrame()
            if not co_prices.empty:
                latest = co_prices.sort_values("observation_date").iloc[-1]
                cv.latest_price = float(latest["value"])
                cv.currency = latest["currency"]
                cv.price_date = str(latest["observation_date"])
                status = DataStatus(latest["status"]) if latest["status"] in DataStatus._value2member_map_ else DataStatus.DELAYED
                cv.price_source_meta = SourceMeta(
                    source=latest["source"], observation_date=latest["observation_date"],
                    frequency=latest["frequency"], status=status,
                )
                cv.price_history = co_prices.sort_values("observation_date")
            else:
                cv.price_source_meta = SourceMeta(
                    source="Yahoo Finance (ticker unresolved or feed unavailable)",
                    observation_date=None, frequency="daily", status=DataStatus.UNAVAILABLE,
                )

        co_fin = fin_df[fin_df["company"] == co["name"]] if not fin_df.empty else pd.DataFrame()
        for metric_key, label in FINANCIAL_PLACEHOLDERS:
            rows = co_fin[co_fin["metric"] == metric_key] if not co_fin.empty else pd.DataFrame()
            if rows.empty:
                cv.financials[metric_key] = {
                    "label": label, "value": None, "unit": None, "period": None,
                    "source_meta": SourceMeta(source="No manual data uploaded", observation_date=None,
                                               frequency="n/a", status=DataStatus.UNAVAILABLE),
                }
            else:
                latest = rows.iloc[0]
                status = DataStatus(latest["status"]) if latest["status"] in DataStatus._value2member_map_ else DataStatus.MANUAL
                # "period" is the reporting period the figure belongs to (e.g. "Q1 2026", "FY2025"),
                # distinct from observation_date (when the analyst recorded it) -- shown to the user so
                # a Q1 figure is never mistaken for a just-released Q2 number. Older uploads made before
                # this column was consistently populated fall back to "n/a" rather than a guess.
                period = latest["period"] if "period" in latest and pd.notna(latest["period"]) else None
                cv.financials[metric_key] = {
                    "label": label, "value": float(latest["value"]), "unit": latest["unit"], "period": period,
                    "source_meta": SourceMeta(source=latest["source"], observation_date=latest["observation_date"],
                                               frequency=latest["frequency"], status=status),
                }
        views.append(cv)
    return views


def get_latest_fx_rate(conn: duckdb.DuckDBPyConnection, pair: str = "USDNOK") -> Optional[tuple[float, SourceMeta]]:
    """Latest FX rate (e.g. USDNOK) for converting NOK-priced names to a common basis.

    Returns None if no FX data has been fetched yet (sidebar "Refresh live data now").
    """
    row = conn.execute(
        "SELECT * FROM market_data_daily WHERE segment = 'FX' AND metric = ? "
        "ORDER BY observation_date DESC LIMIT 1",
        [pair],
    ).df()
    if row.empty:
        return None
    latest = row.iloc[0]
    status = DataStatus(latest["status"]) if latest["status"] in DataStatus._value2member_map_ else DataStatus.LIVE
    meta = SourceMeta(
        source=latest["source"], observation_date=latest["observation_date"],
        frequency=latest["frequency"], status=status,
    )
    return float(latest["value"]), meta
