import json
import urllib.error
from unittest.mock import patch, MagicMock

import pandas as pd

from src.adapters.fx_adapter import FXRateAdapter
from src.data_model import DataStatus


def _fake_response(payload: dict):
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(payload).encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp
    mock_resp.__exit__.return_value = False
    return mock_resp


def test_fx_adapter_parses_successful_response():
    payload = {"amount": 1.0, "base": "USD", "date": "2026-07-24", "rates": {"NOK": 9.5702}}
    with patch("src.adapters.fx_adapter.urllib.request.urlopen", return_value=_fake_response(payload)):
        df = FXRateAdapter(base="USD", quotes=("NOK",)).fetch()
    assert len(df) == 1
    row = df.iloc[0]
    assert row["metric"] == "USDNOK"
    assert row["value"] == 9.5702
    assert row["segment"] == "FX"
    assert row["status"] == DataStatus.LIVE.value


def test_fx_adapter_handles_network_failure_gracefully():
    with patch("src.adapters.fx_adapter.urllib.request.urlopen", side_effect=urllib.error.URLError("network down")):
        df = FXRateAdapter(base="USD", quotes=("NOK",)).fetch()
    assert df.empty


def test_fx_adapter_skips_malformed_response():
    payload = {"amount": 1.0, "base": "USD", "date": "2026-07-24", "rates": {}}
    with patch("src.adapters.fx_adapter.urllib.request.urlopen", return_value=_fake_response(payload)):
        df = FXRateAdapter(base="USD", quotes=("NOK",)).fetch()
    assert df.empty
