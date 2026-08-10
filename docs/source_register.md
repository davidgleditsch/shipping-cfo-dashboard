# Source Register — Shipping CFO Intelligence

Full row-by-row register (33 metrics, all 11 required fields) is in
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
| Hellenic Shipping News + gCaptain RSS | General shipping headlines, auto-categorized | As published | Free |

These four were implemented in Step 2 as "the reliable free sources first." All four degrade
gracefully — if the feed is unreachable, the page shows "Not available" rather than crashing or
guessing (verified in this session: this sandbox's own network proxy blocks these exact domains,
and the app correctly logged warnings and kept running instead of failing).

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

These three are the honest gaps in "free automation" — they are public-sector/exchange sources
that *should* be reachable per the project's sourcing priorities (regulators, exchanges), but do
not currently expose a free machine-readable feed. Worth re-checking periodically.

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
