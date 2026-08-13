"""IMF PortWatch chokepoint traffic adapter -- daily vessel-transit estimates for the world's
major maritime chokepoints (Suez, Panama, Hormuz, Bab al-Mandab, Bosphorus, Malacca, Gibraltar,
Dover).

Genuinely free, no API key, no registration -- PortWatch is a joint IMF / University of Oxford
Environmental Change Institute open-data platform built on AIS ship-tracking data, hosted as a
public ArcGIS FeatureServer. Despite the dataset's name ("Daily_Chokepoints_Data"), IMF publishes
updates weekly (Tuesdays); this adapter reflects that in `frequency` rather than overstating
freshness.

Endpoint: https://services9.arcgis.com/weJ1QsnbMYJlCHdG/arcgis/rest/services/Daily_Chokepoints_Data/FeatureServer/0/query
Docs: https://portwatch.imf.org/pages/data-and-methodology

Field names for this ArcGIS layer could not be verified against a live response when this adapter
was written -- this sandbox has no route to arcgis.com (see docs/source_register.md). The parser
therefore does not assume one fixed schema: it searches each returned feature's attributes for one
of several plausible field names for the chokepoint label, the observation date and the
vessel-count metric, and logs a warning and returns an empty DataFrame (never a fabricated number)
if none of the candidates match. The first real run of this adapter happens in GitHub Actions,
which does have internet access -- check its logs and narrow the candidate lists below if the
schema differs from what's assumed here.
"""
from __future__ import annotations

import json
import urllib.parse
import urllib.request
from datetime import date, datetime
from typing import Optional

import pandas as pd

from src.adapters.base import SourceAdapter
from src.config import CHOKEPOINTS
from src.data_model import DataStatus
from src.utils.logging_config import get_logger

log = get_logger("adapters.imf_portwatch")

FEATURE_SERVER_URL = (
    "https://services9.arcgis.com/weJ1QsnbMYJlCHdG/arcgis/rest/services/"
    "Daily_Chokepoints_Data/FeatureServer/0/query"
)

# Candidate ArcGIS field names, in priority order -- the first one present in a returned feature's
# attributes wins. Extend these (based on GitHub Actions logs) if a live response uses a field name
# not listed here; do not guess a value field just because it is numeric.
_NAME_FIELD_CANDIDATES = ["chokepoint", "Chokepoint", "ChokepointName", "CHOKEPOINT", "portname", "PortName", "name"]
_DATE_FIELD_CANDIDATES = ["date", "Date", "DATE", "dt", "observation_date"]
_VALUE_FIELD_CANDIDATES = [
    "n_total", "vessels_total", "vessel_count_total", "n_ships", "total_vessels", "n_transits", "value",
]


class IMFPortWatchAdapter(SourceAdapter):
    name = "IMF PortWatch (Daily Chokepoints Data)"
    frequency = "weekly (published Tuesdays, AIS-derived)"
    license_note = ("Joint IMF / University of Oxford Environmental Change Institute open data; "
                     "free, no key, public ArcGIS FeatureServer; see "
                     "portwatch.imf.org/pages/data-and-methodology.")

    def __init__(self, chokepoints: Optional[tuple] = None, lookback_records: int = 2000, timeout: int = 15):
        self.chokepoints = tuple(chokepoints) if chokepoints else tuple(CHOKEPOINTS)
        self.lookback_records = lookback_records
        self.timeout = timeout

    def _fetch_raw(self) -> list[dict]:
        params = {
            "where": "1=1",
            "outFields": "*",
            "f": "json",
            "resultRecordCount": str(self.lookback_records),
        }
        query = "&".join(f"{k}={urllib.parse.quote(str(v))}" for k, v in params.items())
        url = f"{FEATURE_SERVER_URL}?{query}"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "ShippingCFOIntelligence/1.0"})
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except (OSError, ValueError) as exc:
            log.warning("IMF PortWatch fetch failed: %s", exc)
            return []
        if "error" in payload:
            log.warning("IMF PortWatch API returned an error payload: %s", payload.get("error"))
            return []
        features = payload.get("features", [])
        if not features:
            log.warning("IMF PortWatch response had no features (payload keys: %s)", list(payload.keys()))
        return [f.get("attributes", {}) for f in features if isinstance(f, dict)]

    @staticmethod
    def _first_present(attrs: dict, candidates: list) -> Optional[str]:
        for c in candidates:
            if c in attrs and attrs[c] is not None:
                return c
        return None

    @staticmethod
    def _parse_date(raw) -> Optional[date]:
        if raw is None:
            return None
        try:
            # ArcGIS commonly returns date fields as epoch milliseconds.
            if isinstance(raw, (int, float)):
                return datetime.utcfromtimestamp(raw / 1000).date()
            return datetime.fromisoformat(str(raw)[:10]).date()
        except (ValueError, OverflowError, OSError, TypeError):
            return None

    def fetch(self) -> pd.DataFrame:
        records = self._fetch_raw()
        if not records:
            return pd.DataFrame()

        sample = records[0]
        name_field = self._first_present(sample, _NAME_FIELD_CANDIDATES)
        date_field = self._first_present(sample, _DATE_FIELD_CANDIDATES)
        value_field = self._first_present(sample, _VALUE_FIELD_CANDIDATES)
        if not (name_field and date_field and value_field):
            log.warning(
                "IMF PortWatch: could not identify name/date/value fields from response schema "
                "(available fields: %s). Returning no data rather than guessing.", list(sample.keys()),
            )
            return pd.DataFrame()

        # Keep only rows matching our tracked chokepoints, then take the latest observation per
        # chokepoint (the feature server returns a long history; ordering is not guaranteed).
        latest_by_chokepoint: dict = {}
        for attrs in records:
            raw_name = attrs.get(name_field)
            if not raw_name:
                continue
            raw_name_lower = str(raw_name).lower()
            matched = next(
                (cp for cp in self.chokepoints if cp.lower() in raw_name_lower or raw_name_lower in cp.lower()),
                None,
            )
            if matched is None:
                continue
            obs_date = self._parse_date(attrs.get(date_field))
            if obs_date is None:
                continue
            value = attrs.get(value_field)
            if value is None:
                continue
            current = latest_by_chokepoint.get(matched)
            if current is None or obs_date > current["observation_date"]:
                latest_by_chokepoint[matched] = {"observation_date": obs_date, "value": value}

        if not latest_by_chokepoint:
            log.warning("IMF PortWatch: response parsed but none of the tracked chokepoints (%s) matched "
                        "values in field '%s'.", self.chokepoints, name_field)
            return pd.DataFrame()

        rows = []
        for chokepoint, data in latest_by_chokepoint.items():
            try:
                value = float(data["value"])
            except (TypeError, ValueError):
                continue
            rows.append({
                "segment": "Chokepoint",
                "metric": f"{chokepoint} — daily vessel transits",
                "value": value,
                "unit": "vessels/day",
                "observation_date": data["observation_date"],
                "source": self.name,
                "frequency": self.frequency,
                "status": DataStatus.LIVE.value,
                "license_note": self.license_note,
            })
        if not rows:
            return pd.DataFrame()
        return pd.DataFrame(rows)
