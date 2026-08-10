"""Entry point for scheduled data refresh of automated (free/live) sources only.

Manual sources (freight rates, fleet fundamentals, orderbook, scrapping, company financials) are
not touched here -- they are refreshed by an analyst uploading a CSV through the app. This script
is deliberately lightweight: it only needs duckdb, pandas, python-dotenv, feedparser and yfinance --
not streamlit/plotly -- so it can run in a minimal environment (GitHub Actions, a scheduled task
sandbox, cron on a small VM) without installing the full app's dependency set.

Prints a one-line summary per source so a human (or an LLM reading the log in a scheduled task)
can immediately tell whether a source succeeded or degraded gracefully.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.adapters.fx_adapter import FXRateAdapter
from src.adapters.news_rss_adapter import NewsRSSAdapter
from src.adapters.sec_edgar_adapter import SECEdgarFilingsAdapter
from src.adapters.yfinance_adapter import YFinanceMarketAdapter
from src.db import get_connection, upsert_dataframe
from src.utils.logging_config import get_logger

log = get_logger("scripts.update_data")


def _run(label: str, table: str, adapter_fetch, conn) -> int:
    log.info("Refreshing %s...", label)
    try:
        df = adapter_fetch()
    except Exception as exc:
        log.error("%s: adapter raised an exception (should not happen -- adapters must catch "
                   "their own errors): %s", label, exc)
        print(f"{label}: FAILED ({exc})")
        return 0
    if df.empty:
        log.warning("%s returned no data (source unavailable or blocked from this network).", label)
        print(f"{label}: 0 rows (source unavailable or blocked)")
        return 0
    n = upsert_dataframe(conn, table, df)
    print(f"{label}: {n} new row(s)")
    return n


def main() -> int:
    conn = get_connection()
    total_inserted = 0

    total_inserted += _run("Yahoo Finance (share prices)", "company_market_data",
                            YFinanceMarketAdapter().fetch, conn)
    total_inserted += _run("Frankfurter (FX rates)", "market_data_daily",
                            FXRateAdapter().fetch, conn)
    total_inserted += _run("SEC EDGAR (filing alerts)", "news_events",
                            SECEdgarFilingsAdapter().fetch, conn)
    total_inserted += _run("Public RSS (shipping news)", "news_events",
                            NewsRSSAdapter().fetch, conn)

    log.info("Scheduled update complete. Total new rows: %d", total_inserted)
    print(f"TOTAL new rows across all free sources: {total_inserted}")
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
