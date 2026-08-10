"""Base interface every source adapter must implement.

Swapping a free source for a licensed one (Clarksons, Baltic Exchange, VesselsValue, Xeneta,
Drewry, S&P Global) later should only require writing a new class that implements `fetch()` and
registering it — page code never talks to a provider directly.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd

from src.data_model import DataStatus


class SourceAdapter(ABC):
    name: str = "unnamed-source"
    frequency: str = "unknown"
    license_note: str = ""

    @abstractmethod
    def fetch(self) -> pd.DataFrame:
        """Return a DataFrame matching the target table schema, or an empty DataFrame on failure.

        Must never raise for network/data errors — catch internally, log, and return empty.
        """
        raise NotImplementedError

    def default_status(self) -> DataStatus:
        return DataStatus.UNAVAILABLE
