"""Live (delayed) share-price data for the listed watchlist via Yahoo Finance.

Free, no API key. Data is exchange-delayed, so it is stored with status=DELAYED, never LIVE or
manual. If yfinance is unreachable or a ticker fails to resolve, that company is skipped and logged
— the rest of the app must keep working (graceful degradation rule).
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

import pandas as pd

from src.adapters.base import SourceAdapter
from src.config import WATCHLIST
from src.data_model import DataStatus
from src.utils.logging_config import get_logger

log = get_logger("adapters.yfinance")


class YFinanceMarketAdapter(SourceAdapter):
    name = "Yahoo Finance"
    frequency = "daily"
    license_note = "Yahoo Finance data via yfinance; exchange-delayed quotes; personal/dashboard use."

    def __init__(self, lookback_days: int = 400):
        self.lookback_days = lookback_days

    def fetch(self) -> pd.DataFrame:
        try:
            import yfinance as yf
        except ImportError:
            log.error("yfinance not installed; skipping live market data fetch.")
            return pd.DataFrame()

        rows = []
        start = (datetime.utcnow() - timedelta(days=self.lookback_days)).date()
        for co in WATCHLIST:
            ticker = co["ticker"]
            try:
                hist = yf.Ticker(ticker).history(start=start.isoformat(), interval="1d")
            except Exception as exc:  # network / provider errors — never crash the app
                log.warning("yfinance fetch failed for %s (%s): %s", co["name"], ticker, exc)
                continue
            if hist is None or hist.empty:
                log.warning("yfinance returned no data for %s (%s)", co["name"], ticker)
                continue
            currency = "NOK" if ticker.endswith(".OL") else "USD"
            for idx, row in hist.iterrows():
                obs_date = idx.date() if hasattr(idx, "date") else idx
                rows.append({
                    "company": co["name"],
                    "ticker": ticker,
                    "metric": "close_price",
                    "value": float(row["Close"]),
                    "unit": "price_per_share",
                    "currency": currency,
                    "observation_date": obs_date,
                    "source": self.name,
                    "frequency": self.frequency,
                    "status": DataStatus.DELAYED.value,
                })
                if "Volume" in row and pd.notna(row["Volume"]):
                    rows.append({
                        "company": co["name"],
                        "ticker": ticker,
                        "metric": "volume",
                        "value": float(row["Volume"]),
                        "unit": "shares",
                        "currency": currency,
                        "observation_date": obs_date,
                        "source": self.name,
                        "frequency": self.frequency,
                        "status": DataStatus.DELAYED.value,
                    })
        if not rows:
            return pd.DataFrame()
        return pd.DataFrame(rows)
