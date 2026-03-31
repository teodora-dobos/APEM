"""
Example script for comparing one pricing algorithm across the three zonal unit-based power-flow models.

The script:
1. parses one unit-based dataset,
2. reuses the latest matching run for each zonal model and zonal configuration, or computes it if missing,
3. loads the resulting price CSVs into one normalized evaluation table,
4. writes grouped price tables, summary statistics, pairwise comparisons, and plots.

You can adapt the zonal models by editing the constants near the top of the file.

Each execution writes a new timestamped evaluation folder under:
`results/unit_based_model/<scenario>_results/evaluation/zonal_price_comparison/`
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
import sys
from pathlib import Path
from typing import Callable, Sequence

if "MPLCONFIGDIR" not in os.environ:
    os.environ["MPLCONFIGDIR"] = str(Path(__file__).resolve().parents[2] / ".matplotlib_cache")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from apem.execution_chain import _retrieve_data, analyse_results, solve_unit_based_scenario
from apem.unit_based_model.allocation.algorithms.zonal_clearing.zonal_fbmc_included import Zonal_FBMC
from apem.unit_based_model.allocation.algorithms.zonal_clearing.zonal_ntc_aggregated import Zonal_NTC_aggregated
from apem.unit_based_model.allocation.algorithms.zonal_clearing.zonal_ntc_multiedge import Zonal_NTC_multiedge
from apem.unit_based_model.evaluation import (
    compare_price_algorithms,
    normalize_run_dir,
    parse_run_config,
    round_numeric_columns,
    statistic_name,
    summarize_prices,
)
from apem.unit_based_model.enums import FBMCBaseCases, PricingAlgorithms, UnitBased_Datasets

DATASET = UnitBased_Datasets.PyPSAEurLarge
ZONAL_CONFIGURATION = "zonal_DE4"
PRICING_ALGORITHM = PricingAlgorithms.IP
NTC_FACTOR = 0.8
FBMC_BASE_CASE = FBMCBaseCases.BC4.value
PLOT_STATISTIC_FN = np.mean

UNIT_BASED_RESULTS_DIR = ROOT / "results" / "unit_based_model"


def build_power_flow_models() -> tuple:
    return (
        Zonal_NTC_aggregated(zonal_configuration=ZONAL_CONFIGURATION, factor=NTC_FACTOR),
        Zonal_NTC_multiedge(zonal_configuration=ZONAL_CONFIGURATION, factor=NTC_FACTOR),
        Zonal_FBMC(zonal_configuration=ZONAL_CONFIGURATION, base_case_type=FBMC_BASE_CASE),
    )


def dataset_root(scenario_name: str) -> Path:
    return UNIT_BASED_RESULTS_DIR / f"{scenario_name}_results"


def evaluation_root(scenario_name: str) -> Path:
    return dataset_root(scenario_name) / "evaluation" / "zonal_price_comparison"


def create_evaluation_output_dir(
    scenario_name: str,
    pricing_algorithm: PricingAlgorithms,
    zonal_configuration: str,
) -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_dir = evaluation_root(scenario_name) / f"{timestamp}_{zonal_configuration}_{pricing_algorithm.name}"
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def zonal_path_for_model(power_flow_model) -> str:
    if isinstance(power_flow_model, Zonal_FBMC):
        base_case = getattr(power_flow_model, "base_case_type", "")
        return f"{power_flow_model.zonal_configuration}_{base_case}" if base_case else power_flow_model.zonal_configuration
    factor = getattr(power_flow_model, "factor", None)
    factor_str = f"_f{factor}" if factor is not None else ""
    return f"{power_flow_model.zonal_configuration}{factor_str}"


def price_file_for_run(run_dir: Path, pricing_algorithm: PricingAlgorithms, power_flow_model, zonal_path: str) -> Path:
    return (
        run_dir
        / str(power_flow_model)
        / zonal_path
        / f"{pricing_algorithm.name}_results"
        / f"{pricing_algorithm.name}_prices.csv"
    )


def find_latest_matching_zonal_run(
    results_root: Path,
    dataset: UnitBased_Datasets,
    pricing_algorithm: PricingAlgorithms,
    power_flow_model,
) -> Path | None:
    if not results_root.exists():
        return None

    expected_model_name = str(power_flow_model)
    expected_zonal_path = zonal_path_for_model(power_flow_model)
    candidates: list[tuple[str, float, Path]] = []

    for run_config_path in results_root.glob("*/run_config.txt"):
        run_dir = run_config_path.parent
        metadata = parse_run_config(run_config_path)
        if metadata.get("dataset") != dataset.name:
            continue
        if metadata.get("power_flow_model") != expected_model_name:
            continue
        if metadata.get("pricing_algorithm") != pricing_algorithm.name:
            continue
        if metadata.get("zonal_path", "") != expected_zonal_path:
            continue

        price_file = price_file_for_run(run_dir, pricing_algorithm, power_flow_model, expected_zonal_path)
        if not price_file.exists():
            continue

        created_at = metadata.get("created_at_utc", "")
        candidates.append((created_at, run_dir.stat().st_mtime, run_dir))

    if not candidates:
        return None

    candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return candidates[0][2]


def ensure_run_for_model(
    results_root: Path,
    repo_root: Path,
    dataset: UnitBased_Datasets,
    pricing_algorithm: PricingAlgorithms,
    power_flow_model,
) -> tuple[Path, str]:
    existing_run = find_latest_matching_zonal_run(
        results_root,
        dataset,
        pricing_algorithm,
        power_flow_model,
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


def load_prices_for_model(
    run_dir: Path,
    scenario_name: str,
    pricing_algorithm: PricingAlgorithms,
    power_flow_model,
) -> pd.DataFrame:
    zonal_path = zonal_path_for_model(power_flow_model)
    df = pd.read_csv(price_file_for_run(run_dir, pricing_algorithm, power_flow_model, zonal_path))
    model_name = str(power_flow_model)
    df["dataset"] = scenario_name
    df["power_flow_model"] = model_name
    df["algorithm"] = model_name
    df["pricing_algorithm"] = pricing_algorithm.name
    return df[["dataset", "power_flow_model", "algorithm", "pricing_algorithm", "node", "period", "price"]]


def run_zonal_price_comparison(
    dataset: UnitBased_Datasets = DATASET,
    pricing_algorithm: PricingAlgorithms = PRICING_ALGORITHM,
) -> tuple[pd.DataFrame, dict[str, dict[str, str]]]:
    scenario = _retrieve_data(dataset)
    scenario_name = scenario.name
    if dataset not in (UnitBased_Datasets.PyPSAEurLarge, UnitBased_Datasets.PyPSAEurSmall):
        raise ValueError("This comparison requires one of the PyPSA datasets.")

    all_prices = []
    selected_runs: dict[str, dict[str, str]] = {}
    results_root = dataset_root(scenario_name)
    power_flow_models = build_power_flow_models()

    for power_flow_model in power_flow_models:
        run_dir, source = ensure_run_for_model(
            results_root=results_root,
            repo_root=ROOT,
            dataset=dataset,
            pricing_algorithm=pricing_algorithm,
            power_flow_model=power_flow_model,
        )
        all_prices.append(
            load_prices_for_model(
                run_dir,
                scenario_name,
                pricing_algorithm,
                power_flow_model,
            )
        )
        selected_runs[str(power_flow_model)] = {
            "source": source,
            "run_dir": str(run_dir),
            "zonal_path": zonal_path_for_model(power_flow_model),
        }

    prices = pd.concat(all_prices, ignore_index=True)
    return prices, selected_runs


def pivot_prices_by_node_period(
    prices: pd.DataFrame,
    power_flow_model_names: Sequence[str],
) -> pd.DataFrame:
    grouped = (
        prices.pivot(
            index=["dataset", "node", "period"],
            columns="power_flow_model",
            values="price",
        )
        .reset_index()
        .rename_axis(columns=None)
    )
    ordered_columns = ["dataset", "node", "period"] + [
        model_name for model_name in power_flow_model_names if model_name in grouped.columns
    ]
    return grouped.loc[:, ordered_columns]


def _aggregate_prices(
    prices: pd.DataFrame,
    group_by: Sequence[str],
    statistic_fn: Callable[[np.ndarray], float],
) -> pd.DataFrame:
    return (
        prices.groupby(list(group_by), dropna=False)["price"]
        .agg(statistic_fn)
        .reset_index()
    )


def _resolve_model_order(available: Sequence[str], desired: Sequence[str] | None) -> list[str]:
    available_list = [str(item) for item in available]
    if desired is None:
        return available_list
    ordered = [str(item) for item in desired if str(item) in available_list]
    ordered.extend(item for item in available_list if item not in ordered)
    return ordered


def _plot_model_boxplot(
    aggregated_prices: pd.DataFrame,
    output_file: Path,
    *,
    power_flow_model_order: Sequence[str] | None,
    title: str,
    ylabel: str,
) -> None:
    ordered_models = [
        model_name
        for model_name in _resolve_model_order(aggregated_prices.columns, power_flow_model_order)
        if model_name in aggregated_prices.columns
    ]
    data = [aggregated_prices[model_name].dropna().to_numpy() for model_name in ordered_models]

    plt.figure(figsize=(10, 6))
    plt.boxplot(data, tick_labels=ordered_models, patch_artist=True)
    plt.ylabel(ylabel)
    plt.title(title)
    plt.xticks(rotation=20, ha="right")
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(output_file, dpi=200)
    plt.close()


def plot_average_prices_by_period_and_power_flow_model(
    prices: pd.DataFrame,
    output_file: Path,
    *,
    power_flow_model_order: Sequence[str] | None = None,
    statistic_fn: Callable[[np.ndarray], float] = np.mean,
) -> None:
    statistic_label = statistic_name(statistic_fn)
    aggregated_prices = _aggregate_prices(prices, ["period", "power_flow_model"], statistic_fn).pivot(
        index="period",
        columns="power_flow_model",
        values="price",
    ).sort_index()

    plt.figure(figsize=(10, 6))
    for model_name in _resolve_model_order(aggregated_prices.columns, power_flow_model_order):
        plt.plot(aggregated_prices.index, aggregated_prices[model_name], marker="o", label=model_name)

    plt.xlabel("Period")
    plt.ylabel(f"{statistic_label} Price")
    plt.title(f"{statistic_label} Prices by Period and Power-Flow Model")
    plt.xticks(aggregated_prices.index.tolist())
    plt.grid(True)
    plt.legend()
    plt.tight_layout()
    plt.savefig(output_file, dpi=200)
    plt.close()


def plot_average_prices_by_node_and_power_flow_model(
    prices: pd.DataFrame,
    output_file: Path,
    *,
    power_flow_model_order: Sequence[str] | None = None,
    statistic_fn: Callable[[np.ndarray], float] = np.mean,
) -> None:
    statistic_label = statistic_name(statistic_fn)
    aggregated_prices = _aggregate_prices(prices, ["node", "power_flow_model"], statistic_fn).pivot(
        index="node",
        columns="power_flow_model",
        values="price",
    )

    sort_reference = next(iter(_resolve_model_order(aggregated_prices.columns, power_flow_model_order)), None)
    if sort_reference is not None:
        aggregated_prices = aggregated_prices.sort_values(by=sort_reference)

    aggregated_prices = aggregated_prices.reset_index()
    x_positions = range(len(aggregated_prices))

    plt.figure(figsize=(14, 7))
    for model_name in _resolve_model_order(aggregated_prices.columns, power_flow_model_order):
        if model_name == "node":
            continue
        plt.plot(
            x_positions,
            aggregated_prices[model_name],
            marker="o",
            markersize=2,
            linewidth=1,
            label=model_name,
        )

    tick_step = max(1, len(aggregated_prices) // 20)
    tick_positions = list(range(0, len(aggregated_prices), tick_step))
    tick_labels = aggregated_prices.loc[tick_positions, "node"].astype(str).tolist()

    plt.xlabel("Node")
    plt.ylabel(f"{statistic_label} Price")
    plt.title(f"{statistic_label} Prices by Node and Power-Flow Model")
    plt.xticks(tick_positions, tick_labels, rotation=45, ha="right")
    plt.grid(True)
    plt.legend()
    plt.tight_layout()
    plt.savefig(output_file, dpi=200)
    plt.close()


def plot_price_boxplot_by_period_and_power_flow_model(
    prices: pd.DataFrame,
    output_file: Path,
    *,
    power_flow_model_order: Sequence[str] | None = None,
    statistic_fn: Callable[[np.ndarray], float] = np.mean,
) -> None:
    aggregated_prices = _aggregate_prices(prices, ["period", "power_flow_model"], statistic_fn).pivot(
        index="period",
        columns="power_flow_model",
        values="price",
    )
    _plot_model_boxplot(
        aggregated_prices,
        output_file,
        power_flow_model_order=power_flow_model_order,
        title=f"Boxplot of {statistic_name(statistic_fn)} Prices by Period and Power-Flow Model",
        ylabel=f"{statistic_name(statistic_fn)} Price",
    )


def plot_price_boxplot_by_node_and_power_flow_model(
    prices: pd.DataFrame,
    output_file: Path,
    *,
    power_flow_model_order: Sequence[str] | None = None,
    statistic_fn: Callable[[np.ndarray], float] = np.mean,
) -> None:
    aggregated_prices = _aggregate_prices(prices, ["node", "power_flow_model"], statistic_fn).pivot(
        index="node",
        columns="power_flow_model",
        values="price",
    )
    _plot_model_boxplot(
        aggregated_prices,
        output_file,
        power_flow_model_order=power_flow_model_order,
        title=f"Boxplot of {statistic_name(statistic_fn)} Prices by Node and Power-Flow Model",
        ylabel=f"{statistic_name(statistic_fn)} Price",
    )


def main() -> None:
    prices, selected_runs = run_zonal_price_comparison()
    scenario_name = prices["dataset"].iloc[0]
    dataset_output_dir = create_evaluation_output_dir(
        scenario_name,
        PRICING_ALGORITHM,
        ZONAL_CONFIGURATION,
    )

    power_flow_models = build_power_flow_models()
    power_flow_model_names = [str(model) for model in power_flow_models]
    statistic_token = statistic_name(PLOT_STATISTIC_FN)
    period_plot_file = dataset_output_dir / f"{statistic_token}_prices_by_period.png"
    node_plot_file = dataset_output_dir / f"{statistic_token}_prices_by_node.png"
    period_boxplot_file = dataset_output_dir / f"{statistic_token}_prices_boxplot_by_period.png"
    node_boxplot_file = dataset_output_dir / f"{statistic_token}_prices_boxplot_by_node.png"

    grouped_prices = round_numeric_columns(pivot_prices_by_node_period(prices, power_flow_model_names))
    summary = round_numeric_columns(summarize_prices(prices, group_by=["power_flow_model"]))
    comparisons = round_numeric_columns(
        compare_price_algorithms(
            prices,
            align_on=["dataset", "node", "period"],
        ).rename(
            columns={
                "algorithm_left": "power_flow_model_left",
                "algorithm_right": "power_flow_model_right",
            }
        )
    )

    plot_average_prices_by_period_and_power_flow_model(
        prices,
        period_plot_file,
        power_flow_model_order=power_flow_model_names,
        statistic_fn=PLOT_STATISTIC_FN,
    )
    plot_average_prices_by_node_and_power_flow_model(
        prices,
        node_plot_file,
        power_flow_model_order=power_flow_model_names,
        statistic_fn=PLOT_STATISTIC_FN,
    )
    plot_price_boxplot_by_period_and_power_flow_model(
        prices,
        period_boxplot_file,
        power_flow_model_order=power_flow_model_names,
        statistic_fn=PLOT_STATISTIC_FN,
    )
    plot_price_boxplot_by_node_and_power_flow_model(
        prices,
        node_boxplot_file,
        power_flow_model_order=power_flow_model_names,
        statistic_fn=PLOT_STATISTIC_FN,
    )

    grouped_prices.to_csv(dataset_output_dir / "prices.csv", index=False)
    summary.to_csv(dataset_output_dir / "summary_by_power_flow_model.csv", index=False)
    comparisons.to_csv(dataset_output_dir / "pairwise_comparisons.csv", index=False)

    metadata = {
        "dataset": DATASET.name,
        "scenario_name": scenario_name,
        "pricing_algorithm": PRICING_ALGORITHM.name,
        "zonal_configuration": ZONAL_CONFIGURATION,
        "ntc_factor": NTC_FACTOR,
        "fbmc_base_case": FBMC_BASE_CASE,
        "power_flow_models": [type(model).__name__ for model in power_flow_models],
        "power_flow_model_names": power_flow_model_names,
        "prices_csv_layout": "grouped_by_dataset_node_period_power_flow_model",
        "plot_statistic": statistic_token,
        "prices_by_period_plot": str(period_plot_file),
        "prices_by_node_plot": str(node_plot_file),
        "prices_boxplot_by_period": str(period_boxplot_file),
        "prices_boxplot_by_node": str(node_boxplot_file),
        "selected_runs": selected_runs,
        "evaluation_root": str(dataset_output_dir),
    }
    with open(dataset_output_dir / "metadata.json", "w", encoding="utf-8") as handle:
        json.dump(metadata, handle, indent=2)


if __name__ == "__main__":
    main()


