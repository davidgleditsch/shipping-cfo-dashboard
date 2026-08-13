"""Shared sidebar rendered on every page: refresh controls + global disclaimer."""
from __future__ import annotations

import streamlit as st

from src.db_session import (
    refresh_fx,
    refresh_macro_context,
    refresh_market_data,
    refresh_news,
    refresh_sec_filings,
)


def render_sidebar() -> None:
    with st.sidebar:
        st.markdown("### Shipping CFO Intelligence")
        st.caption("Executive dashboard — MVP")
        if st.button("Refresh live data now", width="stretch"):
            with st.spinner("Refreshing market data, FX, filings, news and macro context..."):
                n1, err1 = refresh_market_data()
                n2, err2 = refresh_news()
                n3, err3 = refresh_fx()
                n4, err4 = refresh_sec_filings()
                n5, err5 = refresh_macro_context()
            st.success(f"Inserted {n1} market rows, {n2} news rows, {n3} FX rows, {n4} filing items, "
                       f"{n5} macro/chokepoint rows.")
            for e in err1 + err2 + err3 + err4 + err5:
                st.warning(e)
        st.divider()
        st.caption(
            "All figures are labeled Live, Delayed, Manually entered, Estimated, Sample or Not "
            "available. No shipping data is fabricated or interpolated. See the Source Register "
            "in the project README for full provenance."
        )
