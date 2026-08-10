"""Freight Markets -- rates/indices by segment."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import pandas as pd
import plotly.express as px
import streamlit as st

from src.adapters.sample_data_adapter import generate_sample_freight_series
from src.config import FREIGHT_SEGMENTS
from src.db_session import get_conn
from src.pages_logic.freight_markets import get_segment_rate_view
from src.utils.formatting import fmt_number, fmt_pct, render_source_caption
from src.utils.sidebar import render_sidebar
from src.utils.uploads import render_csv_upload_widget

st.set_page_config(page_title="Freight Markets | Shipping CFO Intelligence", layout="wide", page_icon="📈")
render_sidebar()
conn = get_conn()

st.title("Freight Markets")
st.caption("Segment coverage: dry bulk, container, crude tanker, product tanker, LNG, LPG, car carrier.")

with st.expander("Upload freight rates CSV"):
    render_csv_upload_widget(
        conn, dataset_key="freight_rates", target_table="market_data_daily",
        template_name="freight_rates_template.csv", label="Freight rates CSV", key_prefix="freight",
    )

show_sample = st.toggle("Show illustrative sample data where no real data is loaded", value=False,
                         help="Clearly labeled synthetic data for layout preview only. Never used in CFO Monitor.")
sample_df = generate_sample_freight_series() if show_sample else pd.DataFrame()

tabs = st.tabs(FREIGHT_SEGMENTS)
for tab, segment in zip(tabs, FREIGHT_SEGMENTS):
    with tab:
        view = get_segment_rate_view(conn, segment)
        history = view.history

        if history.empty and show_sample:
            seg_sample = sample_df[sample_df["segment"] == segment]
            col1, col2, col3 = st.columns(3)
            col1.metric("Latest (sample)", fmt_number(seg_sample.iloc[-1]["value"]))
            col2.metric("Unit", seg_sample.iloc[-1]["unit"])
            col3.metric("Status", "Sample (illustrative only)")
            fig = px.line(seg_sample, x="observation_date", y="value", title=f"{segment} — SAMPLE DATA, not real")
            fig.update_traces(line=dict(dash="dash"))
            st.plotly_chart(fig, width="stretch")
            st.warning("SAMPLE DATA — illustrative only, not a real market observation.")
        elif history.empty:
            st.info("Not available. No manual CSV uploaded and no free automated source exists for "
                    "this rate/index (see docs/source_register.md). Toggle sample data above to preview layout.")
        else:
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Latest", f"{fmt_number(view.latest_value)} {view.latest_unit or ''}")
            col2.metric("WoW change", fmt_pct(view.wow_change_pct))
            col3.metric("MoM change", fmt_pct(view.mom_change_pct))
            col4.metric("Observed", str(view.latest_date))
            fig = px.line(history, x="observation_date", y="value", title=f"{segment} — {history.iloc[-1]['metric']}")
            st.plotly_chart(fig, width="stretch")

        render_source_caption(view.source_meta)
        st.caption(f"Methodology: {view.methodology}")
