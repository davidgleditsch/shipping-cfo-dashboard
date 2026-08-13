"""Pure logic for the Macro & Chokepoints page -- testable without Streamlit.

Added August 2026 alongside the IMF PortWatch, FRED and EIA adapters. Unlike the seven freight
segments (one rate series each), the "Chokepoint" and "Macro" segments in `market_data_daily` hold
several independent metrics at once (eight chokepoints; SOFR, Brent, WTI, ...), so this module
returns one view per metric rather than one view per segment.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional

import duckdb
import pandas as pd

from src.data_model import DataStatus, SourceMeta


@dataclass
class MetricView:
    label: str
    latest_value: Optional[float]
    latest_unit: Optional[str]
    latest_date: Optional[date]
    wow_change_pct: Optional[float]
    mom_change_pct: Optional[float]
    history: pd.DataFrame
    source_meta: SourceMeta


def _pct_change(latest: float, prior: Optional[float]) -> Optional[float]:
    if prior is None or prior == 0:
        return None
    return (latest - prior) / abs(prior) * 100.0


def _lookback_value(series: pd.Series, latest_date, days: int) -> Optional[float]:
    target = pd.Timestamp(latest_date) - pd.Timedelta(days=days)
    eligible = series[series.index.map(pd.Timestamp) <= target]
    if eligible.empty:
        return None
    return float(eligible.iloc[-1])


def _unavailable_view(label: str, note: str) -> MetricView:
    meta = SourceMeta(source="No free automated source confirmed", observation_date=None,
                       frequency="n/a", status=DataStatus.UNAVAILABLE, license_note=note)
    return MetricView(label, None, None, None, None, None, pd.DataFrame(), meta)


def get_metric_views_for_segment(conn: duckdb.DuckDBPyConnection, segment: str) -> dict:
    """One MetricView per distinct `metric` value stored under the given segment."""
    df = conn.execute(
        "SELECT * FROM market_data_daily WHERE segment = ? ORDER BY observation_date ASC",
        [segment],
    ).df()
    if df.empty:
        return {}

    views = {}
    for metric, series in df.groupby("metric"):
        series = series.sort_values("observation_date")
        latest_row = series.iloc[-1]
        latest_value = float(latest_row["value"])
        latest_date = latest_row["observation_date"]
        series_indexed = series.set_index("observation_date")["value"]
        wow_prior = _lookback_value(series_indexed, latest_date, days=7)
        mom_prior = _lookback_value(series_indexed, latest_date, days=30)
        status = DataStatus(latest_row["status"]) if latest_row["status"] in DataStatus._value2member_map_ else DataStatus.UNAVAILABLE
        meta = SourceMeta(
            source=latest_row["source"],
            observation_date=latest_date,
            frequency=latest_row["frequency"],
            status=status,
            license_note=latest_row.get("license_note", "") or "",
        )
        views[metric] = MetricView(
            label=metric,
            latest_value=latest_value,
            latest_unit=latest_row["unit"],
            latest_date=latest_date,
            wow_change_pct=_pct_change(latest_value, wow_prior),
            mom_change_pct=_pct_change(latest_value, mom_prior),
            history=series,
            source_meta=meta,
        )
    return views


def get_chokepoint_views(conn: duckdb.DuckDBPyConnection) -> dict:
    """One view per tracked maritime chokepoint (IMF PortWatch, weekly AIS-derived vessel transits)."""
    return get_metric_views_for_segment(conn, "Chokepoint")


def get_macro_indicator_views(conn: duckdb.DuckDBPyConnection) -> dict:
    """Reference-rate / benchmark-price views (FRED, EIA), plus documented gaps.

    The EU ETS carbon allowance (EUA) price is always included as an explicit "Not available" gap
    rather than silently omitted -- no genuinely free, no-key, documented API was confirmed for it
    (see docs/source_register.md). This keeps the page honest about what it does and does not cover,
    per the project's core "never fabricate, always label" rule.
    """
    views = get_metric_views_for_segment(conn, "Macro")
    if "EU ETS carbon allowance (EUA) price" not in views:
        views["EU ETS carbon allowance (EUA) price"] = _unavailable_view(
            "EU ETS carbon allowance (EUA) price",
            "Daily EUA price is exchange-derived (ICE/EEX). No genuinely free, no-key, documented "
            "API was confirmed as of August 2026 -- available via Trading Economics, Databento or a "
            "licensed ICE/EEX feed, or as a manual monthly entry. See docs/source_register.md.",
        )
    return views
