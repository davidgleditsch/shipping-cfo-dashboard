import json
import urllib.error
from unittest.mock import patch, MagicMock

from src.adapters.imf_portwatch_adapter import IMFPortWatchAdapter
from src.data_model import DataStatus


def _fake_response(payload: dict):
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(payload).encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp
    mock_resp.__exit__.return_value = False
    return mock_resp


def _feature(chokepoint: str, dt: str, n_total: float) -> dict:
    return {"attributes": {"chokepoint": chokepoint, "date": dt, "n_total": n_total}}


def test_parses_successful_response_and_keeps_latest_per_chokepoint():
    payload = {
        "features": [
            _feature("Suez Canal", "2026-08-01", 45),
            _feature("Suez Canal", "2026-08-08", 51),  # later date, same chokepoint -- should win
            _feature("Panama Canal", "2026-08-08", 30),
            _feature("Not A Tracked Chokepoint", "2026-08-08", 999),  # should be ignored
        ]
    }
    with patch("src.adapters.imf_portwatch_adapter.urllib.request.urlopen", return_value=_fake_response(payload)):
        df = IMFPortWatchAdapter(chokepoints=("Suez Canal", "Panama Canal")).fetch()

    assert len(df) == 2
    assert set(df["segment"]) == {"Chokepoint"}
    suez_row = df[df["metric"].str.contains("Suez")].iloc[0]
    assert suez_row["value"] == 51.0
    assert suez_row["status"] == DataStatus.LIVE.value
    assert str(suez_row["observation_date"]) == "2026-08-08"


def test_handles_network_failure_gracefully():
    with patch("src.adapters.imf_portwatch_adapter.urllib.request.urlopen",
               side_effect=urllib.error.URLError("network down")):
        df = IMFPortWatchAdapter().fetch()
    assert df.empty


def test_handles_empty_features_gracefully():
    with patch("src.adapters.imf_portwatch_adapter.urllib.request.urlopen",
               return_value=_fake_response({"features": []})):
        df = IMFPortWatchAdapter().fetch()
    assert df.empty


def test_handles_unrecognized_schema_without_guessing():
    payload = {"features": [{"attributes": {"totally_unexpected_field": 1}}]}
    with patch("src.adapters.imf_portwatch_adapter.urllib.request.urlopen", return_value=_fake_response(payload)):
        df = IMFPortWatchAdapter().fetch()
    assert df.empty


def test_handles_no_matching_chokepoints():
    payload = {"features": [_feature("Some Unrelated Strait", "2026-08-08", 10)]}
    with patch("src.adapters.imf_portwatch_adapter.urllib.request.urlopen", return_value=_fake_response(payload)):
        df = IMFPortWatchAdapter(chokepoints=("Suez Canal",)).fetch()
    assert df.empty
