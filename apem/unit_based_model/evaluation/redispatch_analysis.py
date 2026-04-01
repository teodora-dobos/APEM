"""Utilities for loading and validating redispatch cost and volume metrics."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

REQUIRED_COLUMNS = ("redispatch_algorithm", "metric", "value")
SUPPORTED_METRICS = {"costs", "volumes"}

REDISPATCH_FILE_PATTERNS = {
    "costs": "_redispatch_costs.csv",
    "volumes": "_redispatch_vols.csv",
}


def validate_redispatch_table(df: pd.DataFrame) -> pd.DataFrame:
    """Validate and normalize the generic redispatch-analysis input table."""
    normalized = df.copy()
    normalized.columns = [str(column).strip() for column in normalized.columns]

    missing = [column for column in REQUIRED_COLUMNS if column not in normalized.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}. Required columns: {list(REQUIRED_COLUMNS)}.")

    normalized["redispatch_algorithm"] = normalized["redispatch_algorithm"].astype(str).str.strip()
    normalized["metric"] = normalized["metric"].astype(str).str.strip().str.lower()
    normalized["value"] = pd.to_numeric(normalized["value"], errors="coerce")

    if normalized["redispatch_algorithm"].eq("").any():
        raise ValueError("Column 'redispatch_algorithm' contains empty values.")

    invalid_metrics = sorted(set(normalized["metric"]) - SUPPORTED_METRICS)
    if invalid_metrics:
        raise ValueError(
            f"Unsupported metric values: {invalid_metrics}. Supported metrics: {sorted(SUPPORTED_METRICS)}."
        )

    if normalized["value"].notna().sum() == 0:
        raise ValueError("Column 'value' does not contain any numeric values.")

    return normalized


def load_redispatch_metric_file(
    path: str | Path,
    *,
    redispatch_algorithm: str | None = None,
    metric: str | None = None,
) -> pd.DataFrame:
    """Load one redispatch metric file and normalize it to the generic table format."""
    file_path = Path(path)
    metric_name = metric or _infer_metric_name(file_path)
    algorithm_name = redispatch_algorithm or _infer_redispatch_algorithm_name(file_path)
    raw_text = file_path.read_text(encoding="utf-8").strip()
    if ":" not in raw_text:
        raise ValueError(f"Could not parse redispatch metric file: {file_path}")

    _, raw_value = raw_text.split(":", maxsplit=1)
    df = pd.DataFrame(
        [
            {
                "redispatch_algorithm": algorithm_name,
                "metric": metric_name,
                "value": raw_value.strip(),
            }
        ]
    )
    return validate_redispatch_table(df)


def _infer_metric_name(file_path: Path) -> str:
    name = file_path.name
    for metric, suffix in REDISPATCH_FILE_PATTERNS.items():
        if name.endswith(suffix):
            return metric
    raise ValueError(f"Could not infer redispatch metric from file name: {file_path.name}")


def _infer_redispatch_algorithm_name(file_path: Path) -> str:
    name = file_path.name
    for suffix in REDISPATCH_FILE_PATTERNS.values():
        if name.endswith(suffix):
            return name.removesuffix(suffix).split("_", 1)[0]
    raise ValueError(f"Could not infer redispatch algorithm from file name: {file_path.name}")
