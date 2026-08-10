# Shipping CFO Intelligence

An executive dashboard for monitoring global shipping markets, listed shipping companies, fleet
fundamentals, freight rates, orderbooks, scrapping, capital-markets activity and industry news —
built for a finance executive (CFO) audience.

Read `docs/architecture.md`, `docs/source_register.md` and `docs/assumptions.md` first — they
explain the design decisions, what is live vs. manual vs. unavailable, and why. `docs/step2_audit_summary.md`
summarizes the Step 2 data-source audit (new adapters, tests, gaps, paid-subscription recommendation).

## What this is (and isn't)

This app never fabricates or interpolates shipping data. Every number shown is labeled **Live**,
**Delayed**, **Manually entered**, **Estimated**, **Sample (illustrative only)** or **Not available**,
with a source, observation date and frequency. Freight rate indices, fleet/orderbook/scrapping data
and vessel valuations from licensed providers (Clarksons, Baltic Exchange, Drewry, Xeneta,
VesselsValue, Kpler, S&P Global) are **not scraped** — they are supported through a validated manual
CSV upload workflow instead. See `docs/source_register.md` / `docs/source_register.csv` for the full
gap list, cost and reliability assessment per metric.

## Pages

1. **Executive Brief** — top developments, segment heatmap, rate movements, company announcements,
   CFO implications.
2. **Freight Markets** — dry bulk, container, crude tanker, product tanker, LNG, LPG, car carrier.
3. **Fleet Fundamentals** — trading fleet, orderbook, deliveries, scrapping, age profile per segment.
4. **Listed Companies** — Wallenius Wilhelmsen, Höegh Autoliners, MPC Container Ships, Hafnia,
   Odfjell, BW LPG, Golden Ocean, Flex LNG, Klaveness Combination Carriers, Cool Company.
5. **News and Events** — categorized shipping news from free public RSS feeds plus SEC filing alerts.
6. **CFO Monitor** — structured warning signals (refinancing maturity, liquidity pressure, high LTV,
   capex commitments, contract coverage, interest expense, dividend sustainability, covenant risk,
   equity issuance risk, consolidation/M&A potential).

## Live/free data sources implemented

- **Yahoo Finance** (`yfinance`) — daily, ~15-20 min delayed share prices for the watchlist.
- **Frankfurter (ECB reference rates)** — USD/NOK, USD/EUR FX, free, no key.
- **SEC EDGAR** — Form 6-K/20-F filing alerts for the three SEC-registered watchlist names (Hafnia,
  BW LPG, Flex LNG), free, no key (requires a descriptive User-Agent header per SEC's fair-access
  policy).
- **Public RSS** (Hellenic Shipping News, gCaptain) — general shipping headlines, auto-categorized.

