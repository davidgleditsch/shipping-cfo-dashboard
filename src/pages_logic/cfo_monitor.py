"""CFO Monitor — structured risk-signal framework.

Every signal is defined once (id, label, plain-language description of what would trigger it) and
evaluated per company against whatever manual financial data has been uploaded. If the underlying
field has not been uploaded yet, the signal is explicitly UNAVAILABLE — never guessed. This keeps
the framework complete (all 10 required signal types are always shown) while being honest about
what can actually be assessed today with only revenue/EBITDA/net debt/cash/dividend/fleet/contract
coverage fields available.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable, Optional

import duckdb
import pandas as pd

from src.config import WATCHLIST


class SignalLevel(str, Enum):
    OK = "ok"
    WARNING = "warning"
    ALERT = "alert"
    UNAVAILABLE = "unavailable"

    @property
    def color(self) -> str:
        return {
            SignalLevel.OK: "#1a7f37",
            SignalLevel.WARNING: "#9a6700",
            SignalLevel.ALERT: "#cf222e",
            SignalLevel.UNAVAILABLE: "#6e7781",
        }[self]


@dataclass
class Signal:
    id: str
    label: str
    level: SignalLevel
    detail: str


def _get_financials(conn: duckdb.DuckDBPyConnection, company: str) -> dict[str, Optional[float]]:
    df = conn.execute(
        "SELECT metric, value FROM company_financials WHERE company = ? ORDER BY observation_date DESC",
        [company],
    ).df()
    out: dict[str, Optional[float]] = {}
    for metric in df["metric"].unique() if not df.empty else []:
        out[metric] = float(df[df["metric"] == metric].iloc[0]["value"])
    return out


def _signal_contract_coverage(fin: dict) -> Signal:
    val = fin.get("contract_coverage_pct")
    if val is None:
        return Signal("weak_contract_coverage", "Weak contract coverage", SignalLevel.UNAVAILABLE,
                       "No contract_coverage_pct uploaded yet.")
    if val < 30:
        return Signal("weak_contract_coverage", "Weak contract coverage", SignalLevel.ALERT,
                       f"Contract coverage is {val:.0f}% — high spot exposure.")
    if val < 50:
        return Signal("weak_contract_coverage", "Weak contract coverage", SignalLevel.WARNING,
                       f"Contract coverage is {val:.0f}% — moderate spot exposure.")
    return Signal("weak_contract_coverage", "Weak contract coverage", SignalLevel.OK,
                   f"Contract coverage is {val:.0f}%.")


def _signal_liquidity(fin: dict) -> Signal:
    cash = fin.get("cash")
    net_debt = fin.get("net_debt")
    if cash is None or net_debt is None:
        return Signal("liquidity_pressure", "Liquidity pressure", SignalLevel.UNAVAILABLE,
                       "Requires both cash and net_debt to be uploaded.")
    if net_debt <= 0:
        return Signal("liquidity_pressure", "Liquidity pressure", SignalLevel.OK,
                       "Company is in a net cash position.")
    ratio = cash / net_debt
    if ratio < 0.05:
        return Signal("liquidity_pressure", "Liquidity pressure", SignalLevel.ALERT,
                       f"Cash covers only {ratio:.0%} of net debt — heuristic check, review liquidity plan.")
    if ratio < 0.15:
        return Signal("liquidity_pressure", "Liquidity pressure", SignalLevel.WARNING,
                       f"Cash covers {ratio:.0%} of net debt — heuristic check, monitor liquidity.")
    return Signal("liquidity_pressure", "Liquidity pressure", SignalLevel.OK,
                   f"Cash covers {ratio:.0%} of net debt.")


def _signal_dividend_sustainability(fin: dict) -> Signal:
    dps = fin.get("dividend_per_share")
    ebitda = fin.get("ebitda")
    if dps is None or ebitda is None:
        return Signal("dividend_sustainability", "Dividend sustainability", SignalLevel.UNAVAILABLE,
                       "Requires both dividend_per_share and ebitda to be uploaded.")
    if dps > 0 and ebitda <= 0:
        return Signal("dividend_sustainability", "Dividend sustainability", SignalLevel.ALERT,
                       "Dividend declared despite non-positive EBITDA in the period — review sustainability.")
    if dps == 0:
        return Signal("dividend_sustainability", "Dividend sustainability", SignalLevel.OK,
                       "No dividend declared this period.")
    return Signal("dividend_sustainability", "Dividend sustainability", SignalLevel.OK,
                   "Dividend declared alongside positive EBITDA.")


# Signals that cannot be computed from the Step 1 manual-financials template (revenue, EBITDA,
# net debt, cash, dividend, fleet size, contract coverage, spot exposure). Each requires additional
# fields (debt maturity schedule, covenant terms, capex plan, interest expense trend, LTV, M&A
# activity feed) that are documented as gaps in docs/source_register.md.
_UNAVAILABLE_SIGNALS = [
    ("refinancing_maturity", "Refinancing maturity", "Requires a debt maturity schedule (not yet in manual template)."),
    ("high_ltv", "High LTV", "Requires vessel valuations and loan balances (blocked on NAV data gap)."),
    ("large_capex_commitments", "Large capex commitments", "Requires newbuilding/capex commitment schedule."),
    ("increasing_interest_expense", "Increasing interest expense", "Requires a multi-period interest expense series."),
    ("covenant_risk", "Covenant risk", "Requires covenant terms and headroom data from loan agreements."),
    ("equity_issuance_risk", "Equity issuance risk", "Requires capital plan / announced equity programs."),
    ("consolidation_or_ma_potential", "Potential consolidation or M&A", "Qualitative — tracked via News and Events (M&A and IPOs category), not a computed signal."),
]


def get_company_signals(conn: duckdb.DuckDBPyConnection, company: str) -> list[Signal]:
    fin = _get_financials(conn, company)
    signals = [
        _signal_contract_coverage(fin),
        _signal_liquidity(fin),
        _signal_dividend_sustainability(fin),
    ]
    for sig_id, label, detail in _UNAVAILABLE_SIGNALS:
        signals.append(Signal(sig_id, label, SignalLevel.UNAVAILABLE, detail))
    return signals


def get_all_signals(conn: duckdb.DuckDBPyConnection) -> dict[str, list[Signal]]:
    return {co["name"]: get_company_signals(conn, co["name"]) for co in WATCHLIST}


def get_signal_summary_table(conn: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    all_signals = get_all_signals(conn)
    rows = []
    for company, signals in all_signals.items():
        for s in signals:
            rows.append({"company": company, "signal": s.label, "level": s.level.value, "detail": s.detail})
    return pd.DataFrame(rows)
