# Step 2 — Data-Source Architecture Audit: Summary

This is the executive summary of the Step 2 deliverables. Full detail lives in
`docs/source_register.md` and `docs/source_register.csv`.

## 1. Updated source register

`docs/source_register.csv` — 33 metrics x 11 fields (metric, segment, preferred source, backup
source, access method, update frequency, publication lag, licence/terms limitations, reliability
assessment, expected cost, implementation status). `docs/source_register.md` is the narrative
companion: what's automated free today, what needs which paid provider, and what was investigated
but couldn't be automated for free.

## 2. Implemented source adapters (Step 2 additions)

All four are free, require no API key beyond a descriptive User-Agent (SEC), and degrade
gracefully (log a warning, return an empty result) if the network/provider is unavailable:

- `src/adapters/fx_adapter.py` — `FXRateAdapter`: USD/NOK and USD/EUR reference rates from
  Frankfurter (ECB), stored in `market_data_daily` with `segment="FX"`. Surfaced on the Listed
  Companies page as context for comparing NOK- and USD-priced names.
- `src/adapters/sec_edgar_adapter.py` — `SECEdgarFilingsAdapter`: recent Form 6-K/20-F filing
  alerts from SEC EDGAR for the three watchlist companies confirmed as SEC registrants (Hafnia,
  BW LPG, Flex LNG). Feeds into `news_events` under "Company reporting."
- `src/adapters/manual_csv_adapter.py` — strengthened: in-file duplicate detection, a per-metric
  expected-unit dictionary (warns on mismatch), an outlier/jump check against the most recent
  existing database observation for the same key, and a 5,000-row upload ceiling.
- `src/utils/uploads.py` — new shared upload widget used by Freight Markets, Fleet Fundamentals
  (x3) and Listed Companies: validate -> show a preview table and all warnings -> require an
  explicit "Confirm and ingest" click. Nothing is written to the database until the analyst has
  seen the preview.

The existing Yahoo Finance and public-RSS-news adapters from Step 1 are unchanged and remain the
other two "free, live" sources.

## 3. Tests

11 new tests added (35 total, all passing): `tests/test_fx_adapter.py` (3),
`tests/test_sec_edgar_adapter.py` (3, including CIK-not-configured and network-failure paths), and
5 new cases appended to `tests/test_manual_csv_adapter.py` covering in-file duplicates, the row-count
ceiling, unit-mismatch warnings, and the outlier check both with and without a database connection.

## 4. Unresolved source gaps

- All seven freight-rate indices (dry bulk, container, crude tanker, product tanker, LNG, LPG, car
  carrier) — behind Baltic Exchange / Clarksons / Drewry / Xeneta.
- All seven fleet-fundamentals metrics across all seven segments (trading fleet, orderbook,
  orderbook %, deliveries, scrapping, average age, %20yrs+) — behind Clarksons / VesselsValue.
- Vessel valuations, and therefore estimated NAV / Price-to-NAV — behind VesselsValue or broker
  valuations; NAV remains uncalculated by explicit project policy until this is sourced.
- Company announcements for the seven Oslo Børs-only watchlist names (no SEC filings) — Euronext
  Newsweb has no confirmed free machine-readable feed; bulk/API access is a paid Euronext product.
- IMO regulatory updates and OFAC sanctions actions — both investigated; IMO's RSS page did not
  yield a working feed on direct fetch, and OFAC retired its RSS feed in January 2025 with no
  replacement. Both remain manual/curated.
- Structured revenue/EBITDA/net debt/cash/dividend/fleet-size/contract-coverage/spot-exposure data
  — currently manual entry from public filings; S&P Capital IQ (or similar) would automate this.
- CFO Monitor inputs for refinancing maturity, LTV, capex commitments, interest-expense trend and
  covenant terms — not in the manual template yet; requires structured extraction from bond
  prospectuses/credit agreements, which are public but unstructured.

## 5. Recommendation: single most valuable paid subscription

**Clarksons** (Shipping Intelligence Network + World Fleet Register). It is the only one of the six
named providers that covers freight rates *and* fleet/orderbook/scrapping/age data across all seven
segments in one subscription, resolving 14 of the register's 33 metrics directly. See the full
reasoning in `docs/source_register.md`.
