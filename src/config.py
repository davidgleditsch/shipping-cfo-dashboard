"""Central configuration. All secrets/config come from environment variables -- never hardcoded."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()  # no-op if .env is absent; safe for CI where real env vars are injected instead

PROJECT_ROOT = Path(__file__).resolve().parent.parent

DB_PATH = Path(os.environ.get("SHIPPING_DB_PATH", PROJECT_ROOT / "data" / "duckdb" / "shipping.duckdb"))
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
LOG_DIR = PROJECT_ROOT / "logs"

TEMPLATES_DIR = PROJECT_ROOT / "data" / "templates"
SAMPLE_DIR = PROJECT_ROOT / "data" / "sample"

# Optional keys for future licensed adapters (Step 2+). Blank means "not configured" -- adapters
# using these must degrade gracefully to DataStatus.UNAVAILABLE, never raise on import.
CLARKSONS_API_KEY = os.environ.get("CLARKSONS_API_KEY", "")
VESSELSVALUE_API_KEY = os.environ.get("VESSELSVALUE_API_KEY", "")
XENETA_API_KEY = os.environ.get("XENETA_API_KEY", "")
SP_GLOBAL_API_KEY = os.environ.get("SP_GLOBAL_API_KEY", "")

# Free-tier keys for the macro/context adapters added August 2026 (chokepoint traffic, reference
# rates, benchmark crude prices). Both require a no-cost registration; blank means "not configured"
# and the adapter degrades to DataStatus.UNAVAILABLE rather than raising.
FRED_API_KEY = os.environ.get("FRED_API_KEY", "")
EIA_API_KEY = os.environ.get("EIA_API_KEY", "")

# Listed company watchlist, as specified in the project brief. Tickers verified against public
# sources in July 2026 (see docs/assumptions.md, item 1). One name in the original brief's
# watchlist has since been delisted and is replaced here by its acquirer per instructions received
# 2026-08-13; one other remains delisted and kept on the list -- both flagged so the app never
# silently shows a blank chart for a stock that no longer trades under its original name.
WATCHLIST = [
    {"name": "Wallenius Wilhelmsen", "segment": "Car carrier", "ticker": "WAWI.OL",
     "listed": True, "status_note": ""},
    {"name": "Hoegh Autoliners", "segment": "Car carrier", "ticker": "HAUTO.OL",
     "listed": True, "status_note": ""},
    {"name": "MPC Container Ships", "segment": "Container", "ticker": "MPCC.OL",
     "listed": True, "status_note": ""},
    {"name": "Hafnia", "segment": "Product tanker", "ticker": "HAFNI.OL",
     "listed": True, "status_note": ""},
    {"name": "Odfjell", "segment": "Chemical/product tanker", "ticker": "ODF.OL",
     "listed": True, "status_note": ""},
    {"name": "BW LPG", "segment": "LPG", "ticker": "BWLPG.OL",
     "listed": True, "status_note": ""},
    {"name": "CMB.TECH", "segment": "Dry bulk (diversified)", "ticker": "CMBTO.OL",
     "listed": True,
     "status_note": "Replaces Golden Ocean on the watchlist (removed 2026-08-13): CMB.TECH acquired "
                     "Golden Ocean and delisted it from Oslo Bors/Nasdaq, merger completed 20 August "
                     "2025. CMB.TECH is triple-listed -- Euronext Brussels and NYSE under 'CMBT', "
                     "Euronext Oslo Bors under 'CMBTO' (ticker used here, for NOK-basis consistency "
                     "with the rest of the Oslo-listed names). Fleet is diversified beyond dry bulk "
                     "(crude/chemical tankers, container, offshore wind, port vessels) -- segment "
                     "financials on the Listed Companies page reflect the whole group, not a pure "
                     "dry-bulk play. Not yet added to SEC_EDGAR_CIKS (src/adapters/sec_edgar_adapter.py): "
                     "CIK not yet confirmed from a primary source -- documented gap, see "
                     "docs/source_register.md."},
    {"name": "Flex LNG", "segment": "LNG", "ticker": "FLNG",
     "listed": True, "status_note": "Dual-listed NYSE/Oslo Bors; ticker here is the NYSE line (USD)."},
    {"name": "Klaveness Combination Carriers", "segment": "Dry bulk / combination carrier", "ticker": "KCC.OL",
     "listed": True, "status_note": ""},
    {"name": "Cool Company", "segment": "LNG", "ticker": "CLCO.OL",
     "listed": False,
     "status_note": "Delisted from NYSE/Euronext Oslo — taken private via merger with EPS Ventures, "
                     "completed January 2026. Kept on the watchlist per project brief; shown as a "
                     "completed consolidation, not a live equity."},
]

# Maritime chokepoints tracked via IMF PortWatch (src/adapters/imf_portwatch_adapter.py). Names
# must match (by case-insensitive substring) the "name"-like field IMF PortWatch returns for its
# Daily_Chokepoints_Data layer -- kept as a short list here (rather than hardcoded in the adapter)
# so it can be extended without touching adapter logic.
CHOKEPOINTS = [
    "Suez Canal",
    "Panama Canal",
    "Strait of Hormuz",
    "Bab al-Mandab",
    "Bosphorus Strait",
    "Strait of Malacca",
    "Strait of Gibraltar",
    "Strait of Dover",
]

FREIGHT_SEGMENTS = [
    "Dry bulk",
    "Container",
    "Crude tanker",
    "Product tanker",
    "LNG",
    "LPG",
    "Car carrier",
]

NEWS_CATEGORIES = [
    "Freight markets",
    "Vessel transactions",
    "Newbuilding orders",
    "Charter contracts",
    "Refinancing",
    "M&A and IPOs",
    "Regulation",
    "Sanctions and geopolitics",
    "Company reporting",
    "Other / needs review",
]

# Free, public RSS feeds only -- no paywalled scraping.
NEWS_RSS_FEEDS = [
    {"source": "Hellenic Shipping News", "url": "https://www.hellenicshippingnews.com/feed/"},
    {"source": "gCaptain", "url": "https://gcaptain.com/feed/"},
]
