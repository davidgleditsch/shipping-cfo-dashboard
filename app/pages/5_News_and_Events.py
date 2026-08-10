"""News and Events — categorized shipping news."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import plotly.express as px
import streamlit as st

from src.config import NEWS_CATEGORIES
from src.db_session import get_conn
from src.pages_logic.news_events import get_category_counts, get_news
from src.utils.sidebar import render_sidebar

st.set_page_config(page_title="News and Events | Shipping CFO Intelligence", layout="wide", page_icon="📰")
render_sidebar()
conn = get_conn()

st.title("News and Events")
st.caption("Free, public RSS sources only. Headline + link; no paywalled content reproduced.")

counts = get_category_counts(conn)
fig = px.bar(counts, x="n", y="category", orientation="h", labels={"n": "Items", "category": ""})
fig.update_layout(height=380)
st.plotly_chart(fig, width='stretch')

category = st.selectbox("Filter by category", ["All"] + NEWS_CATEGORIES)
news = get_news(conn, category=category, limit=100)

if news.empty:
    st.info("No news loaded yet. Click **Refresh live data now** in the sidebar.")
else:
    for _, row in news.iterrows():
        st.markdown(
            f"**[{row['category']}]** [{row['headline']}]({row['url']})  \n"
            f"<span style='color:#6e7781;font-size:0.8rem;'>{row['source']} · {row['published_date']}</span>",
            unsafe_allow_html=True,
        )
        st.divider()
