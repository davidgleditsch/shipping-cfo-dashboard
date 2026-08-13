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
therefore does not assume one fixed schema: it probes a small unordered batch to detect field names,
then issues a second, larger request explicitly ordered by the detected date field (descending) so
a bounded page reliably contains the *most recent* observations rather than whatever slice the
server's default (apparently insertion/OBJECTID) order happens to return. Confirmed against the
2026-08-13 GitHub Actions run: the first version of this adapter (no server-side ordering) returned
only a single chokepoint (Suez Canal) with an observation date of 2024-06-22 -- i.e. an arbitrary
early slice of the dataset's full history, not the latest week. This version fixes that.

Chokepoint name matching is keyword-based (see `_CHOKEPOINT_KEYWORDS` below) rather than exact- or
substring-match against `config.CHOKEPOINTS`, because the dataset's exact label spelling (e.g.
"Bab-el-Mandeb Strait" vs. our "Bab al-Mandab") was not confirmed before writing this either. Widen
`_CHOKEPOINT_KEYWORDS` if a tracked chokepoint still doesn't appear after this fix.
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

# Keyword(s) that identify each tracked chokepoint in whatever free-text label the dataset actually
# uses (confirmed spelling varies -- e.g. IMF's own site uses both "Bab-el-Mandeb" and "Bab al-Mandab"
# in different places). Matching is "any keyword is a case-insensitive substring of the raw label."
_CHOKEPOINT_KEYWORDS = {
    "Suez Canal": ("suez",),
    "Panama Canal": ("panama",),
    "Strait of Hormuz": ("hormuz",),
    "Bab al-Mandab": ("mandab", "mandeb"),
    "Bosphorus Strait": ("bosphorus", "bosporus"),
    "Strait of Malacca": ("malacca",),
    "Strait of Gibraltar": ("gibraltar",),
    "Strait of Dover": ("dover",),
}


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

    def _fetch_page(self, extra_params: dict) -> list[dict]:
        params = {"where": "1=1", "outFields": "*", "f": "json", **extra_params}
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

    @staticmethod
    def _match_chokepoint(raw_name: str, tracked: tuple) -> Optional[str]:
        raw_name_lower = raw_name.lower()
        for cp, keywords in _CHOKEPOINT_KEYWORDS.items():
            if cp not in tracked:
                continue
            if any(kw in raw_name_lower for kw in keywords):
                return cp
        return None

    def fetch(self) -> pd.DataFrame:
        # Phase 1: small, unordered probe purely to discover this layer's actual field names --
        # cheap, and avoids guessing an orderByFields value the server might reject.
        probe = self._fetch_page({"resultRecordCount": "10"})
        if not probe:
            log.warning("IMF PortWatch: probe request returned no features.")
            return pd.DataFrame()

        sample = probe[0]
        name_field = self._first_present(sample, _NAME_FIELD_CANDIDATES)
        date_field = self._first_present(sample, _DATE_FIELD_CANDIDATES)
        value_field = self._first_present(sample, _VALUE_FIELD_CANDIDATES)
        if not (name_field and date_field and value_field):
            log.warning(
                "IMF PortWatch: could not identify name/date/value fields from response schema "
                "(available fields: %s). Returning no data rather than guessing.", list(sample.keys()),
            )
            return pd.DataFrame()

        # Phase 2: ask the server itself for the most recent rows first, ordered by the field we
        # just detected -- this is what actually fixes "got an arbitrary early slice of history."
        records = self._fetch_page({
            "resultRecordCount": str(self.lookback_records),
            "orderByFields": f"{date_field} DESC",
        })
        if not records:
            log.warning("IMF PortWatch: ordered request returned no features (orderByFields=%s).", date_field)
            return pd.DataFrame()

        # Keep only rows matching our tracked chokepoints, then take the latest observation per
        # chokepoint (should now be within the first few dozen rows given the DESC ordering, but
        # scan the whole page defensively in case of duplicate/unsorted ties).
        latest_by_chokepoint: dict = {}
        for attrs in records:
            raw_name = attrs.get(name_field)
            if not raw_name:
                continue
            matched = self._match_chokepoint(str(raw_name), self.chokepoints)
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
