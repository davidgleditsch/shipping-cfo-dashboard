"""SEC EDGAR company filings adapter -- free, documented, authoritative regulator source.

Only used for watchlist companies that are confirmed SEC registrants (dual-listed on a US
exchange and therefore filing Forms 6-K / 20-F as foreign private issuers). Most of the Oslo
Bors-only names in the watchlist have no SEC registration and are correctly skipped -- this
adapter never fabricates a filing feed for a company that does not have one.

Endpoint: https://data.sec.gov/submissions/CIK##########.json
Docs: https://www.sec.gov/os/webmaster-faq#developers
SEC's fair-access policy requires a descriptive User-Agent header identifying the requester;
no API key is needed and there is no cost.
"""
from __future__ import annotations

import json
import urllib.request
from datetime import datetime, timedelta

import pandas as pd

from src.adapters.base import SourceAdapter
from src.data_model import DataStatus
from src.utils.logging_config import get_logger

log = get_logger("adapters.sec_edgar")

# Confirmed CIKs for watchlist companies with SEC registration (verified July 2026). Companies not
# listed here are Oslo Bors-only with no SEC filings to fetch -- intentionally excluded, not missed.
SEC_EDGAR_CIKS = {
    "Hafnia": "1815779",
    "BW LPG": "1649313",
    "Flex LNG": "1772253",
}

_BASE_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik:0>10}.json"


class SECEdgarFilingsAdapter(SourceAdapter):
    name = "SEC EDGAR"
    frequency = "as filed"
    license_note = "US SEC EDGAR full-text filing index; public domain, free, requires a descriptive User-Agent header."

    def __init__(self, ciks: dict[str, str] | None = None, lookback_days: int = 120,
                 contact_email: str = "contact@example.com", timeout: int = 10):
        self.ciks = ciks or SEC_EDGAR_CIKS
        self.lookback_days = lookback_days
        self.user_agent = f"Shipping CFO Intelligence {contact_email}"
        self.timeout = timeout

    def _fetch_one(self, company: str, cik: str) -> list[dict]:
        url = _BASE_SUBMISSIONS_URL.format(cik=cik)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": self.user_agent})
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except (OSError, ValueError) as exc:
            log.warning("SEC EDGAR fetch failed for %s (CIK %s): %s", company, cik, exc)
            return []

        recent = data.get("filings", {}).get("recent", {})
        forms = recent.get("form", [])
        dates = recent.get("filingDate", [])
        accessions = recent.get("accessionNumber", [])
        docs = recent.get("primaryDocument", [])

        cutoff = datetime.utcnow().date() - timedelta(days=self.lookback_days)
        rows = []
        for form, filing_date_str, accession, doc in zip(forms, dates, accessions, docs):
            if form not in ("6-K", "20-F", "20-F/A", "6-K/A"):
                continue
            try:
                filing_date = datetime.strptime(filing_date_str, "%Y-%m-%d").date()
            except ValueError:
                continue
            if filing_date < cutoff:
                continue
            accession_nodash = accession.replace("-", "")
            url_path = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession_nodash}/{doc}"
            rows.append({
                "published_date": datetime.combine(filing_date, datetime.min.time()),
                "category": "Company reporting",
                "headline": f"{company}: SEC Form {form} filed",
                "summary": f"{company} filed Form {form} with the SEC on {filing_date.isoformat()}.",
                "source": self.name,
                "url": url_path,
                "status": DataStatus.LIVE.value,
            })
        return rows

    def fetch(self) -> pd.DataFrame:
        all_rows: list[dict] = []
        for company, cik in self.ciks.items():
            all_rows.extend(self._fetch_one(company, cik))
        if not all_rows:
            return pd.DataFrame()
        return pd.DataFrame(all_rows)
