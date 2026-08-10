"""FX rate adapter -- Frankfurter API (European Central Bank reference rates).

Genuinely free, no API key, no rate limit documented for reasonable use, ECB is an authoritative
primary source for reference FX rates. Used to let the CFO compare NOK-priced Oslo Bors names
against USD-priced NYSE names on a common basis, without ever silently mixing currencies.

Endpoint: https://api.frankfurter.dev/v1/latest?from=USD&to=NOK
Docs: https://frankfurter.dev/
"""
from __future__ import annotations

import json
import urllib.request
from datetime import date

import pandas as pd

from src.adapters.base import SourceAdapter
from src.data_model import DataStatus
from src.utils.logging_config import get_logger

log = get_logger("adapters.fx")

FRANKFURTER_URL = "https://api.frankfurter.dev/v1/latest"


class FXRateAdapter(SourceAdapter):
    name = "Frankfurter (ECB reference rates)"
    frequency = "daily"
    license_note = "European Central Bank reference rates via the free Frankfurter API; no key required."

    def __init__(self, base: str = "USD", quotes: tuple[str, ...] = ("NOK", "EUR"), timeout: int = 10):
        self.base = base
        self.quotes = quotes
        self.timeout = timeout

    def fetch(self) -> pd.DataFrame:
        rows = []
        for quote in self.quotes:
            url = f"{FRANKFURTER_URL}?from={self.base}&to={quote}"
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "ShippingCFOIntelligence/1.0"})
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    payload = json.loads(resp.read().decode("utf-8"))
            except (OSError, ValueError) as exc:
                log.warning("Frankfurter FX fetch failed for %s/%s: %s", self.base, quote, exc)
                continue
            rate = payload.get("rates", {}).get(quote)
            obs_date_str = payload.get("date")
            if rate is None or not obs_date_str:
                log.warning("Frankfurter FX response missing rate/date for %s/%s", self.base, quote)
                continue
            try:
                obs_date = date.fromisoformat(obs_date_str)
            except ValueError:
                log.warning("Frankfurter FX response had unparseable date %r", obs_date_str)
                continue
            rows.append({
                "segment": "FX",
                "metric": f"{self.base}{quote}",
                "value": float(rate),
                "unit": f"{quote}_per_{self.base}",
                "observation_date": obs_date,
                "source": self.name,
                "frequency": self.frequency,
                "status": DataStatus.LIVE.value,
                "license_note": self.license_note,
            })
        if not rows:
            return pd.DataFrame()
        return pd.DataFrame(rows)
