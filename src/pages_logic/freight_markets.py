"""Pure logic for the Freight Markets page — testable without Streamlit."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional

import duckdb
import pandas as pd

from src.config import FREIGHT_SEGMENTS
from src.data_model import DataStatus, SourceMeta

SEGMENT_METHODOLOGY = {
    "Dry bulk": "Baltic Dry Index (BDI) and sub-indices track time-charter-equivalent earnings across Capesize/Panamax/Supramax/Handysize routes.",
    "Container": "Freight indices (e.g. SCFI, WCI) track spot container freight rates on major East-West trade lanes.",
    "Crude tanker": "Worldscale (WS) rates and TCE track crude tanker earnings on benchmark VLCC/Suezmax/Aframax routes.",
    "Product tanker": "Worldscale (WS) rates and TCE track clean/dirty product tanker earnings on benchmark routes.",
    "LNG": "Spot time-charter-equivalent (TCE) day rates for LNG carriers on benchmark trade routes.",
    "LPG": "Baltic LPG index and spot freight rates for VLGC routes (e.g. Middle East–Japan).",
    "Car carrier": "Time-charter rates for pure car and truck carriers (PCTC), benchmarked by vessel size.",
}


@dataclass
class SegmentRateView:
    segment: str
    latest_value: Optional[float]
    latest_unit: Optional[str]
    latest_date: Optional[date]
    wow_change_pct: Optional[float]
    mom_change_pct: Optional[float]
    history: pd.DataFrame
    source_meta: SourceMeta
    methodology: str


def _pct_change(latest: float, prior: Optional[float]) -> Optional[float]:
    if prior is None or prior == 0:
        return None
    return (latest - prior) / abs(prior) * 100.0


def get_segment_rate_view(conn: duckdb.DuckDBPyConnection, segment: str) -> SegmentRateView:
    df = conn.execute(
        "SELECT * FROM market_data_daily WHERE segment = ? ORDER BY observation_date ASC",
        [segment],
    ).df()

    methodology = SEGMENT_METHODOLOGY.get(segment, "")

    if df.empty:
        meta = SourceMeta(source="No manual or automated source connected", observation_date=None,
                           frequency="n/a", status=DataStatus.UNAVAILABLE)
        return SegmentRateView(segment, None, None, None, None, None, df, meta, methodology)

    # if multiple metrics exist for a segment, use the most recently observed metric series
    latest_metric = df.sort_values("observation_date").iloc[-1]["metric"]
    series = df[df["metric"] == latest_metric].sort_values("observation_date")

    latest_row = series.iloc[-1]
    latest_value = latest_row["value"]
    latest_date = latest_row["observation_date"]
    latest_unit = latest_row["unit"]
    status = DataStatus(latest_row["status"]) if latest_row["status"] in DataStatus._value2member_map_ else DataStatus.UNAVAILABLE

    series_indexed = series.set_index("observation_date")["value"]
    wow_prior = _lookback_value(series_indexed, latest_date, days=7)
    mom_prior = _lookback_value(series_indexed, latest_date, days=30)

    meta = SourceMeta(
        source=latest_row["source"],
        observation_date=latest_date,
        frequency=latest_row["frequency"],
        status=status,
        license_note=latest_row.get("license_note", "") or "",
    )

    return SegmentRateView(
        segment=segment,
        latest_value=float(latest_value),
        latest_unit=latest_unit,
        latest_date=latest_date,
        wow_change_pct=_pct_change(float(latest_value), wow_prior),
        mom_change_pct=_pct_change(float(latest_value), mom_prior),
        history=series,
        source_meta=meta,
        methodology=methodology,
    )


def _lookback_value(series: pd.Series, latest_date, days: int) -> Optional[float]:
    target = pd.Timestamp(latest_date) - pd.Timedelta(days=days)
    eligible = series[series.index.map(pd.Timestamp) <= target]
    if eligible.empty:
        return None
    return float(eligible.iloc[-1])


def get_all_segment_views(conn: duckdb.DuckDBPyConnection) -> dict[str, SegmentRateView]:
    return {seg: get_segment_rate_view(conn, seg) for seg in FREIGHT_SEGMENTS}
