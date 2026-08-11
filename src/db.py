"""DuckDB storage layer. Append-only, historized tables so trends can always be reconstructed.

Design: a small number of generic long-format ("tidy") tables rather than one table per metric,
so new metrics/segments/companies never require a schema migration. Daily market data, monthly/
quarterly fleet data, company financials and news are kept in separate tables per project rule
"separate daily market data from monthly or quarterly fleet data".
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import duckdb
import pandas as pd

from src.config import DB_PATH
from src.utils.logging_config import get_logger

log = get_logger("db")

SCHEMA_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS market_data_daily (
        segment VARCHAR,
        metric VARCHAR,
        value DOUBLE,
        unit VARCHAR,
        observation_date DATE,
        source VARCHAR,
        frequency VARCHAR,
        status VARCHAR,
        license_note VARCHAR,
        ingested_at TIMESTAMP DEFAULT current_timestamp
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS fleet_fundamentals (
        segment VARCHAR,
        metric VARCHAR,
        value DOUBLE,
        unit VARCHAR,
        observation_date DATE,
        source VARCHAR,
        frequency VARCHAR,
        status VARCHAR,
        license_note VARCHAR,
        ingested_at TIMESTAMP DEFAULT current_timestamp
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS company_market_data (
        company VARCHAR,
        ticker VARCHAR,
        metric VARCHAR,
        value DOUBLE,
        unit VARCHAR,
        currency VARCHAR,
        observation_date DATE,
        source VARCHAR,
        frequency VARCHAR,
        status VARCHAR,
        license_note VARCHAR,
        ingested_at TIMESTAMP DEFAULT current_timestamp
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS company_financials (
        company VARCHAR,
        metric VARCHAR,
        period VARCHAR,
        value DOUBLE,
        unit VARCHAR,
        observation_date DATE,
        source VARCHAR,
        frequency VARCHAR,
        status VARCHAR,
        license_note VARCHAR,
        ingested_at TIMESTAMP DEFAULT current_timestamp
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS news_events (
        published_date TIMESTAMP,
        category VARCHAR,
        headline VARCHAR,
        summary VARCHAR,
        source VARCHAR,
        url VARCHAR,
        status VARCHAR,
        ingested_at TIMESTAMP DEFAULT current_timestamp
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS manual_upload_log (
        filename VARCHAR,
        target_table VARCHAR,
        row_count INTEGER,
        validation_status VARCHAR,
        validation_notes VARCHAR,
        uploaded_at TIMESTAMP DEFAULT current_timestamp
    )
    """,
]

TABLE_KEY_COLUMNS = {
    "market_data_daily": ["segment", "metric", "observation_date", "source"],
    "fleet_fundamentals": ["segment", "metric", "observation_date", "source"],
    "company_market_data": ["company", "metric", "observation_date", "source"],
    "company_financials": ["company", "metric", "period", "source"],
    # Without a key here, every scheduled run re-inserts the same RSS/filing-alert items it fetched
    # last time (the feeds always return their most recent N items), so "Five things that matter"
    # and the News page silently fill up with duplicates of the same headline. (source, url) is
    # stable per article/filing across both the RSS adapter and the SEC filing-alerts adapter.
    "news_events": ["source", "url"],
}


def get_connection(db_path: Optional[Path] = None) -> duckdb.DuckDBPyConnection:
    path = db_path or DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = duckdb.connect(str(path))
    for stmt in SCHEMA_STATEMENTS:
        conn.execute(stmt)
    return conn


def _table_columns(conn: duckdb.DuckDBPyConnection, table: str) -> list[str]:
    return [row[1] for row in conn.execute(f"PRAGMA table_info('{table}')").fetchall()]


def upsert_dataframe(conn: duckdb.DuckDBPyConnection, table: str, df: pd.DataFrame) -> int:
    """Append rows, skipping ones that already exist for the same natural key.

    This preserves history (new observation dates always get added) while avoiding duplicate
    rows if the same adapter run happens twice (e.g. retried GitHub Actions job).

    Only columns that actually exist in the target table are inserted -- an adapter or manual CSV
    upload may include extra columns (e.g. free-text notes) that should be dropped rather than
    crash the whole ingestion.
    """
    if df.empty:
        return 0
    table_cols = set(_table_columns(conn, table))
    df = df[[c for c in df.columns if c in table_cols]]
    key_cols = TABLE_KEY_COLUMNS.get(table)
    conn.register("_incoming", df)
    if key_cols:
        key_expr = " AND ".join(f"t.{c} = i.{c}" for c in key_cols)
        existing = conn.execute(
            f"SELECT i.* FROM _incoming i WHERE NOT EXISTS "
            f"(SELECT 1 FROM {table} t WHERE {key_expr})"
        ).df()
    else:
        existing = df
    conn.unregister("_incoming")
    if existing.empty:
        log.info("upsert_dataframe: %s -- 0 new rows (all keys already present)", table)
        return 0
    conn.register("_new_rows", existing)
    cols = ", ".join(existing.columns)
    conn.execute(f"INSERT INTO {table} ({cols}) SELECT {cols} FROM _new_rows")
    conn.unregister("_new_rows")
    log.info("upsert_dataframe: %s -- inserted %d new rows", table, len(existing))
    return len(existing)


def latest_per_key(conn: duckdb.DuckDBPyConnection, table: str, partition_cols: list[str]) -> pd.DataFrame:
    """Return only the most recent observation per partition (e.g. per segment+metric)."""
    partition_expr = ", ".join(partition_cols)
    query = f"""
        SELECT * FROM (
            SELECT *, ROW_NUMBER() OVER (
                PARTITION BY {partition_expr} ORDER BY observation_date DESC, ingested_at DESC
            ) AS rn
            FROM {table}
        ) WHERE rn = 1
    """
    return conn.execute(query).df().drop(columns=["rn"], errors="ignore")


def log_manual_upload(conn: duckdb.DuckDBPyConnection, filename: str, target_table: str,
                       row_count: int, validation_status: str, validation_notes: str = "") -> None:
    conn.execute(
        "INSERT INTO manual_upload_log (filename, target_table, row_count, validation_status, validation_notes) "
        "VALUES (?, ?, ?, ?, ?)",
        [filename, target_table, row_count, validation_status, validation_notes],
    )
