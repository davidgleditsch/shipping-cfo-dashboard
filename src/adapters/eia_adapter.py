"""Benchmark crude oil price adapter -- U.S. Energy Information Administration (EIA) API v2.

Free API, requires a no-cost registered API key (register at https://www.eia.gov/opendata/).
Provides Brent and WTI daily spot prices as demand-side context for the tanker segments -- this
adapter does not attempt to derive freight rates from oil prices, it only stores the two published
benchmark spot prices with their own source/date/frequency labeling, same as every other metric.

Note on coverage: the EIA does not publish a Dubai/Oman crude benchmark (it is a US federal agency
covering US and Brent/WTI-referenced markets); no free equivalent was found for Dubai crude at the
time this adapter was written (see docs/source_register.md) -- this is a documented gap, not a
silent omission.

If EIA_API_KEY is not configured (see src/config.py), this adapter logs a warning and returns an
empty DataFrame -- it must never raise just because the optional key is unset.

Endpoint: https://api.eia.gov/v2/petroleum/pri/spt/data/
Docs: https://www.eia.gov/opendata/ (browse the "petroleum/pri/spt" route in the API dashboard for
the exact facet values available)
"""
from __future__ import annotations

import json
import urllib.parse
import urllib.request
from datetime import date
from typing import Optional

import pandas as pd

from src.adapters.base import SourceAdapter
from src.config import EIA_API_KEY
from src.data_model import DataStatus
from src.utils.logging_config import get_logger

log = get_logger("adapters.eia")

EIA_SPOT_PRICES_URL = "https://api.eia.gov/v2/petroleum/pri/spt/data/"

# EIA "product" facet code -> (display metric name, unit). Verified product codes as of the EIA
# opendata browser in 2026: EPCBRENT = Europe Brent spot FOB, EPCWTI = WTI Cushing spot FOB.
DEFAULT_PRODUCTS = {
    "EPCBRENT": ("Brent crude spot (Europe, FOB)", "usd_per_barrel"),
    "EPCWTI": ("WTI crude spot (Cushing, FOB)", "usd_per_barrel"),
}


class EIASpotPriceAdapter(SourceAdapter):
    name = "EIA (U.S. Energy Information Administration)"
    frequency = "daily"
    license_note = ("US federal public-domain data via the free EIA API v2; requires a no-cost "
                     "registered API key, no other usage restriction.")

    def __init__(self, products: Optional[dict] = None, api_key: str = "", timeout: int = 10):
        self.products = products or DEFAULT_PRODUCTS
        self.api_key = api_key or EIA_API_KEY
        self.timeout = timeout

    def _fetch_one(self, product_code: str) -> Optional[dict]:
        # EIA v2 uses repeated bracketed query params for facets/data/sort -- urlencode with
        # doseq=True handles the list values correctly.
        params = [
            ("api_key", self.api_key),
            ("frequency", "daily"),
            ("data[0]", "value"),
            ("facets[product][]", product_code),
            ("sort[0][column]", "period"),
            ("sort[0][direction]", "desc"),
            ("length", "5"),
        ]
        query = urllib.parse.urlencode(params)
        url = f"{EIA_SPOT_PRICES_URL}?{query}"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "ShippingCFOIntelligence/1.0"})
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except (OSError, ValueError) as exc:
            log.warning("EIA fetch failed for product %s: %s", product_code, exc)
            return None

        records = payload.get("response", {}).get("data", [])
        if not records:
            log.warning("EIA returned no data for product %s (response keys: %s)",
                        product_code, list(payload.keys()))
            return None
        top = records[0]
        try:
            obs_date = date.fromisoformat(top["period"])
            value = float(top["value"])
        except (KeyError, ValueError, TypeError):
            log.warning("EIA response for product %s had an unparseable period/value: %s", product_code, top)
            return None
        return {"observation_date": obs_date, "value": value}

    def fetch(self) -> pd.DataFrame:
        if not self.api_key:
            log.warning("EIA_API_KEY not configured -- skipping (register free at https://www.eia.gov/opendata/).")
            return pd.DataFrame()

        rows = []
        for product_code, (label, unit) in self.products.items():
            result = self._fetch_one(product_code)
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
