# Shipping CFO Intelligence — Architecture Plan

## 1. Purpose

A single Streamlit application that gives a shipping-focused finance executive one place to monitor
freight markets, fleet fundamentals, listed peer companies, industry news and CFO-relevant risk
signals. The MVP favors correctness and transparency over completeness: every number on screen is
traceable to a source, an observation date and an update frequency, and any metric that cannot be
sourced legally and reliably is shown as "unavailable" rather than estimated or invented.

## 2. Design principles (from project brief, translated into engineering rules)

| Principle | Engineering consequence |
|---|---|
| Never fabricate/interpolate data | Adapters return `None`/empty rows instead of guessing. UI renders "Not available" state, never a chart with invented points. |
| Show source, date, frequency for every metric | Every stored observation carries `source`, `observation_date`, `frequency`, `status` columns. UI components always render a caption line with these. |
| Label live / delayed / manual / estimated / unavailable | `status` is a controlled enum (`DataStatus`) used everywhere, rendered as a colored badge. |
| Respect paywalls/licences | Adapters only call documented public APIs or free RSS feeds. No scraping of Clarksons, Baltic Exchange, Drewry, Xeneta, VesselsValue, Kpler, S&P Global, TradeWinds, Lloyd's List, etc. Those are manual-upload-only in the MVP. |
| Separate daily vs monthly/quarterly data | Two logical fact tables: `market_data_daily` and `fleet_fundamentals` (monthly/quarterly grain), plus `company_financials` (quarterly). |
| Preserve history | DuckDB is append-only per (entity, metric, date, source); nothing is overwritten, so charts can show trends. |
| App runs when sources are down | Every adapter call is wrapped in try/except with logging; pages render "source unavailable" panels instead of crashing. |
| Logging & graceful errors | Central `src/utils/logging_config.py`; all adapters and pages log to `logs/app.log` and stdout. |
| Executive-level design | Streamlit theming, card/metric layout, minimal chrome, no raw tables unless the user is looking at a manual-upload/QA page. |
| No exposed credentials | All keys read from environment variables via `src/config.py`; `.env` is gitignored; `.env.example` documents required vars; nothing is logged. |

## 3. Technology mapping

- **Frontend**: Streamlit multipage app (`app/Home.py` + `app/pages/*.py`).
- **Charts**: Plotly (`plotly.graph_objects` / `plotly.express`) for all time series and heatmaps.
- **Data transform**: Pandas (primary; the data volumes here do not need Polars, but the adapter
  interface returns plain DataFrames so the engine can be swapped later).
- **Storage**: DuckDB file at `data/duckdb/shipping.duckdb`. Chosen over SQLite because of native
  Parquet/CSV ingestion, fast analytical queries, and zero-server local deployment — a good fit for
  a single-user executive dashboard that may later move to scheduled batch refreshes.
- **Tests**: Pytest, covering the DB layer, adapters (with mocked network calls), CSV validation, and
  the pure-Python "page logic" functions (kept separate from Streamlit rendering so they are testable
  without a running Streamlit server).
- **Scheduling**: GitHub Actions workflow (`.github/workflows/scheduled_update.yml`) runs
  `scripts/update_data.py` on a cron schedule to refresh free/API-based sources and commit the
  updated DuckDB file (or push it to an artifact/storage target — see README).
- **Secrets**: GitHub Actions secrets → environment variables at runtime; never committed.

## 4. Modular source adapters

Every data source implements the `SourceAdapter` interface (`src/adapters/base.py`):

```
class SourceAdapter:
    name: str
    frequency: str          # e.g. "daily", "weekly", "monthly", "quarterly", "manual"
    license_note: str
    def fetch(self) -> pd.DataFrame: ...
    def status(self) -> DataStatus: ...
```

This lets a data provider (e.g. a free Yahoo Finance feed) be replaced later by a licensed provider
(e.g. Clarksons SIN, Baltic Exchange, VesselsValue) without touching page code — only a new adapter
class needs to be written and registered.

Implemented in the MVP:

1. `YFinanceMarketAdapter` — live daily share price / volume data for the listed watchlist via the
   `yfinance` library (free, unofficial Yahoo Finance wrapper; no key required).
2. `ManualCSVAdapter` — validates and ingests analyst-uploaded CSVs (freight rates, fleet
   fundamentals, orderbook, scrapping, company financials) against a documented schema, logging
   every upload for audit.
3. `NewsRSSAdapter` — free, public RSS feeds from shipping-news publishers that make headlines
   available without a paywall (e.g. Hellenic Shipping News, gCaptain). No paywalled scraping.
4. `SampleDataAdapter` — generates a small, clearly labeled ("SAMPLE DATA — ILLUSTRATIVE ONLY, NOT A
   MARKET OBSERVATION") illustrative series purely so first-run users see what a populated chart
   looks like. Sample rows are tagged `status="sample"` and are visually distinct (dashed line,
   warning banner) so they can never be mistaken for real data. They are excluded from the CFO
   Monitor's risk-signal logic.

## 5. Data flow

```
GitHub Actions (cron)  ─┐
Manual CSV upload       ─┼─► adapters/*.py ─► validation ─► DuckDB (append-only, historized) ─► pages_logic/*.py ─► Streamlit pages (app/pages/*.py) ─► Plotly charts + labeled metrics
yfinance / RSS (live)   ─┘
```

`pages_logic/*.py` contains pure functions (`get_executive_brief_data(conn) -> ExecutiveBriefData`)
that query DuckDB and return typed, tested Python objects. `app/pages/*.py` only renders those
objects — this keeps business logic unit-testable without spinning up Streamlit.

## 6. What Step 1 does and does not include

Included: full app structure, working live adapter (yfinance), manual CSV workflow with templates
and validation, RSS news adapter, DuckDB historized storage, all 6 pages, tests, CI scheduling
skeleton, README.

Not included (documented as gaps, see `docs/source_register.md`): licensed freight rate indices
(Baltic Exchange/Clarksons/Drewry), fleet/orderbook/scrapping databases (Clarksons/VesselsValue),
vessel valuations (VesselsValue/broker), detailed financials/consensus (S&P Capital IQ/Bloomberg),
and NAV calculation (explicitly withheld until vessel-value assumptions are sourced and documented,
per project instructions).
