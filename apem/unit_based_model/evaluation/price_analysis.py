"""Utilities for validating, summarizing, and comparing price tables across algorithms."""

from __future__ import annotations

from itertools import combinations
from typing import Sequence

import numpy as np
import pandas as pd

REQUIRED_COLUMNS = ("algorithm", "price")


def validate_price_table(df: pd.DataFrame) -> pd.DataFrame:
    """
    Validate and normalize a generic price-analysis input table.

    :param df: input table containing at least ``algorithm`` and ``price``
               columns; additional columns are preserved
    :return: normalized copy with trimmed column names, normalized algorithm
             labels, and numeric ``price`` values
    :raises ValueError: if required columns are missing, algorithm labels are
                        empty, or no numeric prices are available
    """
    normalized = df.copy()
    normalized.columns = [str(column).strip() for column in normalized.columns]

    missing = [column for column in REQUIRED_COLUMNS if column not in normalized.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}. Required columns: {list(REQUIRED_COLUMNS)}.")

    normalized["algorithm"] = normalized["algorithm"].astype(str).str.strip()
    normalized["price"] = pd.to_numeric(normalized["price"], errors="coerce")

    if normalized["algorithm"].eq("").any():
        raise ValueError("Column 'algorithm' contains empty values.")

    if normalized["price"].notna().sum() == 0:
        raise ValueError("Column 'price' does not contain any numeric values.")

    return normalized


def summarize_prices(
    df: pd.DataFrame,
    *,
    group_by: Sequence[str] = ("algorithm",),
) -> pd.DataFrame:
    """
    Compute descriptive statistics for prices grouped by one or more columns.

    :param df: input price table
    :param group_by: grouping columns to summarize by; defaults to
                     ``("algorithm",)``
    :return: one row per group with counts, central moments, quantiles, spread,
             and additional quality metrics
    """
    validated = validate_price_table(df)
    group_columns = _normalize_group_columns(validated, group_by)

    summary = (
        validated.groupby(list(group_columns), dropna=False)["price"]
        .agg(
            count="count",
            mean="mean",
            median="median",
            std="std",
            variance="var",
            min="min",
            max="max",
            p05=lambda series: series.quantile(0.05),
            p25=lambda series: series.quantile(0.25),
            p75=lambda series: series.quantile(0.75),
            p95=lambda series: series.quantile(0.95),
        )
        .reset_index()
    )

    auxiliary = (
        validated.groupby(list(group_columns), dropna=False)["price"]
        .apply(_auxiliary_price_metrics)
        .unstack()
        .reset_index()
    )

    result = summary.merge(auxiliary, on=list(group_columns), how="left")
    ordered_columns = list(group_columns) + [
        "count",
        "missing_count",
        "negative_price_count",
        "mean",
        "median",
        "std",
        "variance",
        "coefficient_of_variation",
        "min",
        "max",
        "spread",
        "p05",
        "p25",
        "p75",
        "p95",
    ]
    return result.loc[:, ordered_columns]


