# Source Register — Shipping CFO Intelligence

Full row-by-row register (39 metrics, all 11 required fields) is in
[`docs/source_register.csv`](source_register.csv) — open it in Excel/Sheets to filter and sort.
This document summarizes what it says and explains the reasoning behind each status.

Status legend: **Implemented (Live)** = fetched automatically from a free API/RSS at runtime and
verified working. **Manual CSV** = analyst uploads a validated template. **Manual/curated** = no
machine-readable feed exists yet; a human reads a public webpage. **Unavailable** = blocked on a
paid input that has not been purchased.

## What updates automatically today, at no cost

| Source | What it provides | Frequency | Cost |
|---|---|---|---|
| Yahoo Finance (`yfinance`) | Share price, volume for all 10 watchlist tickers | Daily, 15-20 min delayed | Free |
| Frankfurter (ECB reference rates) | USD/NOK, USD/EUR FX rates | Daily | Free |
| SEC EDGAR | Filing alerts (6-K/20-F) for Hafnia, BW LPG, Flex LNG — the three SEC-registered names | As filed | Free |
| SEC EDGAR XBRL company facts | Revenue and cash (annual, from 20-F), plus a *derived* net debt when both tags exist, for Hafnia, BW LPG, Flex LNG | Annual (20-F only — FPI 6-Ks aren't reliably XBRL-tagged) | Free |
| Hellenic Shipping News + gCaptain RSS | General shipping headlines, auto-categorized | As published | Free |
| IMF PortWatch (`Daily_Chokepoints_Data` ArcGIS FeatureServer) | Daily vessel-transit counts for 8 tracked chokepoints (Hormuz, Suez, Panama, Bab al-Mandab, Bosphorus, Malacca, Gibraltar, Dover) | Weekly (published Tuesdays; AIS-derived) | Free, no key |
| FRED (Federal Reserve Bank of St. Louis) | SOFR reference rate — context for watchlist companies' cost of debt | Daily | Free, requires a no-cost registered key (`FRED_API_KEY`) |
| EIA (U.S. Energy Information Administration) | Brent and WTI crude spot prices — demand-side context for tanker segments | Daily | Free, requires a no-cost registered key (`EIA_API_KEY`) |

The last three were added August 2026 in response to a request for additional free, "fun but
relevant" context data alongside the core Shipping CFO metrics. Field names for the IMF PortWatch
ArcGIS layer could not be verified against a live response while writing the adapter (this sandbox
has no route to `arcgis.com`); `src/adapters/imf_portwatch_adapter.py` is deliberately
schema-tolerant (tries several plausible field names, logs a warning and returns no data rather
than guessing) and should be checked against its first real GitHub Actions run. FRED and EIA both
require a free registered API key — set `FRED_API_KEY` / `EIA_API_KEY` as GitHub Actions secrets;
until then both degrade to "Not available" exactly like every other missing source.

The first three were implemented in Step 2 as "the reliable free sources first." The SEC XBRL
company-facts adapter (`src/adapters/sec_edgar_xbrl_adapter.py`) was added afterward to close part
of the company-financials gap: the original SEC EDGAR adapter only flagged *that* a filing
happened (a news item), never the numbers inside it. All of these degrade gracefully — if the feed
is unreachable, the page shows "Not available" rather than crashing or guessing (verified in this
session: this sandbox's own network proxy blocks these exact domains, and the app correctly logged
warnings and kept running instead of failing).

The XBRL adapter deliberately does **not** attempt EBITDA, fleet size, contract coverage % or spot
exposure % — none of these has a standard tag a foreign private issuer is required to use, and
guessing which reported number is "EBITDA" from free text would be exactly the kind of
interpolation the project rules forbid. It also only extracts **annual** figures (from the 20-F);
quarterly numbers (the 6-K press releases) remain a manual-CSV gap because FPI 6-Ks are not
reliably XBRL-tagged. See `tests/test_sec_edgar_xbrl_adapter.py` for the concept-matching and
graceful-degradation behaviour, including the explicit test that a 6-K-form fact is excluded even
if one happened to be tagged.

## What still requires a paid source or manual input, and which one

Every freight-rate index (dry bulk, container, crude tanker, product tanker, LNG, LPG, car
carrier) and every fleet-fundamentals metric (trading fleet, orderbook, deliveries, scrapping,
average age, %20yrs+) sits behind a licensed data provider. No free, legal, machine-readable
equivalent exists for any of these — Baltic Exchange, Drewry and Xeneta indices, and Clarksons'
World Fleet Register/orderbook/demolition data, are all subscription products, and scraping them
would violate their terms of use, which this project will not do. Consolidated by provider:

- **Clarksons** (Shipping Intelligence Network + World Fleet Register) would resolve: trading
  fleet, orderbook, orderbook %, expected deliveries, scrapping, average age, %20yrs+ for *all
  seven* segments, plus most freight rate series. This is the single broadest gap-closer — see the
  recommendation below.
- **Baltic Exchange** membership would resolve: dry bulk, crude tanker, product tanker and LPG
  daily rate indices specifically (the benchmark indices themselves, as opposed to Clarksons'
  broader commentary/estimates around them).
- **Drewry** or **Xeneta** would resolve: container freight rates (WCI/SCFI-equivalent) with more
  granularity than Freightos' free headline numbers.
- **VesselsValue** would resolve: vessel valuations, which is the one input still blocking
  **estimated NAV / Price-to-NAV** — per project policy this is not calculated until that input is
  documented and sourced.
- **S&P Global (Capital IQ)** would resolve: automated ingestion of company revenue, EBITDA, net
  debt, cash, fleet size, contract coverage and spot exposure, replacing manual CSV entry from
  filings.
- **Manual input** remains the only route, even with unlimited budget, for: Oslo Børs-only company
  announcements (no confirmed free bulk feed — see below), debt maturity/covenant/capex data behind
  the CFO Monitor's unresolved signals, and broker-level qualitative colour.

## Investigated but not implemented (documented, not silently dropped)

- **Euronext Oslo Børs Newsweb** (company announcements for the 7 Oslo Børs-only names): the
  public site (newsweb.oslobors.no) is free to browse, but it is a JavaScript application with no
  confirmed free RSS/JSON feed as of July 2026; Euronext's documented API/data products for
  regulated announcements are paid. Kept as manual/curated rather than building a scraper against
  an undocumented endpoint.
- **IMO regulatory RSS**: IMO publishes an RSS feeds page (imo.org/en/about/pages/rss.aspx) but no
  working press-briefing feed could be confirmed by direct fetch in this session. Kept manual.
- **OFAC sanctions RSS**: officially retired by the US Treasury on 31 January 2025. OFAC now
  offers only email notifications or the plain recent-actions webpage; no RSS/API replacement has
  been published. Kept manual rather than scraping the webpage.
- **EU ETS carbon allowance (EUA) daily price** (investigated August 2026): the daily/spot price is
  exchange-derived (ICE futures, EEX auctions). Investing.com and Trading Economics both display a
  free headline number on their websites, but neither offers a genuinely free, no-key, documented
  API for it — Trading Economics' API is a paid product, and building a scraper against either
  site's web page would violate this project's own no-scraping rule. Databento offers real ICE EUA
  futures data via API, but it is a paid feed. The EEA's EU ETS data viewer/EUTL downloads cover
  emissions and allocations, not the daily traded price. Kept as a documented, explicitly-labeled
  "Not available" gap on the new Macro & Chokepoints page (`src/pages_logic/macro_context.py`)
  rather than silently dropped — see the Recommendation section below, which now also covers this.

These four are the honest gaps in "free automation" — they are public-sector/exchange/benchmark
sources that *should* be reachable per the project's sourcing priorities, but do not currently
expose a free machine-readable feed. Worth re-checking periodically.

## Recommendation: single most valuable paid subscription

**Clarksons** (Shipping Intelligence Network + World Fleet Register bundle).

Reasoning: of the 33 metrics in the register, 14 are blocked purely on a licensed shipping-market
data provider (7 freight rate series + 7 fleet-fundamentals metrics), and Clarksons is the only one
of the six named providers (Clarksons, Baltic Exchange, Drewry, Xeneta, VesselsValue, Kpler) that
covers *all seven segments* for *both* freight rates and fleet/orderbook/scrapping/age data in one
subscription. Baltic Exchange, Drewry and Xeneta each cover a narrower rate-only slice; VesselsValue
covers valuations only (useful, but a smaller, more specific gap); Kpler is stronger on cargo-flow
and trade-tracking than on the fleet/orderbook/rate fundamentals this dashboard is built around.
A single Clarksons subscription would move roughly 14 of the 15 currently-manual, non-financial
metrics from "Manual CSV" to "Implemented," leaving VesselsValue (for NAV) as the next-highest-value
addition once Clarksons is in place.

Note: the EUA carbon-price gap added above is unrelated to this recommendation — Clarksons does not
cover exchange-traded carbon prices — and does not change it. Given it is one metric with low
incremental CFO value versus the freight/fleet gaps, a monthly manual entry (from the free headline
number on Trading Economics or Investing.com) is a proportionate interim fix; a paid feed (Trading
Economics API, or Databento for ICE EUA futures) is only worth it if carbon-cost exposure becomes a
standing agenda item.
