"""Clearly labeled illustrative sample data — used ONLY so a first-run user can see what a
populated chart looks like before any manual CSV has been uploaded. Never used for CFO Monitor
signals, never blended silently with real data, always tagged status=SAMPLE.
"""
from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd

from src.config import FREIGHT_SEGMENTS
from src.data_model import DataStatus

_SEGMENT_METRIC = {
    "Dry bulk": ("BDI (illustrative)", "index_pts", 1400),
    "Container": ("SCFI (illustrative)", "index_pts", 1900),
    "Crude tanker": ("WS crude TCE (illustrative)", "index_pts", 90),
    "Product tanker": ("WS product TCE (illustrative)", "index_pts", 110),
    "LNG": ("LNG spot TCE (illustrative)", "usd_per_day_000", 55),
    "LPG": ("BLPG1 (illustrative)", "usd_per_tonne", 65),
    "Car carrier": ("PCTC TC rate (illustrative)", "usd_per_day_000", 90),
}


def generate_sample_freight_series(days: int = 180) -> pd.DataFrame:
    """Deterministic (seeded) random-walk series purely for layout preview. Not a market observation."""
    rng = np.random.default_rng(seed=42)
    rows = []
    end = date.today()
    for segment in FREIGHT_SEGMENTS:
        metric, unit, base = _SEGMENT_METRIC[segment]
        walk = base + np.cumsum(rng.normal(0, base * 0.01, size=days))
        for i in range(days):
            obs_date = end - timedelta(days=days - i)
            rows.append({
                "segment": segment,
                "metric": metric,
                "value": float(walk[i]),
                "unit": unit,
                "observation_date": obs_date,
                "source": "SAMPLE DATA — not a real market observation",
                "frequency": "daily",
                "status": DataStatus.SAMPLE.value,
                "license_note": "Synthetic illustrative data for layout preview only.",
            })
    return pd.DataFrame(rows)
