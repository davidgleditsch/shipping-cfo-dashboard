import json
import urllib.error
from unittest.mock import patch, MagicMock

from src.adapters.eia_adapter import EIASpotPriceAdapter
from src.data_model import DataStatus


def _fake_response(payload: dict):
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(payload).encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp
    mock_resp.__exit__.return_value = False
    return mock_resp


def test_skips_entirely_when_api_key_missing():
    df = EIASpotPriceAdapter(api_key="").fetch()
    assert df.empty


def test_parses_successful_response_for_both_products():
    payload = {"response": {"data": [{"period": "2026-08-12", "value": "71.40"}]}}
    with patch("src.adapters.eia_adapter.urllib.request.urlopen", return_value=_fake_response(payload)):
        df = EIASpotPriceAdapter(api_key="fake-key").fetch()
    assert len(df) == 2  # Brent + WTI, both hitting the same mocked response
    assert set(df["segment"]) == {"Macro"}
    assert all(df["status"] == DataStatus.LIVE.value)
    assert all(df["value"] == 71.40)


def test_handles_network_failure_gracefully():
    with patch("src.adapters.eia_adapter.urllib.request.urlopen", side_effect=urllib.error.URLError("down")):
        df = EIASpotPriceAdapter(api_key="fake-key").fetch()
    assert df.empty


def test_handles_empty_data_gracefully():
    with patch("src.adapters.eia_adapter.urllib.request.urlopen",
               return_value=_fake_response({"response": {"data": []}})):
        df = EIASpotPriceAdapter(api_key="fake-key").fetch()
    assert df.empty
