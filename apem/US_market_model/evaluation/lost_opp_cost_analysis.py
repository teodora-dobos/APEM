from __future__ import annotations

from pathlib import Path

import pandas as pd

REQUIRED_COLUMNS = ("algorithm", "lost_opp_cost", "component", "value")
SUPPORTED_LOST_OPP_COSTS = {"glocs", "llocs", "mwps"}
SUPPORTED_COMPONENTS = {"buyers", "sellers", "network", "total"}

LOST_OPP_COST_LINE_LABELS = {
    "GLOCs buyers": ("glocs", "buyers"),
    "GLOCs sellers": ("glocs", "sellers"),
    "GLOCs network": ("glocs", "network"),
    "Total GLOCs": ("glocs", "total"),
    "LLOCs buyers": ("llocs", "buyers"),
    "LLOCs sellers": ("llocs", "sellers"),
    "LLOCs network": ("llocs", "network"),
    "Total LLOCs": ("llocs", "total"),
    "MWPs buyers": ("mwps", "buyers"),
    "MWPs sellers": ("mwps", "sellers"),
    "MWPs network": ("mwps", "network"),
    "Total MWPs": ("mwps", "total"),
}


def load_lost_opp_cost_table(
    path: str | Path,
    *,
    algorithm_column: str = "algorithm",
    lost_opp_cost_column: str = "lost_opp_cost",
    component_column: str = "component",
    value_column: str = "value",
    sheet_name: str = "Sheet1",
) -> pd.DataFrame:
    """Load a lost-opportunity-cost table from disk and normalize the core columns."""
    file_path = Path(path)
    suffix = file_path.suffix.lower()
    supported_suffixes = {".csv", ".parquet", ".txt", ".xlsx", ".xls"}

    if suffix not in supported_suffixes:
        supported = ", ".join(sorted(supported_suffixes))
        raise ValueError(f"Unsupported file type '{suffix}'. Supported types: {supported}.")

    if suffix == ".csv":
        df = pd.read_csv(file_path)
    elif suffix == ".parquet":
        df = pd.read_parquet(file_path)
    elif suffix == ".txt":
        df = _load_lost_opp_costs_from_stats_file(file_path)
    else:
        df = pd.read_excel(file_path, sheet_name=sheet_name)

    df = df.rename(columns=lambda value: str(value).strip())

    rename_map: dict[str, str] = {}
    if algorithm_column != "algorithm" and algorithm_column in df.columns:
        rename_map[algorithm_column] = "algorithm"
    if lost_opp_cost_column != "lost_opp_cost" and lost_opp_cost_column in df.columns:
        rename_map[lost_opp_cost_column] = "lost_opp_cost"
    if "objective" in df.columns and "lost_opp_cost" not in df.columns:
        rename_map["objective"] = "lost_opp_cost"
    if component_column != "component" and component_column in df.columns:
        rename_map[component_column] = "component"
    if value_column != "value" and value_column in df.columns:
        rename_map[value_column] = "value"
    if rename_map:
        df = df.rename(columns=rename_map)

    if "algorithm" not in df.columns:
        df["algorithm"] = _infer_algorithm_name(file_path)

    return validate_lost_opp_cost_table(df)


def validate_lost_opp_cost_table(df: pd.DataFrame) -> pd.DataFrame:
    """Validate and normalize the generic lost-opportunity-cost input table."""
    normalized = df.copy()
    normalized.columns = [str(column).strip() for column in normalized.columns]

    missing = [column for column in REQUIRED_COLUMNS if column not in normalized.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}. Required columns: {list(REQUIRED_COLUMNS)}.")

    normalized["algorithm"] = normalized["algorithm"].astype(str).str.strip()
    normalized["lost_opp_cost"] = normalized["lost_opp_cost"].astype(str).str.strip().str.lower()
    normalized["component"] = normalized["component"].astype(str).str.strip().str.lower()
    normalized["value"] = pd.to_numeric(normalized["value"], errors="coerce")

    if normalized["algorithm"].eq("").any():
        raise ValueError("Column 'algorithm' contains empty values.")
    if normalized["lost_opp_cost"].eq("").any():
        raise ValueError("Column 'lost_opp_cost' contains empty values.")
    if normalized["component"].eq("").any():
        raise ValueError("Column 'component' contains empty values.")

    invalid_lost_opp_costs = sorted(set(normalized["lost_opp_cost"]) - SUPPORTED_LOST_OPP_COSTS)
    if invalid_lost_opp_costs:
        raise ValueError(
            f"Unsupported lost_opp_cost values: {invalid_lost_opp_costs}. "
            f"Supported lost_opp_cost values: {sorted(SUPPORTED_LOST_OPP_COSTS)}."
        )

    invalid_components = sorted(set(normalized["component"]) - SUPPORTED_COMPONENTS)
    if invalid_components:
        raise ValueError(
            f"Unsupported component values: {invalid_components}. "
            f"Supported components: {sorted(SUPPORTED_COMPONENTS)}."
        )

    if normalized["value"].notna().sum() == 0:
        raise ValueError("Column 'value' does not contain any numeric values.")

    return normalized


def _infer_algorithm_name(file_path: Path) -> str:
    parent_name = file_path.parent.name
    if parent_name.endswith("_results"):
        return parent_name.removesuffix("_results")
    stem = file_path.stem
    if stem.endswith("_stats"):
        return stem.removesuffix("_stats")
    return stem


def _load_lost_opp_costs_from_stats_file(file_path: Path) -> pd.DataFrame:
    records: list[dict[str, object]] = []
    for line in file_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or ":" not in stripped:
            continue
        label, raw_value = stripped.split(":", maxsplit=1)
        if label not in LOST_OPP_COST_LINE_LABELS:
            continue

        lost_opp_cost, component = LOST_OPP_COST_LINE_LABELS[label]
        records.append(
            {
                "lost_opp_cost": lost_opp_cost,
                "component": component,
                "value": raw_value.strip(),
            }
        )

    return pd.DataFrame(records)
