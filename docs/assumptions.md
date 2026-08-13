# Assumptions and reasonable defaults made for the Step 1 MVP

These are documented per the project instruction to "make reasonable assumptions and document them."

1. **Watchlist tickers** — the eleven companies are tracked using their primary Oslo Børs (or NYSE
   where dual-listed) tickers, verified against public sources in July 2026 (August 2026 for the two
   names added that month). If a ticker fails to resolve, the company is shown with a "price data
   unavailable" badge rather than removed, so the watchlist stays complete even when one feed breaks.
   **Golden Ocean** was removed from the watchlist on 2026-08-13 (per explicit instruction) after
   being acquired by and delisted into **CMB.TECH** (merger completed 20 August 2025) and replaced on
   the list by CMB.TECH itself, ticker `CMBTO.OL` (its Euronext Oslo Børs line; CMB.TECH is
   triple-listed, also trading as `CMBT` on Euronext Brussels and NYSE). CMB.TECH's fleet is
   diversified beyond dry bulk, so its company financials reflect the whole group. **Cool Company**
   was removed from the watchlist outright on 2026-08-13 (also per explicit instruction) — unlike
   Golden Ocean, there was no successor entity to swap in for it (taken private via merger with EPS
   Ventures, completed January 2026, no listed continuation). **Frontline** (ticker `FRO.OL`, dual-
   listed NYSE/Oslo Børs both under `FRO`) and **Okeanis Eco Tankers** (ticker `OET.OL` on Oslo Børs,
   `ECO` on NYSE) were added the same day as two more listed crude tanker names; both are
   SEC-registered (CIKs 913290 and 1964954 respectively, confirmed from sec.gov filing URLs) and have
   been added to `SEC_EDGAR_CIKS`. Flex LNG's ticker is `FLNG` (its NYSE line, in USD) rather than
   `FLNG.OL`, matching Yahoo Finance's canonical listing for that stock.
2. **Currency** — share prices are shown in the currency Yahoo Finance reports (typically NOK for
   Oslo-listed names, USD for NYSE-listed names). No FX conversion is applied in the MVP; a `currency`
   column is stored alongside every price so a future version can normalize to USD or NOK.
3. **"Delayed" live data** — Yahoo Finance quotes are exchange-delayed (typically 15–20 minutes); the
   MVP labels all `yfinance` data as `delayed`, not `live`, to avoid overstating freshness.
4. **News categorization** — headlines from RSS feeds are auto-tagged into the required categories
   (freight markets, vessel transactions, newbuilding orders, charter contracts, refinancing, M&A/IPO,
   regulation, sanctions/geopolitics, company reporting) using keyword matching. This is a heuristic,
   not a guarantee — mis-tagged items can be manually recategorized in a future iteration. Uncategorized
   items are shown under "Other / needs review" rather than forced into the wrong bucket.
5. **Sample data** — used only to preview the Freight Markets chart layout when no manual CSV has been
   uploaded yet. It is clearly labeled, uses a dashed line style, and is excluded from any CFO Monitor
   signal or headline number. Removing the sample-data toggle at any time reverts the page to
   "Not available."
6. **NAV** — per explicit instruction, estimated NAV and Price/NAV are **not calculated**. The Listed
   Companies page shows these as placeholders labeled "Requires vessel-value assumptions (see
   docs/source_register.md)".
7. **Hi