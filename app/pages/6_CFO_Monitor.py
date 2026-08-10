"""CFO Monitor — structured warning signals per company."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st

from src.config import WATCHLIST
from src.db_session import get_conn
from src.pages_logic.cfo_monitor import SignalLevel, get_company_signals
from src.utils.sidebar import render_sidebar

st.set_page_config(page_title="CFO Monitor | Shipping CFO Intelligence", layout="wide", page_icon="🚨")
render_sidebar()
conn = get_conn()

st.title("CFO Monitor")
st.caption("Structured warning signals: refinancing maturity, liquidity pressure, high LTV, large capex "
           "commitments, weak contract coverage, increasing interest expense, dividend sustainability, "
           "covenant risk, equity issuance risk, potential consolidation or M&A.")

names = [c["name"] for c in WATCHLIST]
selected = st.selectbox("Select company", names)

signals = get_company_signals(conn, selected)

level_order = {SignalLevel.ALERT: 0, SignalLevel.WARNING: 1, SignalLevel.OK: 2, SignalLevel.UNAVAILABLE: 3}
signals_sorted = sorted(signals, key=lambda s: level_order[s.level])

cols = st.columns(2)
for i, s in enumerate(signals_sorted):
    with cols[i % 2]:
        st.markdown(
            f"<div style='border:1px solid #d0d7de;border-radius:8px;padding:12px;margin-bottom:10px;'>"
            f"<span style='background:{s.level.color}20;color:{s.level.color};padding:2px 8px;"
            f"border-radius:10px;font-size:0.75rem;font-weight:600;'>{s.level.value.upper()}</span>"
            f"<div style='font-weight:600;margin-top:6px;'>{s.label}</div>"
            f"<div style='color:#57606a;font-size:0.9rem;margin-top:4px;'>{s.detail}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )

st.divider()
st.caption(
    "Signals marked UNAVAILABLE require data not yet in the manual financials template (debt "
    "maturity schedules, covenant terms, capex commitments, interest-expense history, LTV/vessel "
    "valuations). See docs/source_register.md for the plan to close these gaps."
)
