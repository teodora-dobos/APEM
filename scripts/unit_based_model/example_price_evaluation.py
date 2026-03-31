"""
Example script for comparing real price outputs from DCOPF pricing algorithms.

The script:
1. parses one unit-based dataset,
2. reuses the latest matching run for each selected pricing algorithm, or computes it if missing,
3. loads the resulting price CSVs into one normalized evaluation table,
4. writes grouped price tables, summary statistics, pairwise comparisons, and plots.

You can adapt the evaluation by editing the constants near the top of the file:
- `DATASET`: choose the unit-based dataset to analyze.
- `POWER_FLOW_MODEL`: choose the power-flow model from `apem.unit_based_model.enums.PowerFlowModels`
  such as `PowerFlowModels.DCOPF`, `PowerFlowModels.Zonal_NTC_aggregated`,
  `PowerFlowModels.Zonal_NTC_multiedge`, or `PowerFlowModels.Zonal_FBMC`.
- `PRICING_ALGORITHMS`: choose the pricing algorithms to compare.
- `PLOT_STATISTIC_FN`: choose the statistic used in the saved plots, for example
  `np.mean`, `np.std`, or `np.var`.

Each execution writes a new timestamped evaluation folder under:
`results/unit_based_model/<scenario>_results/evaluation/price_comparison/`
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
import sys
from pathlib import Path

if "MPLCONFIGDIR" not in os.environ:
    os.environ["MPLCONFIGDIR"] = str(Path(__file__).resolve().parents[2] / ".matplotlib_cache")

import numpy as np
import pandas as pd

# Ensure repo root is on sys.path when run directly
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from apem.execution_chain import _retrieve_data
from apem.unit_based_model.enums import PowerFlowModels, PricingAlgorithms, UnitBased_Datasets
from apem.unit_based_model.evaluation import (
    compare_price_algorithms,
    ensure_run_for_configuration,
    load_prices_from_run,
    plot_average_prices_by_node,
    plot_average_prices_by_period,
    plot_price_boxplot_by_node,
    plot_price_boxplot_by_period,
    round_numeric_columns,
    statistic_name,
    summarize_prices,
)

DATASET = UnitBased_Datasets.PyPSAEurLarge
POWER_FLOW_MODEL = PowerFlowModels.DCOPF
PRICING_ALGORITHMS = (
    PricingAlgorithms.IP,
    PricingAlgorithms.ELMP,
    PricingAlgorithms.Join,
)
PLOT_STATISTIC_FN = np.mean

UNIT_BASED_RESULTS_DIR = ROOT / "results" / "unit_based_model"
POWER_FLOW_MODEL_NAME = str(POWER_FLOW_MODEL.value)


def dataset_root(scenario_name: str) -> Path:
    """Return the root results folder using the main pipeline naming convention."""
    return UNIT_BASED_RESULTS_DIR / f"{scenario_name}_results"


def evaluation_root(scenario_name: str) -> Path:
    """Return the folder used for evaluation outputs."""
    return dataset_root(scenario_name) / "evaluation" / "price_comparison"


def create_evaluation_output_dir(
    scenario_name: str,
    power_flow_model: str,
    pricing_algorithms: tuple[PricingAlgorithms, ...],
) -> Path:
    """Create a timestamped output folder so evaluation results are not overwritten."""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    algorithm_part = "_".join(algorithm.name for algorithm in pricing_algorithms)
    output_dir = evaluation_root(scenario_name) / f"{timestamp}_{power_flow_model}_{algorithm_part}"
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def build_power_flow_model():
    """Build the power-flow model lazily to match the solve_unit_based_scenario signature."""
    return POWER_FLOW_MODEL.value


def run_dcopf_price_comparison(
    dataset: UnitBased_Datasets = DATASET,
    pricing_algorithms: tuple[PricingAlgorithms, ...] = PRICING_ALGORITHMS,
) -> tuple[pd.DataFrame, dict[str, dict[str, str]]]:
    """Reuse or compute DCOPF pricing runs, then collect their price tables."""
    scenario = _retrieve_data(dataset)
    scenario_name = scenario.name
    all_prices = []
    selected_runs: dict[str, dict[str, str]] = {}
    results_root = dataset_root(scenario_name)
    for pricing_algorithm in pricing_algorithms:
        run_dir, source = ensure_run_for_configuration(
            results_root=results_root,
            repo_root=ROOT,
            dataset=dataset,
            pricing_algorithm=pricing_algorithm,
            power_flow_model=build_power_flow_model(),
            power_flow_model_name=POWER_FLOW_MODEL_NAME,
        )
        all_prices.append(
            load_prices_from_run(
                run_dir,
                scenario_name,
                pricing_algorithm,
                power_flow_model_name=POWER_FLOW_MODEL_NAME,
            )
        )
        selected_runs[pricing_algorithm.name] = {
            "source": source,
            "run_dir": str(run_dir),
        }

    prices = pd.concat(all_prices, ignore_index=True)
    return prices[["dataset", "algorithm", "node", "period", "price"]], selected_runs


def pivot_prices_by_node_period(prices: pd.DataFrame) -> pd.DataFrame:
    """Reshape long-form prices to one row per dataset, node, and period."""
    grouped = (
        prices.pivot(
            index=["dataset", "node", "period"],
            columns="algorithm",
            values="price",
        )
        .reset_index()
        .rename_axis(columns=None)
    )

    ordered_columns = ["dataset", "node", "period"] + [
        algorithm.name for algorithm in PRICING_ALGORITHMS if algorithm.name in grouped.columns
    ]
    return grouped.loc[:, ordered_columns]


def main() -> None:
    prices, selected_runs = run_dcopf_price_comparison()
    scenario_name = prices["dataset"].iloc[0]
    dataset_output_dir = create_evaluation_output_dir(scenario_name, POWER_FLOW_MODEL_NAME, PRICING_ALGORITHMS)
    statistic_token = statistic_name(PLOT_STATISTIC_FN)
    period_plot_file = dataset_output_dir / f"{statistic_token}_prices_by_period.png"
    node_plot_file = dataset_output_dir / f"{statistic_token}_prices_by_node.png"
    period_boxplot_file = dataset_output_dir / f"{statistic_token}_prices_boxplot_by_period.png"
    node_boxplot_file = dataset_output_dir / f"{statistic_token}_prices_boxplot_by_node.png"

    grouped_prices = pivot_prices_by_node_period(prices)
    summary = round_numeric_columns(summarize_prices(prices, group_by=["algorithm"]))
    comparisons = round_numeric_columns(compare_price_algorithms(
        prices,
        align_on=["dataset", "node", "period"],
    ))
    algorithm_order = [algorithm.name for algorithm in PRICING_ALGORITHMS]
    plot_average_prices_by_period(
        prices,
        period_plot_file,
        algorithm_order=algorithm_order,
        statistic_fn=PLOT_STATISTIC_FN,
    )
    plot_average_prices_by_node(
        prices,
        node_plot_file,
        algorithm_order=algorithm_order,
        statistic_fn=PLOT_STATISTIC_FN,
    )
    plot_price_boxplot_by_period(
        prices,
        period_boxplot_file,
        algorithm_order=algorithm_order,
        statistic_fn=PLOT_STATISTIC_FN,
    )
    plot_price_boxplot_by_node(
        prices,
        node_boxplot_file,
        algorithm_order=algorithm_order,
        statistic_fn=PLOT_STATISTIC_FN,
    )

    grouped_prices.to_csv(dataset_output_dir / "prices.csv", index=False)
    summary.to_csv(dataset_output_dir / "summary_by_algorithm.csv", index=False)
    comparisons.to_csv(dataset_output_dir / "pairwise_comparisons.csv", index=False)
    metadata = {
        "dataset": DATASET.name,
        "scenario_name": scenario_name,
        "power_flow_model": POWER_FLOW_MODEL_NAME,
        "pricing_algorithms": [algorithm.name for algorithm in PRICING_ALGORITHMS],
        "prices_csv_layout": "grouped_by_dataset_node_period",
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


