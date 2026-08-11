import json
import urllib.error
from unittest.mock import patch, MagicMock

from src.adapters.sec_edgar_xbrl_adapter import SECEdgarXBRLFinancialsAdapter
from src.data_model import DataStatus


def _fake_response(payload: dict):
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(payload).encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp
    mock_resp.__exit__.return_value = False
    return mock_resp


def _companyfacts(revenue=None, cash=None, debt=None, dividend=None, forms="20-F"):
    """Build a minimal companyfacts payload with only the concepts under test populated."""
    facts = {"us-gaap": {}, "ifrs-full": {}}

    def _unit_entries(value, unit_key="USD", duration=True):
        entry = {
            "end": "2025-12-31",
            "val": value,
            "fy": 2025,
            "fp": "FY",
            "form": forms,
            "filed": "2026-04-15",
        }
        if duration:
            entry["start"] = "2025-01-01"
        return {"units": {unit_key: [entry]}}

    if revenue is not None:
        facts["us-gaap"]["Revenues"] = _unit_entries(revenue)
    if cash is not None:
        facts["us-gaap"]["CashAndCashEquivalentsAtCarryingValue"] = _unit_entries(cash, duration=False)
    if debt is not None:
        facts["us-gaap"]["LongTermDebtNoncurrent"] = _unit_entries(debt, duration=False)
    if dividend is not None:
        facts["us-gaap"]["CommonStockDividendsPerShareDeclared"] = _unit_entries(
            dividend, unit_key="USD/shares", duration=True
        )
    return {"facts": facts}


def test_extracts_revenue_and_cash_as_live():
    payload = _companyfacts(revenue=500_000_000, cash=80_000_000)
    with patch("src.adapters.sec_edgar_xbrl_adapter.urllib.request.urlopen",
               return_value=_fake_response(payload)):
        df = SECEdgarXBRLFinancialsAdapter(ciks={"Hafnia": "1815779"}).fetch()

    revenue_row = df[df["metric"] == "revenue"].iloc[0]
    assert revenue_row["value"] == 500.0
    assert revenue_row["unit"] == "usd_million"
    assert revenue_row["status"] == DataStatus.LIVE.value
    assert revenue_row["period"] == "FY2025"

    cash_row = df[df["metric"] == "cash"].iloc[0]
    assert cash_row["value"] == 80.0


def test_net_debt_only_computed_when_both_debt_and_cash_present():
    payload = _companyfacts(cash=80_000_000, debt=410_000_000)
    with patch("src.adapters.sec_edgar_xbrl_adapter.urllib.request.urlopen",
               return_value=_fake_response(payload)):
        df = SECEdgarXBRLFinancialsAdapter(ciks={"BW LPG": "1649313"}).fetch()

    net_debt_row = df[df["metric"] == "net_debt"].iloc[0]
    assert net_debt_row["value"] == 330.0  # (410m - 80m) / 1e6
    assert net_debt_row["status"] == DataStatus.ESTIMATED.value
    assert "Derived" in net_debt_row["license_note"]


def test_net_debt_not_fabricated_when_debt_tag_missing():
    payload = _companyfacts(cash=80_000_000)  # no debt tag at all
    with patch("src.adapters.sec_edgar_xbrl_adapter.urllib.request.urlopen",
               return_value=_fake_response(payload)):
        df = SECEdgarXBRLFinancialsAdapter(ciks={"Flex LNG": "1772253"}).fetch()

    assert "net_debt" not in set(df["metric"]) if not df.empty else True


def test_quarterly_6k_forms_are_excluded():
    """FPIs' 6-K quarterly press releases are not reliably XBRL-tagged; even if a 6-K happened to
    carry a tagged value, this adapter must not treat it as an annual figure."""
    payload = _companyfacts(revenue=500_000_000, forms="6-K")
    with patch("src.adapters.sec_edgar_xbrl_adapter.urllib.request.urlopen",
               return_value=_fake_response(payload)):
        df = SECEdgarXBRLFinancialsAdapter(ciks={"Hafnia": "1815779"}).fetch()
    assert df.empty


def test_handles_network_failure_gracefully():
    with patch("src.adapters.sec_edgar_xbrl_adapter.urllib.request.urlopen",
               side_effect=urllib.error.URLError("blocked")):
        df = SECEdgarXBRLFinancialsAdapter(ciks={"Hafnia": "1815779"}).fetch()
    assert df.empty


def test_skips_when_no_ciks_configured():
    df = SECEdgarXBRLFinancialsAdapter(ciks={}).fetch()
    assert df.empty


def test_reuses_same_cik_registry_as_filing_alerts_adapter():
    from src.adapters.sec_edgar_adapter import SEC_EDGAR_CIKS
    assert SECEdgarXBRLFinancialsAdapter().ciks == SEC_EDGAR_CIKS
