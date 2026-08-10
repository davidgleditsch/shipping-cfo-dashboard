import pandas as pd

from src.db import latest_per_key, log_manual_upload, upsert_dataframe


def test_schema_created(conn):
    tables = {row[0] for row in conn.execute("SHOW TABLES").fetchall()}
    assert {"market_data_daily", "fleet_fundamentals", "company_market_data",
            "company_financials", "news_events", "manual_upload_log"} <= tables


def test_upsert_dataframe_inserts_and_dedupes(conn):
    df = pd.DataFrame([{
        "segment": "Dry bulk", "metric": "BDI", "value": 1400.0, "unit": "index_pts",
        "observation_date": "2026-07-01", "source": "Baltic Exchange", "frequency": "daily",
        "status": "manual", "license_note": "",
    }])
    n1 = upsert_dataframe(conn, "market_data_daily", df)
    assert n1 == 1
    # inserting the exact same row again (same natural key) should not duplicate
    n2 = upsert_dataframe(conn, "market_data_daily", df)
    assert n2 == 0
    total = conn.execute("SELECT COUNT(*) FROM market_data_daily").fetchone()[0]
    assert total == 1


def test_upsert_preserves_history_for_new_dates(conn):
    df1 = pd.DataFrame([{
        "segment": "Dry bulk", "metric": "BDI", "value": 1400.0, "unit": "index_pts",
        "observation_date": "2026-07-01", "source": "Baltic Exchange", "frequency": "daily",
        "status": "manual", "license_note": "",
    }])
    df2 = pd.DataFrame([{
        "segment": "Dry bulk", "metric": "BDI", "value": 1420.0, "unit": "index_pts",
        "observation_date": "2026-07-02", "source": "Baltic Exchange", "frequency": "daily",
        "status": "manual", "license_note": "",
    }])
    upsert_dataframe(conn, "market_data_daily", df1)
    upsert_dataframe(conn, "market_data_daily", df2)
    total = conn.execute("SELECT COUNT(*) FROM market_data_daily").fetchone()[0]
    assert total == 2


def test_latest_per_key(conn):
    df = pd.DataFrame([
        {"segment": "Dry bulk", "metric": "BDI", "value": 1400.0, "unit": "index_pts",
         "observation_date": "2026-07-01", "source": "X", "frequency": "daily", "status": "manual", "license_note": ""},
        {"segment": "Dry bulk", "metric": "BDI", "value": 1420.0, "unit": "index_pts",
         "observation_date": "2026-07-02", "source": "X", "frequency": "daily", "status": "manual", "license_note": ""},
    ])
    upsert_dataframe(conn, "market_data_daily", df)
    latest = latest_per_key(conn, "market_data_daily", ["segment", "metric"])
    assert len(latest) == 1
    assert latest.iloc[0]["value"] == 1420.0


def test_log_manual_upload(conn):
    log_manual_upload(conn, "test.csv", "market_data_daily", 5, "valid", "")
    row = conn.execute("SELECT * FROM manual_upload_log").fetchone()
    assert row is not None
