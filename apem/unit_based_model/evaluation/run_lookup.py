"""Helpers for reusing or loading the latest matching US-model runs from the results directory."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from apem.execution_chain import analyse_results, solve_unit_based_allocation_only, solve_unit_based_scenario
from apem.unit_based_model.allocation.algorithms.zonal_clearing.zonal_fbmc_included import Zonal_FBMC
from apem.unit_based_model.allocation.algorithms.zonal_clearing.zonal_ntc_aggregated import Zonal_NTC_aggregated
from apem.unit_based_model.allocation.algorithms.zonal_clearing.zonal_ntc_multiedge import Zonal_NTC_multiedge
from apem.unit_based_model.evaluation.lost_opp_cost_analysis import load_lost_opp_cost_table
from apem.unit_based_model.evaluation.redispatch_analysis import load_redispatch_metric_file
from apem.unit_based_model.evaluation.welfare_analysis import load_welfare_table
from apem.unit_based_model.enums import PricingAlgorithms, RedispatchAlgorithms, UnitBased_Datasets


def normalize_run_dir(path: Path | str, repo_root: Path) -> Path:
    """Resolve run directories relative to the repository root when needed."""
    run_dir = Path(path)
    if not run_dir.is_absolute():
        run_dir = repo_root / run_dir
    return run_dir


def parse_run_config(run_config_path: Path) -> dict[str, str]:
    """Parse the key-value metadata written next to each run."""
    metadata: dict[str, str] = {}
    with open(run_config_path, "r", encoding="utf-8") as handle:
        for line in handle:
            if "=" not in line:
                continue
            key, value = line.strip().split("=", 1)
            metadata[key] = value
    return metadata


def expected_zonal_path(power_flow_model) -> str:
    """Return the zonal-path metadata expected for one power-flow model."""
    if isinstance(power_flow_model, Zonal_FBMC):
        base_case = getattr(power_flow_model, "base_case_type", "")
        return f"{power_flow_model.zonal_configuration}_{base_case}" if base_case else power_flow_model.zonal_configuration
    if isinstance(power_flow_model, (Zonal_NTC_aggregated, Zonal_NTC_multiedge)):
        factor = getattr(power_flow_model, "factor", None)
        factor_str = f"_f{factor}" if factor is not None else ""
        return f"{power_flow_model.zonal_configuration}{factor_str}"
    return ""


def find_latest_matching_run(
    results_root: Path,
    dataset: UnitBased_Datasets,
    pricing_algorithm: PricingAlgorithms,
    power_flow_model_name: str,
    zonal_path: str = "",
) -> Path | None:
    """Return the newest run folder matching the requested dataset/model/pricing configuration."""
    if not results_root.exists():
        return None

    candidates: list[tuple[str, float, Path]] = []
    for run_config_path in results_root.glob("*/run_config.txt"):
        run_dir = run_config_path.parent
        metadata = parse_run_config(run_config_path)
        run_zonal_path = metadata.get("zonal_path", "")
        price_file = (
            run_dir
            / power_flow_model_name
            / run_zonal_path
            / f"{pricing_algorithm.name}_results"
            / f"{pricing_algorithm.name}_prices.csv"
        )
        if not price_file.exists():
            continue
        if metadata.get("dataset") != dataset.name:
            continue
        if metadata.get("power_flow_model") != power_flow_model_name:
            continue
        if metadata.get("pricing_algorithm") != pricing_algorithm.name:
            continue
        if run_zonal_path != zonal_path:
            continue

        created_at = metadata.get("created_at_utc", "")
        candidates.append((created_at, run_dir.stat().st_mtime, run_dir))

    if not candidates:
        return None

    candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return candidates[0][2]


def find_latest_matching_lost_opp_cost_run(
    results_root: Path,
    dataset: UnitBased_Datasets,
    pricing_algorithm: PricingAlgorithms,
    power_flow_model_name: str,
    zonal_path: str = "",
) -> Path | None:
    """Return the newest run folder matching the requested configuration with lost opportunity cost stats available."""
    if not results_root.exists():
        return None

    candidates: list[tuple[str, float, Path]] = []
    for run_config_path in results_root.glob("*/run_config.txt"):
        run_dir = run_config_path.parent
        metadata = parse_run_config(run_config_path)
        run_zonal_path = metadata.get("zonal_path", "")
        stats_file = (
            run_dir
            / power_flow_model_name
            / run_zonal_path
            / f"{pricing_algorithm.name}_results"
            / f"{pricing_algorithm.name}_stats.txt"
        )
        if not stats_file.exists():
            continue
        if metadata.get("dataset") != dataset.name:
            continue
        if metadata.get("power_flow_model") != power_flow_model_name:
            continue
        if metadata.get("pricing_algorithm") != pricing_algorithm.name:
            continue
        if run_zonal_path != zonal_path:
            continue

        created_at = metadata.get("created_at_utc", "")
        candidates.append((created_at, run_dir.stat().st_mtime, run_dir))

    if not candidates:
        return None

    candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return candidates[0][2]


def ensure_run_for_configuration(
    results_root: Path,
    repo_root: Path,
    dataset: UnitBased_Datasets,
    pricing_algorithm: PricingAlgorithms,
    power_flow_model,
    power_flow_model_name: str,
) -> tuple[Path, str]:
    """Return the latest matching run folder, computing it first if necessary."""
    zonal_path = expected_zonal_path(power_flow_model)
    existing_run = find_latest_matching_run(
        results_root,
        dataset,
        pricing_algorithm,
        power_flow_model_name=power_flow_model_name,
        zonal_path=zonal_path,
    )
    if existing_run is not None:
        return existing_run, "reused"

    analysis = solve_unit_based_scenario(
        dataset=dataset,
        power_flow_model=power_flow_model,
        pricing_algorithm=pricing_algorithm,
    )
    return normalize_run_dir(analysis.results_root, repo_root), "computed"


def ensure_lost_opp_cost_run_for_configuration(
    results_root: Path,
    repo_root: Path,
    dataset: UnitBased_Datasets,
    pricing_algorithm: PricingAlgorithms,
    power_flow_model,
    power_flow_model_name: str,
) -> tuple[Path, str]:
    """Return the latest matching run folder with lost opportunity cost stats, computing analysis first if necessary."""
    zonal_path = expected_zonal_path(power_flow_model)
    existing_run = find_latest_matching_lost_opp_cost_run(
        results_root,
        dataset,
        pricing_algorithm,
        power_flow_model_name=power_flow_model_name,
        zonal_path=zonal_path,
    )
    if existing_run is not None:
        return existing_run, "reused"

    analysis = solve_unit_based_scenario(
        dataset=dataset,
        power_flow_model=power_flow_model,
        pricing_algorithm=pricing_algorithm,
    )
    run_root = normalize_run_dir(analysis.results_root, repo_root)
    analyse_results(
        analysis.scenario,
        analysis.allocation,
        analysis.pricing,
        analysis.configuration,
        power_flow_model,
        base_scenario=getattr(analysis, "base_scenario", None),
        results_root=str(run_root),
    )
    return run_root, "computed"


def load_prices_from_run(
    run_dir: Path,
    scenario_name: str,
    pricing_algorithm: PricingAlgorithms,
    power_flow_model_name: str,
) -> pd.DataFrame:
    """Load one algorithm's price CSV from a selected run folder."""
    metadata = parse_run_config(run_dir / "run_config.txt")
    zonal_path = metadata.get("zonal_path", "")
    price_file = (
        run_dir
        / power_flow_model_name
        / zonal_path
        / f"{pricing_algorithm.name}_results"
        / f"{pricing_algorithm.name}_prices.csv"
    )
    df = pd.read_csv(price_file)
    df["dataset"] = scenario_name
    df["algorithm"] = pricing_algorithm.name
    return df[["dataset", "algorithm", "node", "period", "price"]]


