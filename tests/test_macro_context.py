import pandas as pd

from src.data_model import DataStatus
from src.db import upsert_dataframe
from src.pages_logic.macro_context import get_chokepoint_views, get_macro_indicator_views


def test_chokepoint_views_empty_when_no_data(conn):
    assert get_chokepoint_views(conn) == {}


def test_chokepoint_views_computes_wow_change(conn):
    df = pd.DataFrame([
        {"segment": "Chokepoint", "metric": "Suez Canal — daily vessel transits", "value": 40.0,
         "unit": "vessels/day", "observation_date": "2026-08-01", "source": "IMF PortWatch",
         "frequency": "weekly", "status": "live", "license_note": ""},
        {"segment": "Chokepoint", "metric": "Suez Canal — daily vessel transits", "value": 44.0,
         "unit": "vessels/day", "observation_date": "2026-08-08", "source": "IMF PortWatch",
         "frequency": "weekly", "status": "live", "license_note": ""},
    ])
    upsert_dataframe(conn, "market_data_daily", df)
    views = get_chokepoint_views(conn)
    assert len(views) == 1
    v = views["Suez Canal — daily vessel transits"]
    assert v.latest_value == 44.0
    assert v.wow_change_pct == 10.0


def test_macro_indicator_views_always_include_eua_gap(conn):
    views = get_macro_indicator_views(conn)
    assert "EU ETS carbon allowance (EUA) price" in views
    eua = views["EU ETS carbon allowance (EUA) price"]
    assert eua.latest_value is None
    assert eua.source_meta.status == DataStatus.UNAVAILABLE


def test_macro_indicator_views_includes_real_data_alongside_eua_gap(conn):
    df = pd.DataFrame([
        {"segment": "Macro", "metric": "SOFR (Secured Overnight Financing Rate)", "value": 4.33,
         "unit": "percent", "observation_date": "2026-08-11", "source": "FRED",
         "frequency": "daily", "status": "live", "license_note": ""},
    ])
    upsert_dataframe(conn, "market_data_daily", df)
    views = get_macro_indicator_views(conn)
    assert views["SOFR (Secured Overnight Financing Rate)"].latest_value == 4.33
    assert "EU ETS carbon allowance (EUA) price" in views  # gap still shown alongside real data
