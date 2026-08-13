"""SEC EDGAR XBRL company-facts adapter -- free, structured, primary-source company financials.

Fills a narrow but genuine gap documented in docs/source_register.md: the existing
`SECEdgarFilingsAdapter` only surfaces *that a filing happened* (a news item), never the
financial figures inside it. This adapter reads the actual tagged numbers.

Scope, and why it is narrower than the full `company_financials` schema:

- Only the five SEC-registered watchlist names (Hafnia, BW LPG, Flex LNG, Frontline, Okeanis Eco
  Tankers) file with the SEC at all -- the six Oslo Bors-only names have no CIK and are correctly
  skipped (see
  `SEC_EDGAR_CIKS` in `sec_edgar_adapter.py`, reused here rather than duplicated).
- Only concepts that these foreign private issuers reliably tag in inline XBRL are extracted:
  revenue, cash, and (only when both are present for the same period) a *derived* net debt.
  EBITDA, fleet size, contract coverage % and spot exposure % have no standard XBRL tag a foreign
  private issuer is required to use -- guessing which reported number is "EBITDA" from free text
  would be exactly the kind of interpolation the project rules forbid, so those stay
  DataStatus.UNAVAILABLE (manual CSV) rather than being invented here.
- Foreign private issuers are generally not required to tag their 6-K quarterly earnings press
  releases with inline XBRL (only the annual 20-F is reliably tagged), so in practice this adapter
  mostly yields *annual* observations, arriving with the multi-month lag of the 20-F filing itself.
  Quarterly figures remain a manual-CSV gap -- documented, not silently patched over.

Endpoint: https://data.sec.gov/api/xbrl/companyfacts/CIK##########.json
Docs: https://www.sec.gov/os/webmaster-faq#developers, https://www.sec.gov/edgar/sec-api-documentation
Public domain, free, no API key. SEC's fair-access policy requires a descriptive User-Agent header.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from datetime import date, datetime

import pandas as pd

from src.adapters.base import SourceAdapter
from src.adapters.sec_edgar_adapter import SEC_EDGAR_CIKS
from src.data_model import DataStatus
from src.utils.logging_config import get_logger

log = get_logger("adapters.sec_edgar_xbrl")

_COMPANYFACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:0>10}.json"

# Try US-GAAP tags first, then IFRS-full -- these are foreign private issuers, so IFRS is common,
# but some also report supplementary US-GAAP-tagged figures. First matching taxonomy/tag wins.
_REVENUE_CONCEPTS = [("us-gaap", "Revenues"),
                      ("us-gaap", "RevenueFromContractWithCustomerExcludingAssessedTax"),
                      ("ifrs-full", "Revenue")]
_CASH_CONCEPTS = [("us-gaap", "CashAndCashEquivalentsAtCarryingValue"),
                   ("ifrs-full", "CashAndCashEquivalents")]
_DEBT_CONCEPTS = [("us-gaap", "LongTermDebtNoncurrent"),
                   ("us-gaap", "LongTermDebt"),
                   ("ifrs-full", "BorrowingsNoncurrent"),
                   ("ifrs-full", "NoncurrentBorrowings")]
_DIVIDEND_CONCEPTS = [("us-gaap", "CommonStockDividendsPerShareDeclared"),
                       ("us-gaap", "CommonStockDividendsPerShareCashPaid")]

# Only annual filings -- 6-K quarterly press releases are not reliably XBRL-tagged for FPIs (see
# module docstring). Accepting only these two form types is what keeps this adapter from silently
# mixing in unreliable quarterly guesses.
_ANNUAL_FORMS = {"20-F", "20-F/A"}


def _find_first_matching_concept(facts: dict, candidates: list[tuple[str, str]]) -> tuple[str, str, dict] | None:
    for taxonomy, tag in candidates:
        node = facts.get("facts", {}).get(taxonomy, {}).get(tag)
        if node:
            return taxonomy, tag, node
    return None


def _annual_points(concept_node: dict, unit_key: str) -> dict[str, dict]:
    """Return {end_date_iso: {"value": ..., "filed": ..., "fy": ...}} for annual 20-F facts only.

    Deduplicates by period end date, keeping the most recently *filed* value if a figure was
    revised (e.g. 20-F/A amendment) -- matches "preserve historical observations" without keeping
    superseded duplicates for the same fiscal year end.
    """
    points: dict[str, dict] = {}
    for entry in concept_node.get("units", {}).get(unit_key, []):
        if entry.get("form") not in _ANNUAL_FORMS:
            continue
        end = entry.get("end")
        value = entry.get("val")
        filed = entry.get("filed", "")
        if end is None or value is None:
            continue
        # Duration-style facts (revenue) carry both start/end; keep only ~full-year spans so a
        # stub/transition-period filing doesn't get mistaken for a full fiscal year.
        start = entry.get("start")
        if start:
            try:
                span_days = (date.fromisoformat(end) - date.fromisoformat(start)).days
            except ValueError:
                continue
            if span_days < 300:
                continue
        existing = points.get(end)
        if existing is None or filed > existing.get("filed", ""):
            points[end] = {"value": value, "filed": filed, "fy": entry.get("fy")}
    return points


class SECEdgarXBRLFinancialsAdapter(SourceAdapter):
    name = "SEC EDGAR XBRL"
    frequency = "annual (20-F XBRL)"
    license_note = ("US SEC EDGAR XBRL company facts API; public domain, free. Only annual (20-F) "
                     "figures are extracted -- FPI quarterly 6-K press releases are not reliably "
                     "XBRL-tagged, so quarterly company_financials remain a manual-CSV gap.")

    def __init__(self, ciks: dict[str, str] | None = None,
                 contact_email: str = "contact@example.com", timeout: int = 10):
        self.ciks = ciks or SEC_EDGAR_CIKS
        self.user_agent = f"Shipping CFO Intelligence {contact_email}"
        self.timeout = timeout

    def _fetch_facts(self, cik: str) -> dict | None:
        url = _COMPANYFACTS_URL.format(cik=cik)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": self.user_agent})
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (OSError, urllib.error.URLError, ValueError) as exc:
            log.warning("SEC EDGAR XBRL companyfacts fetch failed for CIK %s: %s", cik, exc)
            return None

    def _rows_for_company(self, company: str, cik: str) -> list[dict]:
        facts = self._fetch_facts(cik)
        if not facts:
            return []

        rows: list[dict] = []

        rev_match = _find_first_matching_concept(facts, _REVENUE_CONCEPTS)
        cash_match = _find_first_matching_concept(facts, _CASH_CONCEPTS)
        debt_match = _find_first_matching_concept(facts, _DEBT_CONCEPTS)
        div_match = _find_first_matching_concept(facts, _DIVIDEND_CONCEPTS)

        revenue_points: dict[str, dict] = {}
        cash_points: dict[str, dict] = {}
        debt_points: dict[str, dict] = {}

        if rev_match:
            _, tag, node = rev_match
            revenue_points = _annual_points(node, "USD")
            for end, pt in revenue_points.items():
                rows.append(self._row(company, "revenue", end, pt, tag, DataStatus.LIVE,
                                       divisor=1_000_000, unit="usd_million"))

        if cash_match:
            _, tag, node = cash_match
            cash_points = _annual_points(node, "USD")
            for end, pt in cash_points.items():
                rows.append(self._row(company, "cash", end, pt, tag, DataStatus.LIVE,
                                       divisor=1_000_000, unit="usd_million"))

        if debt_match:
            _, tag, node = debt_match
            debt_points = _annual_points(node, "USD")

        if div_match:
            _, tag, node = div_match
            for end, pt in _annual_points(node, "USD/shares").items():
                rows.append(self._row(company, "dividend_per_share", end, pt, tag, DataStatus.LIVE,
                                       divisor=1, unit="usd_per_share"))

        # Net debt is *derived*, never a raw tag -- only emit it for period ends where both the
        # debt and cash figures exist, and mark it ESTIMATED with a note naming both source tags.
        # This is the one place this adapter computes rather than just reads a number; per project
        # policy that requires the derivation to be visible, not hidden behind a plain "Live" tag.
        if debt_match and cash_points:
            _, debt_tag, _node = debt_match
            for end, debt_pt in debt_points.items():
                cash_pt = cash_points.get(end)
                if cash_pt is None:
                    continue
                net_debt_value = (debt_pt["value"] - cash_pt["value"]) / 1_000_000
                rows.append({
                    "company": company,
                    "metric": "net_debt",
                    "period": self._period_label(end, debt_pt.get("fy")),
                    "value": net_debt_value,
                    "unit": "usd_million",
                    "observation_date": end,
                    "source": self.name,
                    "frequency": self.frequency,
                    "status": DataStatus.ESTIMATED.value,
                    "license_note": (f"Derived as (non-current debt tag '{debt_tag}' minus cash "
                                      f"tag from SEC XBRL) for the same period end -- not a single "
                                      f"reported line item. {self.license_note}"),
                })

        return rows

    def _row(self, company: str, metric: str, end: str, point: dict, tag: str,
              status: DataStatus, divisor: float, unit: str) -> dict:
        return {
            "company": company,
            "metric": metric,
            "period": self._period_label(end, point.get("fy")),
            "value": point["value"] / divisor,
            "unit": unit,
            "observation_date": end,
            "source": self.name,
            "frequency": self.frequency,
            "status": status.value,
            "license_note": f"XBRL tag '{tag}'. {self.license_note}",
        }

    @staticmethod
    def _period_label(end: str, fy) -> str:
        if fy:
            return f"FY{fy}"
        try:
            return f"FY{date.fromisoformat(end).year}"
        except ValueError:
            return "FY unknown"

    def fetch(self) -> pd.DataFrame:
        all_rows: list[dict] = []
        for company, cik in self.ciks.items():
            all_rows.extend(self._rows_for_company(company, cik))
        if not all_rows:
            return pd.DataFrame()
        df = pd.DataFrame(all_rows)
        df["observation_date"] = pd.to_datetime(df["observation_date"]).dt.date
        df["ingested_at"] = datetime.utcnow()
        return df
