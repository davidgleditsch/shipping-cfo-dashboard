"""Shared enums and dataclasses used across adapters and pages."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Optional


class DataStatus(str, Enum):
    """Every metric shown to the user must declare one of these. Never left ambiguous."""

    LIVE = "live"
    DELAYED = "delayed"
    MANUAL = "manual"
    ESTIMATED = "estimated"
    SAMPLE = "sample"
    UNAVAILABLE = "unavailable"

    @property
    def label(self) -> str:
        return {
            DataStatus.LIVE: "Live",
            DataStatus.DELAYED: "Delayed",
            DataStatus.MANUAL: "Manually entered",
            DataStatus.ESTIMATED: "Estimated",
            DataStatus.SAMPLE: "Sample (illustrative only)",
            DataStatus.UNAVAILABLE: "Not available",
        }[self]

    @property
    def color(self) -> str:
        return {
            DataStatus.LIVE: "#1a7f37",
            DataStatus.DELAYED: "#9a6700",
            DataStatus.MANUAL: "#0969da",
            DataStatus.ESTIMATED: "#8250df",
            DataStatus.SAMPLE: "#6e7781",
            DataStatus.UNAVAILABLE: "#cf222e",
        }[self]


@dataclass
class SourceMeta:
    """Provenance block rendered under every metric/chart."""

    source: str
    observation_date: Optional[date]
    frequency: str
    status: DataStatus
    license_note: str = ""
    url: Optional[str] = None

    def caption(self) -> str:
        date_str = self.observation_date.isoformat() if self.observation_date else "n/a"
        return f"Source: {self.source} · Observed: {date_str} · Frequency: {self.frequency} · {self.status.label}"


@dataclass
class MetricPoint:
    entity: str          # e.g. segment name or company name
    metric: str          # e.g. "BDI", "orderbook_pct_fleet", "revenue"
    value: Optional[float]
    unit: str
    observation_date: date
    source: str
    frequency: str
    status: DataStatus
    ingested_at: datetime = field(default_factory=datetime.utcnow)
    notes: str = ""
