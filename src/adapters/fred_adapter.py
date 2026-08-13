"""Reference interest-rate adapter -- FRED (Federal Reserve Bank of St. Louis).

Free API, requires a no-cost registered API key (register at https://fred.stlouisfed.org/docs/api/api_key.html).
Used to give the CFO a benchmark reference rate (SOFR by default) to compare against the watchlist
companies' own disclosed cost of debt -- this adapter never computes or estimates any company's
actual interest expense, it only stores the public benchmark series.

If FRED_API_KEY is not configured (see src/config.py), this adapter logs a warning and returns an
empty DataFrame -- it must never raise just because the optional key is unset.

Endpoint: https://api.stlouisfed.org/fred/series/observations
Docs: https://fred.stlouisfed.org/docs/api/fred/series_observations.html
"""
from __future__ import annotations

import json
import urllib.parse
import urllib.request
from datetime import date
from typing import Optional

import pandas as pd

from src.adapters.base import SourceAdapter
from src.config import FRED_API_KEY
from src.data_model import DataStatus
from src.utils.logging_config import get_logger

log = get_logger("adapters.fred")

FRED_OBSERVATIONS_URL = "https://api.stlouisfed.org/fred/series/observations"

# FRED series ID -> (display metric name, unit). SOFR is the default -- the reference rate most
# relevant to shipping debt, which is now overwhelmingly SOFR-indexed rather than LIBOR-indexed.
DEFAULT_SERIES = {
    "SOFR": ("SOFR (Secured Overnight Financing Rate)", "percent"),
}


class FREDRateAdapter(SourceAdapter):
    name = "FRED (Federal Reserve Bank of St. Louis)"
    frequency = "daily"
    license_note = ("Public US Federal Reserve economic data via the free FRED API; requires a "
                     "no-cost registered API key, no other usage restriction for this kind of use.")

    def __init__(self, series: Optional[dict] = None, api_key: str = "", timeout: int = 10):
        self.series = series or DEFAULT_SERIES
        self.api_key = api_key or FRED_API_KEY
        self.timeout = timeout

    def _fetch_one(self, series_id: str) -> Optional[dict]:
        params = {
            "series_id": series_id,
            "api_key": self.api_key,
            "file_type": "json",
            "sort_order": "desc",
            "limit": "5",
        }
        query = urllib.parse.urlencode(params)
        url = f"{FRED_OBSERVATIONS_URL}?{query}"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "ShippingCFOIntelligence/1.0"})
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except (OSError, ValueError) as exc:
            log.warning("FRED fetch failed for series %s: %s", series_id, exc)
            return None

        observations = payload.get("observations", [])
        for obs in observations:  # most recent first; FRED uses "." for a missing value
            if obs.get("value") in (None, "."):
                continue
            try:
                obs_date = date.fromisoformat(obs["date"])
                value = float(obs["value"])
            except (KeyError, ValueError):
                continue
            return {"observation_date": obs_date, "value": value}
        log.warning("FRED series %s returned no usable (non-missing) observation in the last 5 points.", series_id)
        return None

    def fetch(self) -> pd.DataFrame:
        if not self.api_key:
            log.warning("FRED_API_KEY not configured -- skipping (register free at "
                        "https://fred.stlouisfed.org/docs/api/api_key.html).")
            return pd.DataFrame()

        rows = []
        for series_id, (label, unit) in self.series.items():
            result = self._fetch_one(series_id)
            if result is None:
                continue
            rows.append({
                "segment": "Macro",
                "metric": label,
                "value": result["value"],
                "unit": unit,
                "observation_date": result["observation_date"],
                "source": self.name,
                "frequency": self.frequency,
                "status": DataStatus.LIVE.value,
                "license_note": self.license_note,
            })
        if not rows:
            return pd.DataFrame()
        return pd.DataFrame(rows)