def load_lost_opp_costs_from_run(
    run_dir: Path,
    scenario_name: str,
    pricing_algorithm: PricingAlgorithms,
    power_flow_model_name: str,
) -> pd.DataFrame:
    """Load one algorithm's GLOC/LLOC/MWP values from a selected run folder."""
    metadata = parse_run_config(run_dir / "run_config.txt")
    zonal_path = metadata.get("zonal_path", "")
    stats_file = (
        run_dir
        / power_flow_model_name
        / zonal_path
        / f"{pricing_algorithm.name}_results"
        / f"{pricing_algorithm.name}_stats.txt"
    )
    df = load_lost_opp_cost_table(stats_file)
    df["dataset"] = scenario_name
    df["algorithm"] = pricing_algorithm.name
    return df[["dataset", "algorithm", "lost_opp_cost", "component", "value"]]


def find_latest_matching_welfare_run(
    results_root: Path,
    dataset: UnitBased_Datasets,
    power_flow_model_name: str,
    zonal_path: str = "",
) -> Path | None:
    """Return the newest run folder matching the requested dataset/model with allocation stats available."""
    if not results_root.exists():
        return None

    candidates: list[tuple[str, float, Path]] = []
    for run_config_path in results_root.glob("*/run_config.txt"):
        run_dir = run_config_path.parent
        metadata = parse_run_config(run_config_path)
        run_zonal_path = metadata.get("zonal_path", "")
        stats_file = (
            run_dir
            / power_flow_model_name
            / run_zonal_path
            / "allocation_results"
            / f"{power_flow_model_name}_stats.txt"
        )
        if not stats_file.exists():
            continue
        if metadata.get("dataset") != dataset.name:
            continue
        if metadata.get("power_flow_model") != power_flow_model_name:
            continue
        if run_zonal_path != zonal_path:
            continue

        created_at = metadata.get("created_at_utc", "")
        candidates.append((created_at, run_dir.stat().st_mtime, run_dir))

    if not candidates:
        return None

    candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return candidates[0][2]


