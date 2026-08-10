"""Pure logic for the News and Events page."""
from __future__ import annotations

from typing import Optional

import duckdb
import pandas as pd

from src.config import NEWS_CATEGORIES


def get_news(conn: duckdb.DuckDBPyConnection, category: Optional[str] = None, limit: int = 100) -> pd.DataFrame:
    if category and category != "All":
        df = conn.execute(
            "SELECT * FROM news_events WHERE category = ? ORDER BY published_date DESC LIMIT ?",
            [category, limit],
        ).df()
    else:
        df = conn.execute(
            "SELECT * FROM news_events ORDER BY published_date DESC LIMIT ?", [limit]
        ).df()
    return df


def get_category_counts(conn: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    df = conn.execute(
        "SELECT category, COUNT(*) AS n FROM news_events GROUP BY category ORDER BY n DESC"
    ).df()
    # ensure every category is represented, even with 0, so UI can show a full picture
    all_cats = pd.DataFrame({"category": NEWS_CATEGORIES})
    merged = all_cats.merge(df, on="category", how="left").fillna({"n": 0})
    merged["n"] = merged["n"].astype(int)
    return merged
