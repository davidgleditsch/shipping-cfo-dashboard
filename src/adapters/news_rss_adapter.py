"""Free, public RSS adapter for shipping news headlines.

Only feeds that publishers make openly available without a paywall/login are used. Headlines and
links are stored; full article text is never scraped/reproduced.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

from src.adapters.base import SourceAdapter
from src.config import NEWS_CATEGORIES, NEWS_RSS_FEEDS
from src.data_model import DataStatus
from src.utils.logging_config import get_logger

log = get_logger("adapters.news_rss")

_KEYWORD_MAP = {
    "Freight markets": ["freight rate", "charter rate", "index", "baltic", "spot rate", "freight market"],
    "Vessel transactions": ["sale and purchase", "s&p", "vessel sale", "acquires vessel", "secondhand", "second-hand"],
    "Newbuilding orders": ["newbuilding", "new build", "orders vessel", "shipyard order", "places order"],
    "Charter contracts": ["charter contract", "time charter", "bareboat", "long-term charter", "fixture"],
    "Refinancing": ["refinanc", "bond issue", "credit facility", "bank facility", "sale and leaseback", "loan facility"],
    "M&A and IPOs": ["merger", "acquisition", "ipo", "initial public offering", "takeover", "combines with"],
    "Regulation": ["imo", "eu ets", "fueleu", "regulation", "emission", "carbon", "sulphur", "ballast water"],
    "Sanctions and geopolitics": ["sanction", "red sea", "houthi", "strait of hormuz", "geopolit", "war risk", "embargo"],
    "Company reporting": ["quarterly result", "q1 result", "q2 result", "q3 result", "q4 result", "earnings", "reports profit", "reports loss"],
}


def categorize(headline: str, summary: str) -> str:
    text = f"{headline} {summary}".lower()
    for category, keywords in _KEYWORD_MAP.items():
        if any(kw in text for kw in keywords):
            return category
    return "Other / needs review"


class NewsRSSAdapter(SourceAdapter):
    name = "Public RSS feeds"
    frequency = "as published"
    license_note = "Publisher RSS feeds; headline + link only, per publisher terms. No paywalled content."

    def __init__(self, feeds=None, max_items_per_feed: int = 30):
        self.feeds = feeds or NEWS_RSS_FEEDS
        self.max_items_per_feed = max_items_per_feed

    def fetch(self) -> pd.DataFrame:
        try:
            import feedparser
        except ImportError:
            log.error("feedparser not installed; skipping news fetch.")
            return pd.DataFrame()

        rows = []
        for feed_cfg in self.feeds:
            try:
                parsed = feedparser.parse(feed_cfg["url"])
            except Exception as exc:
                log.warning("RSS fetch failed for %s: %s", feed_cfg["source"], exc)
                continue
            if parsed.bozo and not parsed.entries:
                log.warning("RSS feed %s returned no parseable entries.", feed_cfg["source"])
                continue
            for entry in parsed.entries[: self.max_items_per_feed]:
                headline = getattr(entry, "title", "").strip()
                summary = getattr(entry, "summary", "").strip()
                link = getattr(entry, "link", "")
                published = getattr(entry, "published_parsed", None)
                if published:
                    pub_dt = datetime(*published[:6], tzinfo=timezone.utc)
                else:
                    pub_dt = datetime.now(timezone.utc)
                if not headline:
                    continue
                rows.append({
                    "published_date": pub_dt.replace(tzinfo=None),
                    "category": categorize(headline, summary),
                    "headline": headline,
                    "summary": summary[:500],
                    "source": feed_cfg["source"],
                    "url": link,
                    "status": DataStatus.LIVE.value,
                })
        if not rows:
            return pd.DataFrame()
        df = pd.DataFrame(rows)
        assert set(NEWS_CATEGORIES) >= set(df["category"].unique())
        return df