def ensure_welfare_run_for_configuration(
    results_root: Path,
    repo_root: Path,
    dataset: UnitBased_Datasets,
    power_flow_model,
    power_flow_model_name: str,
) -> tuple[Path, str]:
    """Return the latest matching run folder with welfare stats, computing it first if necessary."""
    zonal_path = expected_zonal_path(power_flow_model)
    existing_run = find_latest_matching_welfare_run(
        results_root,
        dataset,
        power_flow_model_name=power_flow_model_name,
        zonal_path=zonal_path,
    )
    if existing_run is not None:
        return existing_run, "reused"

    run_root = solve_unit_based_allocation_only(
        dataset=dataset,
        power_flow_model=power_flow_model,
    )
    return normalize_run_dir(run_root, repo_root), "computed"


def load_welfare_from_run(
    run_dir: Path,
    scenario_name: str,
    power_flow_model_name: str,
) -> pd.DataFrame:
    """Load welfare values from a selected run folder."""
    metadata = parse_run_config(run_dir / "run_config.txt")
    zonal_path = metadata.get("zonal_path", "")
    stats_file = (
        run_dir
        / power_flow_model_name
        / zonal_path
        / "allocation_results"
        / f"{power_flow_model_name}_stats.txt"
    )
    df = load_welfare_table(stats_file, power_flow_model_name=power_flow_model_name)
    df["dataset"] = scenario_name
    return df[["dataset", "power_flow_model", "welfare_scope", "period", "welfare"]]


