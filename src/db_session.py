"""Streamlit-cached DB connection + adapter refresh helpers shared by all pages."""
from __future__ import annotations

import streamlit as st

from src.adapters.eia_adapter import EIASpotPriceAdapter
from src.adapters.fred_adapter import FREDRateAdapter
from src.adapters.fx_adapter import FXRateAdapter
from src.adapters.imf_portwatch_adapter import IMFPortWatchAdapter
from src.adapters.news_rss_adapter import NewsRSSAdapter
from src.adapters.sec_edgar_adapter import SECEdgarFilingsAdapter
from src.adapters.yfinance_adapter import YFinanceMarketAdapter
from src.db import get_connection, upsert_dataframe
from src.utils.logging_config import get_logger

log = get_logger("db_session")


@st.cache_resource
def get_conn():
    return get_connection()


def refresh_market_data() -> tuple[int, list[str]]:
    conn = get_conn()
    errors = []
    inserted = 0
    try:
        df = YFinanceMarketAdapter().fetch()
        inserted += upsert_dataframe(conn, "company_market_data", df)
        if df.empty:
            errors.append("Yahoo Finance returned no data (feed unavailable or all tickers failed).")
    except Exception as exc:
        log.exception("Market data refresh failed")
        errors.append(f"Market data refresh failed: {exc}")
    return inserted, errors


def refresh_news() -> tuple[int, list[str]]:
    conn = get_conn()
    errors = []
    inserted = 0
    try:
        df = NewsRSSAdapter().fetch()
        inserted += upsert_dataframe(conn, "news_events", df) if not df.empty else 0
        if df.empty:
            errors.append("News RSS feeds returned no items (feeds unavailable).")
    except Exception as exc:
        log.exception("News refresh failed")
        errors.append(f"News refresh failed: {exc}")
    return inserted, errors


def refresh_fx() -> tuple[int, list[str]]:
    conn = get_conn()
    errors = []
    inserted = 0
    try:
        df = FXRateAdapter().fetch()
        inserted += upsert_dataframe(conn, "market_data_daily", df) if not df.empty else 0
        if df.empty:
            errors.append("FX rate feed (Frankfurter) returned no data.")
    except Exception as exc:
        log.exception("FX refresh failed")
        errors.append(f"FX refresh failed: {exc}")
    return inserted, errors


def refresh_sec_filings() -> tuple[int, list[str]]:
    conn = get_conn()
    errors = []
    inserted = 0
    try:
        df = SECEdgarFilingsAdapter().fetch()
        inserted += upsert_dataframe(conn, "news_events", df) if not df.empty else 0
        if df.empty:
            errors.append("SEC EDGAR returned no recent filings for SEC-registered watchlist names.")
    except Exception as exc:
        log.exception("SEC EDGAR refresh failed")
        errors.append(f"SEC EDGAR refresh failed: {exc}")
    return inserted, errors


def refresh_macro_context() -> tuple[int, list[str]]:
    """IMF PortWatch chokepoint transits + FRED/EIA benchmark rates -- added August 2026."""
    conn = get_conn()
    errors = []
    inserted = 0
    for label, adapter in (
        ("IMF PortWatch", IMFPortWatchAdapter()),
        ("FRED", FREDRateAdapter()),
        ("EIA", EIASpotPriceAdapter()),
    ):
        try:
            df = adapter.fetch()
            inserted += upsert_dataframe(conn, "market_data_daily", df) if not df.empty else 0
            if df.empty:
                errors.append(f"{label} returned no data (feed unavailable, key missing, or schema mismatch).")
        except Exception as exc:
            log.exception("%s refresh failed", label)
            errors.append(f"{label} refresh failed: {exc}")
    return inserted, errors
