"""Executive Brief — the landing page of the Shipping CFO Intelligence dashboard."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import plotly.express as px
import streamlit as st

from src.db_session import get_conn
from src.pages_logic.executive_brief import (
    get_cfo_implications_summary,
    get_company_announcements,
    get_rate_movements_table,
    get_segment_heatmap,
    get_top_news,
)
from src.utils.formatting import fmt_pct
from src.utils.sidebar import render_sidebar

st.set_page_config(page_title="Executive Brief | Shipping CFO Intelligence", layout="wide", page_icon="🚢")
render_sidebar()
conn = get_conn()

st.title("Executive Brief")
st.caption("Global shipping markets, fleet fundamentals, listed peers and CFO-relevant risk signals — one page.")

# 1. Five most important developments
st.subheader("1. Five things that matter today")
news = get_top_news(conn, n=5)
if news.empty:
    st.info("No news items loaded yet. Click **Refresh live data now** in the sidebar to pull free RSS headlines.")
else:
    for _, row in news.iterrows():
        st.markdown(f"**[{row['category']}]** [{row['headline']}]({row['url']})  \n"
                    f"<span style='color:#6e7781;font-size:0.8rem;'>{row['source']} · {row['published_date']}</span>",
                    unsafe_allow_html=True)

st.divider()

# 2. Segment heatmap
st.subheader("2. Segment heatmap — week-over-week rate change")
heat = get_segment_heatmap(conn)
available = heat.dropna(subset=["wow_change_pct"])
if available.empty:
    st.info("No freight-rate history available yet. Upload the freight rates CSV template on the "
            "Freight Markets page, or enable sample data there to preview the layout.")
else:
    fig = px.bar(available, x="segment", y="wow_change_pct", color="wow_change_pct",
                 color_continuous_scale="RdYlGn", labels={"wow_change_pct": "WoW change (%)"})
    fig.update_layout(height=320, coloraxis_showscale=False)
    st.plotly_chart(fig, width='stretch')
missing_segs = heat[heat["wow_change_pct"].isna()]["segment"].tolist()
if missing_segs:
    st.caption(f"Not available for: {', '.join(missing_segs)}.")

st.divider()

# 3. Rate and index movements
st.subheader("3. Rate and index movements")
rates = get_rate_movements_table(conn)
display_rates = rates.copy()
display_rates["WoW"] = display_rates["wow_change_pct"].apply(fmt_pct)
display_rates["MoM"] = display_rates["mom_change_pct"].apply(fmt_pct)
st.dataframe(
    display_rates[["segment", "latest_value", "unit", "observation_date", "WoW", "MoM", "status", "source"]]
    .rename(columns={"segment": "Segment", "latest_value": "Latest", "unit": "Unit",
                     "observation_date": "Observed", "status": "Status", "source": "Source"}),
    width='stretch', hide_index=True,
)

st.divider()

# 4. Company announcements
st.subheader("4. Important company announcements")
announcements = get_company_announcements(conn, n=5)
if announcements.empty:
    st.info("No company-reporting news captured yet.")
else:
    for _, row in announcements.iterrows():
        st.markdown(f"- [{row['headline']}]({row['url']}) — {row['source']}, {row['published_date']}")

st.divider()

# 5. CFO implications
st.subheader("5. CFO implications")
cfo_summary = get_cfo_implications_summary(conn)
alerts_total = int(cfo_summary["alerts"].sum())
warnings_total = int(cfo_summary["warnings"].sum())
col1, col2, col3 = st.columns(3)
col1.metric("Companies with active alerts", int((cfo_summary["alerts"] > 0).sum()))
col2.metric("Companies with warnings", int((cfo_summary["warnings"] > 0).sum()))
col3.metric("Total signals awaiting data", int(cfo_summary["signals_unavailable"].sum()))
st.dataframe(cfo_summary.rename(columns={"company": "Company", "alerts": "Alerts", "warnings": "Warnings",
                                          "signals_unavailable": "Signals awaiting data"}),
             width='stretch', hide_index=True)
st.caption("Full detail and definitions for every signal are on the CFO Monitor page.")

st.divider()
st.caption("Source links and timestamps are shown inline above and in full detail on each dedicated page.")