def find_latest_matching_redispatch_run(
    results_root: Path,
    dataset: UnitBased_Datasets,
    power_flow_model_name: str,
    redispatch_algorithm: RedispatchAlgorithms,
    redispatch_constraint_units: bool = False,
    redispatch_threshold: float = 0,
    zonal_path: str = "",
) -> Path | None:
    """Return the newest run folder matching the requested redispatch configuration."""
    if not results_root.exists():
        return None

    candidates: list[tuple[str, float, Path]] = []
    redispatch_suffix = (
        f"{redispatch_algorithm.name}_{redispatch_constraint_units}_{redispatch_threshold}_redispatch_costs.csv"
    )
    for run_config_path in results_root.glob("*/run_config.txt"):
        run_dir = run_config_path.parent
        metadata = parse_run_config(run_config_path)
        run_zonal_path = metadata.get("zonal_path", "")
        stats_file = (
            run_dir
            / power_flow_model_name
            / run_zonal_path
            / "allocation_results"
            / "redispatch"
            / redispatch_suffix
        )
        if not stats_file.exists():
            continue
        if metadata.get("dataset") != dataset.name:
            continue
        if metadata.get("power_flow_model") != power_flow_model_name:
            continue
        if metadata.get("redispatch_algorithm") != redispatch_algorithm.name:
            continue
        if run_zonal_path != zonal_path:
            continue

        created_at = metadata.get("created_at_utc", "")
        candidates.append((created_at, run_dir.stat().st_mtime, run_dir))

    if not candidates:
        return None

    candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return candidates[0][2]


def ensure_redispatch_run_for_configuration(
    results_root: Path,
    repo_root: Path,
    dataset: UnitBased_Datasets,
    power_flow_model,
    power_flow_model_name: str,
    redispatch_algorithm: RedispatchAlgorithms,
    pricing_algorithm: PricingAlgorithms,
    redispatch_constraint_units: bool = False,
    redispatch_threshold: float = 0,
) -> tuple[Path, str]:
    """Return the latest matching run folder with redispatch metrics, computing it first if necessary."""
    zonal_path = expected_zonal_path(power_flow_model)
    existing_run = find_latest_matching_redispatch_run(
        results_root,
        dataset,
        power_flow_model_name=power_flow_model_name,
        redispatch_algorithm=redispatch_algorithm,
        redispatch_constraint_units=redispatch_constraint_units,
        redispatch_threshold=redispatch_threshold,
        zonal_path=zonal_path,
    )
    if existing_run is not None:
        return existing_run, "reused"

    analysis = solve_unit_based_scenario(
        dataset=dataset,
        power_flow_model=power_flow_model,
        pricing_algorithm=pricing_algorithm,
        redispatch_algorithm=redispatch_algorithm,
        redispatch_constraint_units=redispatch_constraint_units,
        redispatch_threshold=redispatch_threshold,
    )
    return normalize_run_dir(analysis.results_root, repo_root), "computed"


def load_redispatch_metrics_from_run(
    run_dir: Path,
    scenario_name: str,
    power_flow_model_name: str,
    redispatch_algorithm: RedispatchAlgorithms,
    redispatch_constraint_units: bool = False,
    redispatch_threshold: float = 0,
) -> pd.DataFrame:
    """Load redispatch metrics from a selected run folder."""
    metadata = parse_run_config(run_dir / "run_config.txt")
    zonal_path = metadata.get("zonal_path", "")
    redispatch_root = (
        run_dir
        / power_flow_model_name
        / zonal_path
        / "allocation_results"
        / "redispatch"
    )
    stem = f"{redispatch_algorithm.name}_{redispatch_constraint_units}_{redispatch_threshold}"
    metric_files = {
        "costs": redispatch_root / f"{stem}_redispatch_costs.csv",
        "volumes": redispatch_root / f"{stem}_redispatch_vols.csv",
    }

    metrics = [
        load_redispatch_metric_file(
            path,
            redispatch_algorithm=redispatch_algorithm.name,
            metric=metric,
        )
        for metric, path in metric_files.items()
    ]
    df = pd.concat(metrics, ignore_index=True)
    df["dataset"] = scenario_name
    df["power_flow_model"] = power_flow_model_name
    df["redispatch_constraint_units"] = redispatch_constraint_units
    df["redispatch_threshold"] = redispatch_threshold
    return df[
        [
            "dataset",
            "power_flow_model",
            "redispatch_algorithm",
            "redispatch_constraint_units",
            "redispatch_threshold",
            "metric",
            "value",
        ]
    ]


