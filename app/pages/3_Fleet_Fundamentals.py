"""Fleet Fundamentals -- trading fleet, orderbook, deliveries, scrapping, age profile by segment."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st

from src.config import FREIGHT_SEGMENTS
from src.db_session import get_conn
from src.pages_logic.fleet_fundamentals import get_segment_fundamentals
from src.utils.formatting import fmt_number, render_source_caption
from src.utils.sidebar import render_sidebar
from src.utils.uploads import render_csv_upload_widget

st.set_page_config(page_title="Fleet Fundamentals | Shipping CFO Intelligence", layout="wide", page_icon="🛠️")
render_sidebar()
conn = get_conn()

st.title("Fleet Fundamentals")
st.caption("Trading fleet, orderbook, deliveries, scrapping and age profile — monthly/quarterly grain, "
           "kept separate from daily rate data.")

st.markdown("#### Upload manual data")
upload_cols = st.columns(3)
with upload_cols[0]:
    st.write("**Fleet & age template**")
    render_csv_upload_widget(
        conn, dataset_key="fleet_fundamentals", target_table="fleet_fundamentals",
        template_name="fleet_fundamentals_template.csv", label="Upload fleet & age template",
        key_prefix="fleet",
    )
with upload_cols[1]:
    st.write("**Orderbook template**")
    render_csv_upload_widget(
        conn, dataset_key="orderbook", target_table="fleet_fundamentals",
        template_name="orderbook_template.csv", label="Upload orderbook template",
        key_prefix="orderbook",
    )
with upload_cols[2]:
    st.write("**Scrapping template**")
    render_csv_upload_widget(
        conn, dataset_key="scrapping", target_table="fleet_fundamentals",
        template_name="scrapping_template.csv", label="Upload scrapping template",
        key_prefix="scrapping",
    )

st.divider()

tabs = st.tabs(FREIGHT_SEGMENTS)
for tab, segment in zip(tabs, FREIGHT_SEGMENTS):
    with tab:
        view = get_segment_fundamentals(conn, segment)
        cols = st.columns(4)
        keys = list(view.metrics.items())
        for i, (metric_key, mv) in enumerate(keys):
            with cols[i % 4]:
                display_val = f"{fmt_number(mv.value)} {mv.unit or ''}" if mv.value is not None else "Not available"
                st.metric(mv.label, display_val)
                render_source_caption(mv.source_meta)
                st.markdown("&nbsp;")
