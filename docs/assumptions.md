# Assumptions and reasonable defaults made for the Step 1 MVP

These are documented per the project instruction to "make reasonable assumptions and document them."

1. **Watchlist tickers** — the ten companies are tracked using their primary Oslo Børs (or NYSE where
   dual-listed) tickers, verified against public sources in July 2026. If a ticker fails to resolve,
   the company is shown with a "price data unavailable" badge rather than removed, so the watchlist
   stays complete even when one feed breaks. Two names in the original brief's watchlist are no
   longer publicly listed as of July 2026: **Golden Ocean** was acquired by CMB.TECH and delisted
   from Oslo Børs/Nasdaq in August 2025, and **Cool Company** was taken private via merger with EPS
   Ventures and delisted from NYSE/Euronext Oslo in January 2026. Both are kept on the watchlist per
   the project brief, but the app labels them "no longer publicly listed" instead of silently showing
   blank price data — this is itself a CFO-relevant consolidation data point, not a data error.
   Flex LNG's ticker is `FLNG` (its NYSE line, in USD) rather than `FLNG.OL`, matching Yahoo Finance's
   canonical listing for that stock.
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