"""
Example script for comparing costs across power-flow models for one dataset.

The script:
1. parses one US dataset,
2. reuses the latest matching run for each selected power-flow model, or computes it if missing,
3. loads welfare values from each model's allocation stats file,
4. converts welfare to cost via `abs(welfare)`,
5. writes grouped cost tables and comparison plots.

The pricing algorithm is not part of the comparison itself. `RUN_PRICING_ALGORITHM`
is only used when the script needs to compute a missing run.

In this script, `cost = abs(welfare)` is used only under the assumption that there
is no elastic demand. The PyPSA datasets in this repository are examples where
this assumption applies, so interpreting cost as the absolute value of welfare is
appropriate for them.

Each execution writes a new timestamped evaluation folder under:
`US_results/<scenario>_results/evaluation/cost_comparison/`
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys

if "MPLCONFIGDIR" not in os.environ:
    os.environ["MPLCONFIGDIR"] = str(Path(__file__).resolve().parents[2] / ".matplotlib_cache")

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from apem.execution_chain import _retrieve_data
from apem.US_market_model.enums import PowerFlowModels, PricingAlgorithms, US_Datasets
from apem.US_market_model.evaluation import (
    ensure_welfare_run_for_configuration,
    load_welfare_from_run,
    plot_value_by_period_and_power_flow_model,
    plot_value_by_power_flow_model,
    round_numeric_columns,
)

US_RESULTS_DIR = ROOT / "US_results"

DATASET = US_Datasets.PyPSAEurLarge
POWER_FLOW_MODELS = (
    PowerFlowModels.DCOPF,
    PowerFlowModels.Zonal_NTC_aggregated,
    PowerFlowModels.Zonal_NTC_multiedge,
    PowerFlowModels.ZonalFBMC,
)
RUN_PRICING_ALGORITHM = PricingAlgorithms.IP


def dataset_root(scenario_name: str) -> Path:
    return US_RESULTS_DIR / f"{scenario_name}_results"


def evaluation_root(scenario_name: str) -> Path:
    return dataset_root(scenario_name) / "evaluation" / "cost_comparison"


def create_evaluation_output_dir(
    scenario_name: str,
    power_flow_models: tuple[PowerFlowModels, ...],
) -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    model_part = "_".join(model.name for model in power_flow_models)
    output_dir = evaluation_root(scenario_name) / f"{timestamp}_{model_part}"
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def run_cost_comparison(
    dataset: US_Datasets = DATASET,
    power_flow_models: tuple[PowerFlowModels, ...] = POWER_FLOW_MODELS,
) -> tuple[pd.DataFrame, dict[str, dict[str, str]]]:
    scenario = _retrieve_data(dataset)
    scenario_name = scenario.name
    all_welfare = []
    selected_runs: dict[str, dict[str, str]] = {}
    results_root = dataset_root(scenario_name)

    for power_flow_model in power_flow_models:
        power_flow_model_name = str(power_flow_model.value)
        run_dir, source = ensure_welfare_run_for_configuration(
            results_root=results_root,
            repo_root=ROOT,
            dataset=dataset,
            power_flow_model=power_flow_model.value,
            power_flow_model_name=power_flow_model_name,
            pricing_algorithm=RUN_PRICING_ALGORITHM,
        )
        all_welfare.append(
            load_welfare_from_run(
                run_dir,
                scenario_name,
                power_flow_model_name=power_flow_model_name,
            )
        )
        selected_runs[power_flow_model.name] = {
            "source": source,
            "run_dir": str(run_dir),
        }

    welfare = pd.concat(all_welfare, ignore_index=True)
    welfare["cost"] = welfare["welfare"].abs()
    return welfare[["dataset", "power_flow_model", "welfare_scope", "period", "cost"]], selected_runs


def pivot_period_cost_by_model(cost_table: pd.DataFrame) -> pd.DataFrame:
    period_cost = cost_table.loc[cost_table["welfare_scope"] == "period"].copy()
    grouped = (
        period_cost.pivot(
            index=["dataset", "period"],
            columns="power_flow_model",
            values="cost",
        )
        .reset_index()
        .rename_axis(columns=None)
    )

    ordered_columns = ["dataset", "period"] + [
        str(model.value) for model in POWER_FLOW_MODELS if str(model.value) in grouped.columns
    ]
    return grouped.loc[:, ordered_columns]


def pivot_total_cost_by_model(cost_table: pd.DataFrame) -> pd.DataFrame:
    total_cost = cost_table.loc[cost_table["welfare_scope"] == "total"].copy()
    grouped = (
        total_cost.pivot(
            index=["dataset"],
            columns="power_flow_model",
            values="cost",
        )
        .reset_index()
        .rename_axis(columns=None)
    )

    ordered_columns = ["dataset"] + [
        str(model.value) for model in POWER_FLOW_MODELS if str(model.value) in grouped.columns
    ]
    return grouped.loc[:, ordered_columns]


def main() -> None:
    cost_table, selected_runs = run_cost_comparison()
    scenario_name = cost_table["dataset"].iloc[0]
    dataset_output_dir = create_evaluation_output_dir(scenario_name, POWER_FLOW_MODELS)

    period_cost = round_numeric_columns(pivot_period_cost_by_model(cost_table))
    total_cost = round_numeric_columns(pivot_total_cost_by_model(cost_table))
    power_flow_model_order = [str(model.value) for model in POWER_FLOW_MODELS]
    period_plot_file = dataset_output_dir / "cost_by_period.png"
    total_plot_file = dataset_output_dir / "total_cost_by_power_flow_model.png"

    plot_value_by_period_and_power_flow_model(
        cost_table.loc[cost_table["welfare_scope"] == "period", ["period", "power_flow_model", "cost"]],
        period_plot_file,
        period_column="period",
        model_column="power_flow_model",
        value_column="cost",
        ylabel="Cost",
        title="Cost by Period and Power-Flow Model",
        power_flow_model_order=power_flow_model_order,
    )
    plot_value_by_power_flow_model(
        cost_table.loc[cost_table["welfare_scope"] == "total", ["power_flow_model", "cost"]],
        total_plot_file,
        value_column="cost",
        ylabel="Total Cost",
        title="Total Cost by Power-Flow Model",
        power_flow_model_order=power_flow_model_order,
    )

    period_cost.to_csv(dataset_output_dir / "period_cost.csv", index=False)
    total_cost.to_csv(dataset_output_dir / "total_cost.csv", index=False)
    metadata = {
        "dataset": DATASET.name,
        "scenario_name": scenario_name,
        "power_flow_models": [model.name for model in POWER_FLOW_MODELS],
        "power_flow_model_names": [str(model.value) for model in POWER_FLOW_MODELS],
        "run_pricing_algorithm": RUN_PRICING_ALGORITHM.name,
        "cost_definition": "absolute_value_of_welfare",
        "period_cost_csv_layout": "grouped_by_dataset_period_power_flow_model",
        "total_cost_csv_layout": "grouped_by_dataset_power_flow_model",
        "cost_by_period_plot": str(period_plot_file),
        "total_cost_plot": str(total_plot_file),
        "selected_runs": selected_runs,
        "evaluation_root": str(dataset_output_dir),
    }
    with open(dataset_output_dir / "metadata.json", "w", encoding="utf-8") as handle:
        json.dump(metadata, handle, indent=2)


if __name__ == "__main__":
    main()
