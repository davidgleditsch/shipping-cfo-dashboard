import pandas as pd
import pytest

from src.data_model import DataStatus
from src.db import upsert_dataframe
from src.pages_logic.cfo_monitor import SignalLevel, get_company_signals
from src.pages_logic.fleet_fundamentals import get_segment_fundamentals
from src.pages_logic.freight_markets import get_segment_rate_view
from src.pages_logic.listed_companies import get_company_views
from src.pages_logic.news_events import get_category_counts


def test_freight_view_unavailable_when_no_data(conn):
    view = get_segment_rate_view(conn, "Dry bulk")
    assert view.latest_value is None
    assert view.source_meta.status == DataStatus.UNAVAILABLE


def test_freight_view_computes_changes(conn):
    df = pd.DataFrame([
        {"segment": "Dry bulk", "metric": "BDI", "value": 1000.0, "unit": "index_pts",
         "observation_date": "2026-06-01", "source": "Baltic Exchange", "frequency": "daily",
         "status": "manual", "license_note": ""},
        {"segment": "Dry bulk", "metric": "BDI", "value": 1100.0, "unit": "index_pts",
         "observation_date": "2026-07-01", "source": "Baltic Exchange", "frequency": "daily",
         "status": "manual", "license_note": ""},
    ])
    upsert_dataframe(conn, "market_data_daily", df)
    view = get_segment_rate_view(conn, "Dry bulk")
    assert view.latest_value == 1100.0
    assert view.mom_change_pct == pytest.approx(10.0, rel=1e-3)


def test_fleet_fundamentals_unavailable_by_default(conn):
    view = get_segment_fundamentals(conn, "Container")
    for metric_key, mv in view.metrics.items():
        assert mv.value is None
        assert mv.source_meta.status == DataStatus.UNAVAILABLE


def test_listed_companies_views_cover_full_watchlist(conn):
    views = get_company_views(conn)
    assert len(views) == 10
    assert all(v.nav_status.startswith("Requires vessel-value assumptions") for v in views)


def test_cfo_signals_include_all_ten_categories(conn):
    signals = get_company_signals(conn, "CMB.TECH")
    assert len(signals) == 10
    ids = {s.id for s in signals}
    assert "refinancing_maturity" in ids
    assert "weak_contract_coverage" in ids


def test_cfo_signal_liquidity_alert_when_low_cash(conn):
    df = pd.DataFrame([
        {"company": "CMB.TECH", "metric": "cash", "period": "Q2 2026", "value": 1.0,
         "unit": "usd_million", "observation_date": "2026-07-01", "source": "Filing",
         "frequency": "quarterly", "status": "manual", "license_note": ""},
        {"company": "CMB.TECH", "metric": "net_debt", "period": "Q2 2026", "value": 500.0,
         "unit": "usd_million", "observation_date": "2026-07-01", "source": "Filing",
         "frequency": "quarterly", "status": "manual", "license_note": ""},
    ])
    upsert_dataframe(conn, "company_financials", df)
    signals = get_company_signals(conn, "CMB.TECH")
    liquidity = next(s for s in signals if s.id == "liquidity_pressure")
    assert liquidity.level == SignalLevel.ALERT


def test_news_category_counts_covers_all_categories(conn):
    counts = get_category_counts(conn)
    assert len(counts) == len(set(counts["category"]))
