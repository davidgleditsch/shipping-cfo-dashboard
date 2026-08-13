import json
import urllib.error
from unittest.mock import patch, MagicMock

from src.adapters.fred_adapter import FREDRateAdapter
from src.data_model import DataStatus


def _fake_response(payload: dict):
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(payload).encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp
    mock_resp.__exit__.return_value = False
    return mock_resp


def test_skips_entirely_when_api_key_missing():
    df = FREDRateAdapter(api_key="").fetch()
    assert df.empty


def test_parses_successful_response_using_first_non_missing_observation():
    payload = {"observations": [
        {"date": "2026-08-12", "value": "."},  # most recent, but missing -- must be skipped
        {"date": "2026-08-11", "value": "4.33"},
    ]}
    with patch("src.adapters.fred_adapter.urllib.request.urlopen", return_value=_fake_response(payload)):
        df = FREDRateAdapter(api_key="fake-key").fetch()
    assert len(df) == 1
    row = df.iloc[0]
    assert row["value"] == 4.33
    assert row["segment"] == "Macro"
    assert row["status"] == DataStatus.LIVE.value
    assert str(row["observation_date"]) == "2026-08-11"


def test_handles_network_failure_gracefully():
    with patch("src.adapters.fred_adapter.urllib.request.urlopen", side_effect=urllib.error.URLError("down")):
        df = FREDRateAdapter(api_key="fake-key").fetch()
    assert df.empty


def test_handles_all_missing_observations_gracefully():
    payload = {"observations": [{"date": "2026-08-12", "value": "."}]}
    with patch("src.adapters.fred_adapter.urllib.request.urlopen", return_value=_fake_response(payload)):
        df = FREDRateAdapter(api_key="fake-key").fetch()
    assert df.empty
