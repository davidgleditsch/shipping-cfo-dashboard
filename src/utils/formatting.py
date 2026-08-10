"""Shared Streamlit rendering helpers so every page labels data consistently."""
from __future__ import annotations

import streamlit as st

from src.data_model import SourceMeta


def status_badge(meta: SourceMeta) -> str:
    return (
        f"<span style='background:{meta.status.color}20;color:{meta.status.color};"
        f"padding:2px 8px;border-radius:10px;font-size:0.75rem;font-weight:600;'>"
        f"{meta.status.label}</span>"
    )


def render_source_caption(meta: SourceMeta) -> None:
    st.markdown(
        f"{status_badge(meta)}&nbsp;&nbsp;<span style='color:#6e7781;font-size:0.8rem;'>{meta.caption()}</span>",
        unsafe_allow_html=True,
    )
    if meta.license_note:
        st.caption(meta.license_note)


def fmt_number(value, decimals: int = 1) -> str:
    if value is None:
        return "—"
    try:
        return f"{value:,.{decimals}f}"
    except (TypeError, ValueError):
        return "—"


def fmt_pct(value, decimals: int = 1) -> str:
    if value is None:
        return "—"
    sign = "+" if value > 0 else ""
    return f"{sign}{value:.{decimals}f}%"
