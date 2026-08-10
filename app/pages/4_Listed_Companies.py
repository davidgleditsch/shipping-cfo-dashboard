"""Listed Companies -- watchlist market data, financial placeholders, NAV gap disclosure."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import plotly.express as px
import streamlit as st

from src.db_session import get_conn
from src.pages_logic.listed_companies import get_company_views, get_latest_fx_rate
from src.utils.formatting import fmt_number, render_source_caption
from src.utils.sidebar import render_sidebar
from src.utils.uploads import render_csv_upload_widget

st.set_page_config(page_title="Listed Companies | Shipping CFO Intelligence", layout="wide", page_icon="🏢")
render_sidebar()
conn = get_conn()

st.title("Listed Companies")
st.caption("Watchlist: Wallenius Wilhelmsen, Hoegh Autoliners, MPC Container Ships, Hafnia, Odfjell, "
           "BW LPG, Golden Ocean, Flex LNG, Klaveness Combination Carriers, Cool Company.")

fx = get_latest_fx_rate(conn, "USDNOK")
if fx:
    rate, fx_meta = fx
    st.caption(f"Reference FX: 1 USD = {rate:.4f} NOK ({fx_meta.caption()})")
else:
    st.caption("Reference FX rate not loaded yet — click 'Refresh live data now' in the sidebar (Frankfurter/ECB, free).")

with st.expander("Upload company financials CSV"):
    render_csv_upload_widget(
        conn, dataset_key="company_financials", target_table="company_financials",
        template_name="company_financials_template.csv", label="Company financials CSV",
        key_prefix="fin",
    )

views = get_company_views(conn)
names = [v.name for v in views]
selected = st.selectbox("Select company", names)
view = next(v for v in views if v.name == selected)

if not view.listed:
    st.error(f"**No longer publicly listed.** {view.status_note}")

col1, col2 = st.columns([2, 1])
with col1:
    st.subheader(f"{view.name} ({view.ticker}) — {view.segment}")
    if view.status_note and view.listed:
        st.info(view.status_note)
    if not view.price_history.empty:
        fig = px.line(view.price_history, x="observation_date", y="value",
                      title=f"Share price ({view.currency})")
        st.plotly_chart(fig, width="stretch")
    elif view.listed:
        st.info("Price history not available.")
    render_source_caption(view.price_source_meta)

with col2:
    if view.listed:
        st.metric("Latest price", f"{fmt_number(view.latest_price)} {view.currency or ''}", help=view.price_date)
    else:
        st.metric("Latest price", "Delisted")

st.divider()
st.subheader("Financials (manual, quarterly)")
fin_cols = st.columns(4)
for i, (metric_key, data) in enumerate(view.financials.items()):
    with fin_cols[i % 4]:
        val = f"{fmt_number(data['value'])} {data['unit'] or ''}" if data["value"] is not None else "Not available"
        st.metric(data["label"], val)
        render_source_caption(data["source_meta"])
        st.markdown("&nbsp;")

st.divider()
st.subheader("Estimated NAV / Price-to-NAV")
st.warning(view.nav_status)
st.caption("Per project policy, NAV is not calculated until vessel-value assumptions are sourced "
           "and documented (see docs/source_register.md and docs/assumptions.md).")
