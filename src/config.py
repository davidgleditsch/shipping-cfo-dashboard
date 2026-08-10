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

# Listed company watchlist, as specified in the project brief. Tickers verified against public
# sources in July 2026 (see docs/assumptions.md, item 1). Two names in the original brief's
# watchlist have since been delisted -- they are kept on the watchlist (per instructions) but
# flagged so the app never silently shows a blank chart for a stock that no longer trades.
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
    {"name": "Golden Ocean", "segment": "Dry bulk", "ticker": "GOGL.OL",
     "listed": False,
     "status_note": "Delisted from Oslo Bors/Nasdaq — acquired by CMB.TECH, completed August 2025. "
                     "Kept on the watchlist per project brief; shown as a completed consolidation, "
                     "not a live equity."},
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