Everything else (freight rate indices, fleet/orderbook/scrapping data, detailed company financials,
vessel valuations, Oslo Børs-only company announcements) has no free, legal, machine-readable source
and is manual-CSV-only by design — see `docs/source_register.md` for why, and what it would cost to
automate.

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                # edit if you have licensed-source API keys later
streamlit run app/Home.py
```

The app creates `data/duckdb/shipping.duckdb` on first run. Click **Refresh live data now** in the
sidebar to pull share prices, FX rates, SEC filing alerts and RSS news in one go.

## Uploading manual data

Each of Freight Markets, Fleet Fundamentals and Listed Companies has an upload panel. Templates are
in `data/templates/`:

- `freight_rates_template.csv`
- `fleet_fundamentals_template.csv`
- `orderbook_template.csv`
- `scrapping_template.csv`
- `company_financials_template.csv`

Fill these in from a source you already have access to (Clarksons, Baltic Exchange, a broker report,
company filings, etc.) and upload through the app. Every upload is validated before it touches the
database: required columns, numeric values, parseable dates, recognized segment names, **no
duplicate rows within the file**, **expected unit per metric** (warns on mismatch — e.g. fleet counts
should be "vessels," not "ships"), and **an outlier check** against the most recent existing
observation for the same metric (warns if a new value has moved more than 75% versus history — a
common data-entry-typo catcher). You then see a preview of exactly what will be ingested and must
click **Confirm and ingest** — nothing is written silently. Every upload (successful or rejected) is
logged in the `manual_upload_log` table for audit.

## Running tests

```bash
pip install -r requirements.txt
pytest tests/ -v
```

35 tests cover the DB layer (append-only history, dedup), the manual-CSV validator (including the
Step 2 duplicate/unit/outlier/row-limit checks), the FX and SEC EDGAR adapters (mocked network,
including failure paths), adapter categorization/sample-data tagging, and all page logic (freight
views, fleet fundamentals, listed companies, CFO Monitor signals, news category counts).

**Note on a local dev quirk**: if you edit `.py` files while a Python process has already imported
them, stale `__pycache__/*.pyc` bytecode can occasionally be reused. If you see an error that doesn't
match your latest edit, delete the `__pycache__` directories under `src/` and `tests/` and re-run.

## Scheduled data updates

`scripts/update_data.py` now refreshes all four free/live sources in one run: Yahoo Finance share
prices, Frankfurter FX rates, SEC EDGAR filing alerts and public RSS news. It never raises — a
source that is temporarily unreachable is logged and reported as "0 rows," not treated as fatal.
Manual sources are, by design, only refreshed by a human uploading a new CSV.

`scripts/generate_static_dashboard.py [output.html]` renders a self-contained static HTML version of
every page's key figures, using the same `pages_logic` functions as the interactive Streamlit app (no
`streamlit`/`plotly` dependency, so it's cheap to run anywhere). This is what produces David's daily
HTML dashboard.

Two ways to run these on a schedule:

- **Cowork scheduled task (current setup)** — a daily task ("shipping-cfo-daily-brief," weekdays at
  07:07 local time) runs `update_data.py` then `generate_static_dashboard.py` and posts the resulting
  HTML dashboard plus a written text brief straight into chat each morning. No hosting, GitHub account
  or domain required. Its data refresh depends on whatever outbound network access that execution
  environment has; if a source is blocked there, the brief will say so plainly rather than guessing.
- **GitHub Actions (optional, if you later want a hosted/always-on version)** —
  `.github/workflows/scheduled_update.yml` runs `update_data.py` on a weekday cron schedule and commits
  the updated DuckDB file back to the repo. If you'd rather not version a binary DuckDB file in git
  history, swap the final "commit" step for an `actions/upload-artifact` step or a push to external
  storage (S3/GCS) — see the comment in the workflow file. Add any future licensed-source API keys as
  GitHub Actions repository secrets and reference them as environment variables in the workflow —
  never commit them.

## Deployment

Any host that can run a long-lived Streamlit process works (Streamlit Community Cloud, a small VM,
an internal container platform). Set environment variables from `.env.example` in the host's secret
manager. The DuckDB file is a single portable file — back it up like any other database file.

## Environment variables

See `.env.example`. `SHIPPING_DB_PATH` and `LOG_LEVEL` are used today. The licensed-source keys
(`CLARKSONS_API_KEY`, `VESSELSVALUE_API_KEY`, `XENETA_API_KEY`, `SP_GLOBAL_API_KEY`) are placeholders
for adapters to be built once those subscriptions exist (see `docs/source_register.md`).

## What still requires a paid or manual source

- All freight rate/index series (BDI/BCI/BPI/BSI, SCFI/WCI, WS crude/product, LNG/LPG spot, PCTC) —
  Baltic Exchange / Clarksons / Drewry / Xeneta license required. Manual CSV upload only.
- Trading fleet size, orderbook, expected deliveries, scrapping, average fleet age, %fleet 20yrs+ for
  every segment — Clarksons / VesselsValue license required. Manual CSV upload only.
- Company revenue, EBITDA, net debt, cash, dividend, fleet size, contract coverage, spot exposure —
  public in filings but not automated. Manual CSV upload from the filing (dividend filing *events*
  are auto-alerted for the 3 SEC-registered names via SEC EDGAR).
- Company announcements for the 7 Oslo Børs-only names — no confirmed free machine-readable feed
  from Euronext Newsweb; manual/curated. (SEC EDGAR covers the 3 SEC-registered names automatically.)
- Vessel valuations and therefore **estimated NAV / Price-to-NAV** — explicitly not calculated until
  vessel-value assumptions are sourced and documented (VesselsValue or broker valuations).
- IMO and OFAC regulatory/sanctions feeds — investigated; no working free RSS/API found (OFAC retired
  its RSS in Jan 2025). Manual/curated.
- Several CFO Monitor signals (refinancing maturity, high LTV, capex commitments, interest-expense
  trend, covenant risk, equity issuance risk) require debt/covenant/capex data not yet in the manual
  financials template — shown as "Not available" with the reason, not guessed.

Full detail, preferred/backup source, cost and reliability notes for every metric are in
`docs/source_register.md` and `docs/source_register.csv`.
