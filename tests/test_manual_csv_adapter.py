import pandas as pd

from src.adapters.manual_csv_adapter import validate_csv


def test_valid_freight_rates_csv():
    df = pd.DataFrame([
        {"segment": "Dry bulk", "metric": "BDI", "value": 1450, "unit": "index_pts",
         "observation_date": "2026-07-20", "source": "Baltic Exchange", "frequency": "daily"},
    ])
    result = validate_csv("freight_rates", df)
    assert result.is_valid
    assert len(result.cleaned) == 1
    assert result.cleaned.iloc[0]["status"] == "manual"


def test_missing_column_is_rejected():
    df = pd.DataFrame([{"segment": "Dry bulk", "value": 1450}])
    result = validate_csv("freight_rates", df)
    assert not result.is_valid
    assert any("Missing required column" in e for e in result.errors)


def test_non_numeric_value_is_rejected():
    df = pd.DataFrame([
        {"segment": "Dry bulk", "metric": "BDI", "value": "not-a-number", "unit": "index_pts",
         "observation_date": "2026-07-20", "source": "Baltic Exchange", "frequency": "daily"},
    ])
    result = validate_csv("freight_rates", df)
    assert not result.is_valid


def test_unrecognized_segment_is_rejected():
    df = pd.DataFrame([
        {"segment": "Bananas", "metric": "BDI", "value": 1450, "unit": "index_pts",
         "observation_date": "2026-07-20", "source": "Baltic Exchange", "frequency": "daily"},
    ])
    result = validate_csv("freight_rates", df)
    assert not result.is_valid
    assert any("Unrecognized segment" in e for e in result.errors)


def test_future_date_triggers_warning_not_error():
    df = pd.DataFrame([
        {"segment": "Dry bulk", "metric": "BDI", "value": 1450, "unit": "index_pts",
         "observation_date": "2099-01-01", "source": "Baltic Exchange", "frequency": "daily"},
    ])
    result = validate_csv("freight_rates", df)
    assert result.is_valid
    assert any("future observation_date" in w for w in result.warnings)


def test_company_financials_unknown_company_is_warning_only():
    df = pd.DataFrame([
        {"company": "Not A Real Company", "metric": "revenue", "period": "Q2 2026", "value": 100,
         "unit": "usd_million", "observation_date": "2026-07-20", "source": "Filing", "frequency": "quarterly"},
    ])
    result = validate_csv("company_financials", df)
    assert result.is_valid
    assert any("not in the current watchlist" in w for w in result.warnings)


def test_empty_file_is_rejected():
    df = pd.DataFrame(columns=["segment", "metric", "value", "unit", "observation_date", "source", "frequency"])
    result = validate_csv("freight_rates", df)
    assert not result.is_valid


def test_in_file_duplicate_rows_rejected():
    df = pd.DataFrame([
        {"segment": "Dry bulk", "metric": "BDI", "value": 1450, "unit": "index_pts",
         "observation_date": "2026-07-20", "source": "Baltic Exchange", "frequency": "daily"},
        {"segment": "Dry bulk", "metric": "BDI", "value": 1460, "unit": "index_pts",
         "observation_date": "2026-07-20", "source": "Baltic Exchange", "frequency": "daily"},
    ])
    result = validate_csv("freight_rates", df)
    assert not result.is_valid
    assert any("Duplicate rows" in e for e in result.errors)


def test_row_count_limit_enforced():
    from src.adapters.manual_csv_adapter import MAX_ROWS_PER_UPLOAD
    df = pd.DataFrame([
        {"segment": "Dry bulk", "metric": "BDI", "value": 1000 + i, "unit": "index_pts",
         "observation_date": "2026-07-20", "source": "Baltic Exchange", "frequency": "daily"}
        for i in range(MAX_ROWS_PER_UPLOAD + 1)
    ])
    result = validate_csv("freight_rates", df)
    assert not result.is_valid
    assert any("exceeds" in e for e in result.errors)


def test_unit_mismatch_triggers_warning_not_error():
    df = pd.DataFrame([
        {"segment": "Dry bulk", "metric": "trading_fleet_count", "value": 4200, "unit": "ships",
         "observation_date": "2026-06-30", "source": "Clarksons", "frequency": "monthly"},
    ])
    result = validate_csv("fleet_fundamentals", df)
    assert result.is_valid
    assert any("usually reported in 'vessels'" in w for w in result.warnings)


def test_outlier_jump_warns_against_db_history(conn):
    from src.db import upsert_dataframe
    existing = pd.DataFrame([
        {"segment": "Dry bulk", "metric": "trading_fleet_count", "value": 4000.0, "unit": "vessels",
         "observation_date": "2026-05-31", "source": "Clarksons", "frequency": "monthly",
         "status": "manual", "license_note": ""},
    ])
    upsert_dataframe(conn, "fleet_fundamentals", existing)

    new_upload = pd.DataFrame([
        {"segment": "Dry bulk", "metric": "trading_fleet_count", "value": 9000, "unit": "vessels",
         "observation_date": "2026-06-30", "source": "Clarksons", "frequency": "monthly"},
    ])
    result = validate_csv("fleet_fundamentals", new_upload, conn=conn)
    assert result.is_valid
    assert any("moved" in w for w in result.warnings)


def test_no_outlier_warning_without_conn():
    df = pd.DataFrame([
        {"segment": "Dry bulk", "metric": "trading_fleet_count", "value": 9000, "unit": "vessels",
         "observation_date": "2026-06-30", "source": "Clarksons", "frequency": "monthly"},
    ])
    result = validate_csv("fleet_fundamentals", df)
    assert result.is_valid
    assert not any("moved" in w for w in result.warnings)
