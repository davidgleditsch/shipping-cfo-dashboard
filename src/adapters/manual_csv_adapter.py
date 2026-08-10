"""Validated ingestion of analyst-uploaded CSVs for data with no free/legal automated source.

Each dataset has a documented schema (matching data/templates/*.csv). Validation failures are
collected and returned to the caller so the UI can show exactly what is wrong, rather than silently
dropping or guessing at bad rows -- consistent with "never fabricate or interpolate."

Step 2 additions: in-file duplicate detection, a per-metric expected-unit dictionary (warns on
mismatch rather than blocking, since unit conventions vary by broker), an outlier/jump check against
the most recent existing observation in the database (when a connection is supplied), and a row-count
ceiling to catch obviously wrong file uploads.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import duckdb
import pandas as pd

from src.config import FREIGHT_SEGMENTS, WATCHLIST
from src.data_model import DataStatus
from src.utils.logging_config import get_logger

log = get_logger("adapters.manual_csv")

_COMPANY_NAMES = {c["name"] for c in WATCHLIST}

MAX_ROWS_PER_UPLOAD = 5000

# Expected unit per canonical metric key, used across fleet_fundamentals/orderbook/scrapping and
# company_financials templates. Freight rate metrics are free-text (segment-specific index names
# chosen by the analyst) so they are intentionally not covered here -- only a plausibility check
# happens for those via the outlier check, not a fixed unit dictionary.
UNIT_DICTIONARY = {
    "trading_fleet_count": "vessels",
    "orderbook_units": "vessels",
    "orderbook_pct_fleet": "percent",
    "expected_deliveries_units": "vessels",
    "scrapping_units": "vessels",
    "scrapping_dwt": "dwt",
    "avg_fleet_age_years": "years",
    "pct_fleet_over_20yrs": "percent",
    "revenue": "usd_million",
    "ebitda": "usd_million",
    "net_debt": "usd_million",
    "cash": "usd_million",
    "dividend_per_share": "usd_per_share",
    "fleet_size": "vessels",
    "contract_coverage_pct": "percent",
    "spot_exposure_pct": "percent",
}

# A jump larger than this (as a fraction of the prior value) versus the most recent existing
# observation for the same key triggers a warning, not a hard error -- real market moves can be
# large, but this catches likely typos (e.g. a misplaced decimal point) before they enter history.
OUTLIER_JUMP_THRESHOLD = 0.75


@dataclass
class ValidationResult:
    is_valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    cleaned: pd.DataFrame | None = None


DATASET_SCHEMAS = {
    "freight_rates": {
        "target_table": "market_data_daily",
        "required_columns": ["segment", "metric", "value", "unit", "observation_date", "source", "frequency"],
        "segment_column": "segment",
        "key_columns": ["segment", "metric", "observation_date", "source"],
        "partition_columns": ["segment", "metric"],
    },
    "fleet_fundamentals": {
        "target_table": "fleet_fundamentals",
        "required_columns": ["segment", "metric", "value", "unit", "observation_date", "source", "frequency"],
        "segment_column": "segment",
        "key_columns": ["segment", "metric", "observation_date", "source"],
        "partition_columns": ["segment", "metric"],
    },
    "orderbook": {
        "target_table": "fleet_fundamentals",
        "required_columns": ["segment", "metric", "value", "unit", "observation_date", "source", "frequency"],
        "segment_column": "segment",
        "key_columns": ["segment", "metric", "observation_date", "source"],
        "partition_columns": ["segment", "metric"],
    },
    "scrapping": {
        "target_table": "fleet_fundamentals",
        "required_columns": ["segment", "metric", "value", "unit", "observation_date", "source", "frequency"],
        "segment_column": "segment",
        "key_columns": ["segment", "metric", "observation_date", "source"],
        "partition_columns": ["segment", "metric"],
    },
    "company_financials": {
        "target_table": "company_financials",
        "required_columns": ["company", "metric", "period", "value", "unit", "observation_date", "source", "frequency"],
        "segment_column": None,
        "key_columns": ["company", "metric", "period", "source"],
        "partition_columns": ["company", "metric"],
    },
}


def _check_in_file_duplicates(df: pd.DataFrame, key_columns: list[str]) -> list[str]:
    dup_mask = df.duplicated(subset=key_columns, keep=False)
    if not dup_mask.any():
        return []
    dup_rows = df.index[dup_mask].tolist()
    return [
        f"Duplicate rows within the uploaded file for the same {key_columns}: row(s) {dup_rows}. "
        "Remove duplicates before uploading -- each combination should appear once per file."
    ]


def _check_units(df: pd.DataFrame) -> list[str]:
    warnings = []
    for metric, expected_unit in UNIT_DICTIONARY.items():
        rows = df[df["metric"] == metric]
        if rows.empty:
            continue
        mismatched = rows[rows["unit"] != expected_unit]
        if not mismatched.empty:
            warnings.append(
                f"Metric '{metric}' is usually reported in '{expected_unit}' but row(s) "
                f"{mismatched.index.tolist()} use '{sorted(set(mismatched['unit']))}'. "
                "Double-check the unit is not a typo."
            )
    return warnings


def _check_outliers(df: pd.DataFrame, target_table: str, partition_columns: list[str],
                     conn: Optional[duckdb.DuckDBPyConnection]) -> list[str]:
    if conn is None:
        return []
    warnings = []
    try:
        existing = conn.execute(f"SELECT * FROM {target_table}").df()
    except Exception as exc:  # table may not exist yet in a fresh/test DB -- treat as no history
        log.warning("Outlier check could not read %s: %s", target_table, exc)
        return []
    if existing.empty:
        return []
    for idx, row in df.iterrows():
        mask = pd.Series(True, index=existing.index)
        for col in partition_columns:
            mask &= existing[col] == row[col]
        prior = existing[mask].sort_values("observation_date")
        if prior.empty:
            continue
        prior_value = prior.iloc[-1]["value"]
        if prior_value == 0:
            continue
        change = abs(row["value"] - prior_value) / abs(prior_value)
        if change > OUTLIER_JUMP_THRESHOLD:
            warnings.append(
                f"Row {idx}: {row['metric']} moved {change:.0%} versus the most recent existing "
                f"observation ({prior_value:g} -> {row['value']:g}). Please double-check this isn't a data-entry error."
            )
    return warnings


def validate_csv(dataset: str, df: pd.DataFrame,
                  conn: Optional[duckdb.DuckDBPyConnection] = None) -> ValidationResult:
    if dataset not in DATASET_SCHEMAS:
        return ValidationResult(False, errors=[f"Unknown dataset type '{dataset}'."])

    schema = DATASET_SCHEMAS[dataset]
    errors: list[str] = []
    warnings: list[str] = []

    if len(df) > MAX_ROWS_PER_UPLOAD:
        return ValidationResult(False, errors=[
            f"File has {len(df)} rows, which exceeds the {MAX_ROWS_PER_UPLOAD}-row limit per upload. "
            "Split into smaller files (e.g. by segment or by quarter)."
        ])

    missing = [c for c in schema["required_columns"] if c not in df.columns]
    if missing:
        errors.append(f"Missing required column(s): {', '.join(missing)}")
        return ValidationResult(False, errors=errors)

    df = df.copy()

    if df.empty:
        errors.append("File contains no data rows.")
        return ValidationResult(False, errors=errors)

    # value must be numeric
    non_numeric = pd.to_numeric(df["value"], errors="coerce").isna() & df["value"].notna()
    if non_numeric.any():
        bad_rows = df.index[non_numeric].tolist()
        errors.append(f"Non-numeric 'value' in row(s): {bad_rows}")
    df["value"] = pd.to_numeric(df["value"], errors="coerce")

    # observation_date must parse
    parsed_dates = pd.to_datetime(df["observation_date"], errors="coerce")
    bad_dates = parsed_dates.isna() & df["observation_date"].notna()
    if bad_dates.any():
        errors.append(f"Unparseable 'observation_date' in row(s): {df.index[bad_dates].tolist()}")
    df["observation_date"] = parsed_dates.dt.date

    if df["observation_date"].isna().any() or df["value"].isna().any():
        errors.append("Some rows have missing/invalid value or observation_date after parsing.")

    # future dates are suspicious for an "observation"
    today = pd.Timestamp.utcnow().date()
    future_mask = df["observation_date"].apply(lambda d: d is not None and d > today)
    if future_mask.any():
        warnings.append(f"Row(s) {df.index[future_mask].tolist()} have a future observation_date — check for typos.")

    seg_col = schema["segment_column"]
    if seg_col:
        bad_segments = ~df[seg_col].isin(FREIGHT_SEGMENTS)
        if bad_segments.any():
            errors.append(
                f"Unrecognized segment(s) in row(s) {df.index[bad_segments].tolist()}: "
                f"{sorted(set(df.loc[bad_segments, seg_col]))}. Must be one of {FREIGHT_SEGMENTS}."
            )

    if dataset == "company_financials":
        bad_companies = ~df["company"].isin(_COMPANY_NAMES)
        if bad_companies.any():
            warnings.append(
                f"Company name(s) not in the current watchlist (row(s) {df.index[bad_companies].tolist()}): "
                f"{sorted(set(df.loc[bad_companies, 'company']))}. Row will still be ingested."
            )

    if "frequency" in df.columns and df["frequency"].isna().any():
        errors.append("Missing 'frequency' value in one or more rows.")

    errors.extend(_check_in_file_duplicates(df, schema["key_columns"]))

    if errors:
        return ValidationResult(False, errors=errors, warnings=warnings)

    # From here on the file is structurally valid -- remaining checks are advisory (warnings only).
    warnings.extend(_check_units(df))
    warnings.extend(_check_outliers(df, schema["target_table"], schema["partition_columns"], conn))

    df["status"] = DataStatus.MANUAL.value
    if "license_note" not in df.columns:
        df["license_note"] = "Manually entered by analyst from a licensed/subscribed source."
    df["ingested_at"] = datetime.utcnow()

    keep_cols = schema["required_columns"] + ["status"]
    if "license_note" in df.columns:
        keep_cols.append("license_note")
    if "currency" in df.columns:
        keep_cols.append("currency")
    if "notes" in df.columns:
        keep_cols.append("notes")
    cleaned = df[[c for c in keep_cols if c in df.columns]]

    return ValidationResult(True, errors=[], warnings=warnings, cleaned=cleaned)


def target_table_for(dataset: str) -> str:
    return DATASET_SCHEMAS[dataset]["target_table"]
