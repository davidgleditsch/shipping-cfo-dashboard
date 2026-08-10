import json
import urllib.error
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from src.adapters.sec_edgar_adapter import SECEdgarFilingsAdapter


def _fake_response(payload: dict):
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(payload).encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp
    mock_resp.__exit__.return_value = False
    return mock_resp


def _submissions_payload(recent_date: str, older_date: str):
    return {
        "filings": {
            "recent": {
                "form": ["6-K", "6-K", "S-8"],
                "filingDate": [recent_date, older_date, recent_date],
                "accessionNumber": ["0001104659-26-000123", "0001104659-25-000045", "0001104659-26-000200"],
                "primaryDocument": ["ex99.htm", "ex99.htm", "s8.htm"],
            }
        }
    }


def test_sec_edgar_filters_to_recent_relevant_forms():
    today = datetime.utcnow().date()
    recent = today.isoformat()
    old = (today - timedelta(days=400)).isoformat()
    payload = _submissions_payload(recent, old)
    with patch("src.adapters.sec_edgar_adapter.urllib.request.urlopen", return_value=_fake_response(payload)):
        df = SECEdgarFilingsAdapter(ciks={"Hafnia": "1815779"}, lookback_days=120).fetch()
    # only the recent 6-K should survive: the older 6-K is out of lookback window, the S-8 is not a
    # form type this adapter cares about
    assert len(df) == 1
    assert "Hafnia" in df.iloc[0]["headline"]
    assert df.iloc[0]["category"] == "Company reporting"
    assert "sec.gov" in df.iloc[0]["url"]


def test_sec_edgar_handles_network_failure_gracefully():
    with patch("src.adapters.sec_edgar_adapter.urllib.request.urlopen", side_effect=urllib.error.URLError("blocked")):
        df = SECEdgarFilingsAdapter(ciks={"Hafnia": "1815779"}).fetch()
    assert df.empty


def test_sec_edgar_skips_companies_with_no_cik_configured():
    df = SECEdgarFilingsAdapter(ciks={}).fetch()
    assert df.empty
