"""Pure logic for the Executive Brief page — pulls a summary across all other pages."""
from __future__ import annotations

import duckdb
import pandas as pd

from src.config import FREIGHT_SEGMENTS
from src.pages_logic.cfo_monitor import SignalLevel, get_all_signals
from src.pages_logic.freight_markets import get_all_segment_views


def get_top_news(conn: duckdb.DuckDBPyConnection, n: int = 5) -> pd.DataFrame:
    return conn.execute(
        "SELECT * FROM news_events ORDER BY published_date DESC LIMIT ?", [n]
    ).df()


def get_company_announcements(conn: duckdb.DuckDBPyConnection, n: int = 5) -> pd.DataFrame:
    return conn.execute(
        "SELECT * FROM news_events WHERE category = 'Company reporting' "
        "ORDER BY published_date DESC LIMIT ?", [n]
    ).df()


def get_segment_heatmap(conn: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    views = get_all_segment_views(conn)
    rows = []
    for seg, v in views.items():
        rows.append({
            "segment": seg,
            "wow_change_pct": v.wow_change_pct,
            "mom_change_pct": v.mom_change_pct,
            "status": v.source_meta.status.value,
        })
    return pd.DataFrame(rows)


def get_rate_movements_table(conn: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    views = get_all_segment_views(conn)
    rows = []
    for seg, v in views.items():
        rows.append({
            "segment": seg,
            "latest_value": v.latest_value,
            "unit": v.latest_unit,
            "observation_date": v.latest_date,
            "wow_change_pct": v.wow_change_pct,
            "mom_change_pct": v.mom_change_pct,
            "status": v.source_meta.status.value,
            "source": v.source_meta.source,
        })
    return pd.DataFrame(rows)


def get_cfo_implications_summary(conn: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Roll up CFO Monitor signals to a count of alerts/warnings per company for the brief."""
    all_signals = get_all_signals(conn)
    rows = []
    for company, signals in all_signals.items():
        alerts = sum(1 for s in signals if s.level == SignalLevel.ALERT)
        warnings = sum(1 for s in signals if s.level == SignalLevel.WARNING)
        unavailable = sum(1 for s in signals if s.level == SignalLevel.UNAVAILABLE)
        rows.append({"company": company, "alerts": alerts, "warnings": warnings, "signals_unavailable": unavailable})
    return pd.DataFrame(rows).sort_values(["alerts", "warnings"], ascending=False)
