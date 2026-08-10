"""Pure logic for the Fleet Fundamentals page."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Optional

import duckdb

from src.config import FREIGHT_SEGMENTS
from src.data_model import DataStatus, SourceMeta

FUNDAMENTAL_METRICS = [
    ("trading_fleet_count", "Trading fleet"),
    ("orderbook_units", "Orderbook (vessels)"),
    ("orderbook_pct_fleet", "Orderbook as % of fleet"),
    ("expected_deliveries_units", "Expected deliveries"),
    ("scrapping_units", "Scrapping (vessels)"),
    ("avg_fleet_age_years", "Average fleet age"),
    ("pct_fleet_over_20yrs", "Share of fleet 20yrs+"),
]


@dataclass
class MetricValue:
    label: str
    value: Optional[float]
    unit: Optional[str]
    source_meta: SourceMeta


@dataclass
class SegmentFundamentalsView:
    segment: str
    metrics: dict[str, MetricValue] = field(default_factory=dict)


def get_segment_fundamentals(conn: duckdb.DuckDBPyConnection, segment: str) -> SegmentFundamentalsView:
    df = conn.execute(
        "SELECT * FROM fleet_fundamentals WHERE segment = ? ORDER BY observation_date DESC",
        [segment],
    ).df()

    metrics: dict[str, MetricValue] = {}
    for metric_key, label in FUNDAMENTAL_METRICS:
        rows = df[df["metric"] == metric_key]
        if rows.empty:
            meta = SourceMeta(source="No manual data uploaded", observation_date=None,
                               frequency="n/a", status=DataStatus.UNAVAILABLE)
            metrics[metric_key] = MetricValue(label, None, None, meta)
            continue
        latest = rows.iloc[0]  # already sorted desc
        status = DataStatus(latest["status"]) if latest["status"] in DataStatus._value2member_map_ else DataStatus.MANUAL
        meta = SourceMeta(
            source=latest["source"], observation_date=latest["observation_date"],
            frequency=latest["frequency"], status=status,
            license_note=latest.get("license_note", "") or "",
        )
        metrics[metric_key] = MetricValue(label, float(latest["value"]), latest["unit"], meta)

    return SegmentFundamentalsView(segment=segment, metrics=metrics)


def get_all_segment_fundamentals(conn: duckdb.DuckDBPyConnection) -> dict[str, SegmentFundamentalsView]:
    return {seg: get_segment_fundamentals(conn, seg) for seg in FREIGHT_SEGMENTS}
