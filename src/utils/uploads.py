"""Shared manual-CSV upload widget: validate, preview, warn, then require explicit confirmation
before anything is written to the database. Used by Freight Markets, Fleet Fundamentals and
Listed Companies pages so the upload workflow behaves identically everywhere.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from src.adapters.manual_csv_adapter import validate_csv
from src.db import log_manual_upload, upsert_dataframe


def render_csv_upload_widget(conn, dataset_key: str, target_table: str, template_name: str,
                              label: str, key_prefix: str) -> None:
    st.write(f"Use the template in `data/templates/{template_name}`.")
    up = st.file_uploader(label, type=["csv"], key=f"{key_prefix}_file")
    if up is None:
        return

    try:
        df_raw = pd.read_csv(up)
    except Exception as exc:
        st.error(f"Could not read file as CSV: {exc}")
        return

    result = validate_csv(dataset_key, df_raw, conn=conn)

    if not result.is_valid:
        log_manual_upload(conn, up.name, target_table, 0, "invalid", "; ".join(result.errors))
        for e in result.errors:
            st.error(e)
        return

    st.caption(f"{len(result.cleaned)} row(s) validated — review below, then confirm to ingest.")
    st.dataframe(result.cleaned, width="stretch", hide_index=True)
    for w in result.warnings:
        st.warning(w)

    if st.button(f"Confirm and ingest {len(result.cleaned)} row(s)", key=f"{key_prefix}_confirm"):
        n = upsert_dataframe(conn, target_table, result.cleaned)
        log_manual_upload(conn, up.name, target_table, n, "valid", "; ".join(result.warnings))
        st.success(f"Ingested {n} new row(s).")
