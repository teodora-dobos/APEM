"""Utilities for loading and validating welfare tables from structured files or allocation stats text files."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

REQUIRED_COLUMNS = ("power_flow_model", "welfare_scope", "period", "welfare")
SUPPORTED_WELFARE_SCOPES = {"period", "total"}


def load_welfare_table(
    path: str | Path,
    *,
    power_flow_model_name: str | None = None,
    welfare_scope_column: str = "welfare_scope",
    period_column: str = "period",
    welfare_column: str = "welfare",
    sheet_name: str = "Sheet1",
) -> pd.DataFrame:
    """
    Load a welfare table from disk and normalize core columns.

    Supported file types are ``.txt``, ``.csv``, ``.parquet``, ``.xlsx``,
    and ``.xls``.

    :param path: file path to load
    :param power_flow_model_name: model name override used when the loaded file
                                  does not include ``power_flow_model``
    :param welfare_scope_column: source column name mapped to ``welfare_scope``
    :param period_column: source column name mapped to ``period``
    :param welfare_column: source column name mapped to ``welfare``
    :param sheet_name: Excel sheet name when loading ``.xlsx``/``.xls``
    :return: validated normalized welfare table
    :raises ValueError: if file type is unsupported or parsed data fails
                        validation
    """
    file_path = Path(path)
    suffix = file_path.suffix.lower()
    supported_suffixes = {".txt", ".csv", ".parquet", ".xlsx", ".xls"}

    if suffix not in supported_suffixes:
        supported = ", ".join(sorted(supported_suffixes))
        raise ValueError(f"Unsupported file type '{suffix}'. Supported types: {supported}.")

    if suffix == ".txt":
        df = _load_welfare_from_stats_file(file_path)
    elif suffix == ".csv":
        df = pd.read_csv(file_path)
    elif suffix == ".parquet":
        df = pd.read_parquet(file_path)
    else:
        df = pd.read_excel(file_path, sheet_name=sheet_name)

    df = df.rename(columns=lambda value: str(value).strip())

    rename_map: dict[str, str] = {}
    if welfare_scope_column != "welfare_scope" and welfare_scope_column in df.columns:
        rename_map[welfare_scope_column] = "welfare_scope"
    if period_column != "period" and period_column in df.columns:
        rename_map[period_column] = "period"
    if welfare_column != "welfare" and welfare_column in df.columns:
        rename_map[welfare_column] = "welfare"
    if rename_map:
        df = df.rename(columns=rename_map)

    if "power_flow_model" not in df.columns:
        df["power_flow_model"] = power_flow_model_name or _infer_power_flow_model_name(file_path)

    return validate_welfare_table(df)


def validate_welfare_table(df: pd.DataFrame) -> pd.DataFrame:
    """
    Validate and normalize a generic welfare-analysis input table.

    :param df: input table expected to contain ``power_flow_model``,
               ``welfare_scope``, ``period``, and ``welfare``
    :return: normalized copy with lowercase scope labels, integer-like periods,
             and numeric welfare values
    :raises ValueError: if required columns are missing, scope values are
                        unsupported, model labels are empty, or period/scope
                        combinations are inconsistent
    """
    normalized = df.copy()
    normalized.columns = [str(column).strip() for column in normalized.columns]

    missing = [column for column in REQUIRED_COLUMNS if column not in normalized.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}. Required columns: {list(REQUIRED_COLUMNS)}.")

    normalized["power_flow_model"] = normalized["power_flow_model"].astype(str).str.strip()
    normalized["welfare_scope"] = normalized["welfare_scope"].astype(str).str.strip().str.lower()
    normalized["period"] = pd.to_numeric(normalized["period"], errors="coerce").astype("Int64")
    normalized["welfare"] = pd.to_numeric(normalized["welfare"], errors="coerce")

    if normalized["power_flow_model"].eq("").any():
        raise ValueError("Column 'power_flow_model' contains empty values.")

    invalid_scopes = sorted(set(normalized["welfare_scope"]) - SUPPORTED_WELFARE_SCOPES)
    if invalid_scopes:
        raise ValueError(
            f"Unsupported welfare_scope values: {invalid_scopes}. "
            f"Supported welfare_scope values: {sorted(SUPPORTED_WELFARE_SCOPES)}."
        )

    if normalized["welfare"].notna().sum() == 0:
        raise ValueError("Column 'welfare' does not contain any numeric values.")

    if ((normalized["welfare_scope"] == "period") & normalized["period"].isna()).any():
        raise ValueError("Rows with welfare_scope='period' must have a numeric period.")

    if ((normalized["welfare_scope"] == "total") & normalized["period"].notna()).any():
        raise ValueError("Rows with welfare_scope='total' must not have a period value.")

    return normalized


def _infer_power_flow_model_name(file_path: Path) -> str:
    stem = file_path.stem
    if stem.endswith("_stats"):
        return stem.removesuffix("_stats")
    return stem


def _load_welfare_from_stats_file(file_path: Path) -> pd.DataFrame:
    records: list[dict[str, object]] = []
    for line in file_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or ":" not in stripped:
            continue

        label, raw_value = stripped.split(":", maxsplit=1)
        label = label.strip()
        raw_value = raw_value.strip()

        if label.startswith("Welfare period "):
            records.append(
                {
                    "welfare_scope": "period",
                    "period": label.removeprefix("Welfare period ").strip(),
                    "welfare": raw_value,
                }
            )
        elif label == "Total welfare":
            records.append(
                {
                    "welfare_scope": "total",
                    "period": pd.NA,
                    "welfare": raw_value,
                }
            )

    return pd.DataFrame(records)
