"""Macro & Chokepoints -- added August 2026.

Context data that sits outside the seven freight segments and ten listed companies: maritime
chokepoint traffic (IMF PortWatch) and macro benchmark rates (FRED, EIA). All free, all automated
where a working source was confirmed; the one confirmed gap (EU ETS carbon price) is shown as an
explicit "Not available" card rather than omitted.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import plotly.express as px
import streamlit as st

from src.config import CHOKEPOINTS
from src.db_session import get_conn
from src.pages_logic.macro_context import get_chokepoint_views, get_macro_indicator_views
from src.utils.formatting import fmt_number, fmt_pct, render_source_caption
from src.utils.sidebar import render_sidebar

st.set_page_config(page_title="Macro & Chokepoints | Shipping CFO Intelligence", layout="wide", page_icon="🌍")
render_sidebar()
conn = get_conn()

st.title("Macro & Chokepoints")
st.caption("Maritime chokepoint traffic (IMF PortWatch) and macro benchmark rates (FRED, EIA) — "
           "context for the freight and company pages, not a substitute for them.")

st.subheader("Chokepoint traffic")
st.caption("Daily vessel-transit estimates for the eight major maritime chokepoints, from AIS data "
           "published weekly by IMF PortWatch.")
choke_views = get_chokepoint_views(conn)
if not choke_views:
    st.info("Not available yet. No chokepoint data has been ingested — click **Refresh live data "
            "now** in the sidebar, or wait for the next scheduled GitHub Actions run.")
else:
    chart_rows = [
        {"Chokepoint": label.replace(" — daily vessel transits", ""), "Vessels/day": v.latest_value}
        for label, v in choke_views.items() if v.latest_value is not None
    ]
    if chart_rows:
        fig = px.bar(chart_rows, x="Chokepoint", y="Vessels/day",
                     title="Latest daily vessel transits by chokepoint")
        st.plotly_chart(fig, width="stretch")
    cols = st.columns(4)
    for i, (label, v) in enumerate(choke_views.items()):
        with cols[i % 4]:
            short_label = label.replace(" — daily vessel transits", "")
            st.metric(short_label, f"{fmt_number(v.latest_value, 0)} {v.latest_unit or ''}",
                      delta=fmt_pct(v.wow_change_pct))
            render_source_caption(v.source_meta)
missing_chokepoints = set(CHOKEPOINTS) - {label.replace(" — daily vessel transits", "") for label in choke_views}
if missing_chokepoints:
    st.caption(f"Not yet available: {', '.join(sorted(missing_chokepoints))}.")

st.divider()

st.subheader("Macro benchmark rates")
st.caption("Reference points for interest expense (SOFR) and tanker-demand context (Brent/WTI) — "
           "not a substitute for a company's own disclosed cost of debt or realized freight rates.")
macro_views = get_macro_indicator_views(conn)
cols = st.columns(3)
for i, (label, v) in enumerate(macro_views.items()):
    with cols[i % 3]:
        if v.latest_value is None:
            st.metric(label, "Not available")
        else:
            st.metric(label, f"{fmt_number(v.latest_value)} {v.latest_unit or ''}",
                      delta=fmt_pct(v.wow_change_pct))
        render_source_caption(v.source_meta)

st.divider()
st.caption(
    "Chokepoint data: IMF PortWatch, free, no key. SOFR: FRED (Federal Reserve Bank of St. Louis), "
    "free, requires a no-cost registered API key (FRED_API_KEY). Brent/WTI: EIA, free, requires a "
    "no-cost registered API key (EIA_API_KEY). Set both keys as environment variables / GitHub "
    "Actions secrets for these two to populate — see .env.example. Full detail in "
    "docs/source_register.md."
)