def compare_price_algorithms(
    df: pd.DataFrame,
    *,
    align_on: Sequence[str] | None = None,
    baseline: str | None = None,
) -> pd.DataFrame:
    """
    Compare algorithm price series on aligned observations.

    :param df: input price table with one ``algorithm`` and ``price`` value per
               aligned observation
    :param align_on: explicit alignment key columns; when omitted, all
                     non-required columns are used, or an inferred row index if
                     none are available
    :param baseline: optional algorithm name; if provided, only pairs including
                     this baseline are returned
    :return: pairwise comparison table with mean levels, mean differences,
             absolute differences, and correlation per algorithm pair
    :raises ValueError: if duplicates exist for the same alignment key and
                        algorithm, if fewer than two algorithms are present, or
                        if ``baseline`` is not present
    """
    validated = validate_price_table(df)
    alignment_columns, prepared = _prepare_alignment(validated, align_on)

    duplicates = prepared.duplicated(subset=[*alignment_columns, "algorithm"], keep=False)
    if duplicates.any():
        duplicate_rows = prepared.loc[duplicates, [*alignment_columns, "algorithm"]]
        preview = duplicate_rows.head(5).to_dict(orient="records")
        raise ValueError(
            "Found duplicate rows for the same algorithm and alignment key. "
            f"Examples: {preview}"
        )

    wide = prepared.pivot(index=list(alignment_columns), columns="algorithm", values="price")
    algorithm_names = list(wide.columns)
    if len(algorithm_names) < 2:
        raise ValueError("At least two algorithms are required for pairwise comparison.")

    pairs = combinations(algorithm_names, 2)
    if baseline is not None:
        if baseline not in algorithm_names:
            raise ValueError(f"Baseline '{baseline}' not found. Available algorithms: {algorithm_names}.")
        pairs = ((left, right) for left, right in pairs if baseline in (left, right))

    comparisons: list[dict[str, float | int | str]] = []
    for left, right in pairs:
        pair = wide[[left, right]].dropna()
        if pair.empty:
            continue

        difference = pair[left] - pair[right]
        absolute_difference = difference.abs()
        comparisons.append(
            {
                "algorithm_left": left,
                "algorithm_right": right,
                "shared_observations": int(pair.shape[0]),
                "mean_left": float(pair[left].mean()),
                "mean_right": float(pair[right].mean()),
                "mean_difference": float(difference.mean()),
                "mean_absolute_difference": float(absolute_difference.mean()),
                "max_absolute_difference": float(absolute_difference.max()),
                "correlation": float(pair[left].corr(pair[right])),
            }
        )

    return pd.DataFrame(comparisons)


def round_numeric_columns(df: pd.DataFrame, digits: int = 2) -> pd.DataFrame:
    """
    Round all numeric columns to a fixed number of decimal places.

    :param df: input table
    :param digits: number of decimals used for rounding numeric columns
    :return: copy of ``df`` with rounded numeric columns
    """
    rounded = df.copy()
    numeric_columns = rounded.select_dtypes(include="number").columns
    rounded.loc[:, numeric_columns] = rounded.loc[:, numeric_columns].round(digits)
    return rounded


def _normalize_group_columns(df: pd.DataFrame, group_by: Sequence[str]) -> tuple[str, ...]:
    group_columns = tuple(group_by) if group_by else ("algorithm",)
    missing = [column for column in group_columns if column not in df.columns]
    if missing:
        raise ValueError(f"Grouping columns not found: {missing}.")
    return group_columns


def _prepare_alignment(
    df: pd.DataFrame,
    align_on: Sequence[str] | None,
) -> tuple[tuple[str, ...], pd.DataFrame]:
    prepared = df.copy()

    if align_on is None:
        inferred = [column for column in prepared.columns if column not in REQUIRED_COLUMNS]
        if inferred:
            alignment_columns = tuple(inferred)
        else:
            prepared["row_number"] = prepared.groupby("algorithm").cumcount()
            alignment_columns = ("row_number",)
    else:
        alignment_columns = tuple(align_on)

    missing = [column for column in alignment_columns if column not in prepared.columns]
    if missing:
        raise ValueError(f"Alignment columns not found: {missing}.")

    return alignment_columns, prepared


def _auxiliary_price_metrics(series: pd.Series) -> pd.Series:
    valid = series.dropna()
    mean = valid.mean()
    std = valid.std()
    coefficient_of_variation = np.nan
    if pd.notna(mean) and mean != 0 and pd.notna(std):
        coefficient_of_variation = float(std / mean)

    spread = np.nan
    if not valid.empty:
        spread = float(valid.max() - valid.min())

    return pd.Series(
        {
            "missing_count": int(series.isna().sum()),
            "negative_price_count": int((valid < 0).sum()),
            "spread": spread,
            "coefficient_of_variation": coefficient_of_variation,
        }
    )
