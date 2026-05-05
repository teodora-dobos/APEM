"""
Example script for combining total costs and redispatch costs across power-flow models.

The script:
1. parses one unit-based dataset,
2. reuses the latest matching run for each selected power-flow model, or computes it if missing,
3. loads total welfare and redispatch costs for one selected redispatch algorithm,
4. converts welfare to cost via `abs(total_welfare)`,
5. adds cost and redispatch costs for each power-flow model,
6. writes a grouped comparison table and a plot.

You can adapt the evaluation by editing the constants near the top of the file.
- `DATASET`: choose the unit-based dataset to analyze.
- `POWER_FLOW_MODELS`: choose and order the power-flow models to compare.
- `REDISPATCH_ALGORITHM`: choose the redispatch algorithm used for zonal runs.
- `REDISPATCH_CONSTRAINT_UNITS`: decide whether redispatch is limited to selected units.
- `REDISPATCH_THRESHOLD`: choose the threshold used when unit constraints are enabled.

For `DCOPF`, redispatch costs are set to `0` because there is no redispatch stage.

In this script, `cost = abs(total_welfare)` is used only under the assumption that
there is no elastic demand. The PyPSA datasets in this repository are examples
where this assumption applies, so interpreting cost as the absolute value of
welfare is appropriate for them.

Each execution writes a new timestamped evaluation folder under:
`results/unit_based_model/<scenario>_results/evaluation/cost_plus_redispatch_cost_comparison/`
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
from apem.unit_based_model.enums import (
    PowerFlowModels,
    RedispatchAlgorithms,
    UnitBased_Datasets,
)
from apem.unit_based_model.evaluation import (
    ensure_redispatch_run_for_configuration,
    ensure_welfare_run_for_configuration,
    load_redispatch_metrics_from_run,
    load_welfare_from_run,
    plot_value_by_power_flow_model,
    round_numeric_columns,
)

UNIT_BASED_RESULTS_DIR = ROOT / "results" / "unit_based_model"

DATASET = UnitBased_Datasets.PyPSAEurLarge
POWER_FLOW_MODELS = (
    PowerFlowModels.DCOPF,
    PowerFlowModels.Zonal_NTC_aggregated,
    PowerFlowModels.Zonal_NTC_multiedge,
    PowerFlowModels.Zonal_FBMC,
)
REDISPATCH_ALGORITHM = RedispatchAlgorithms.MinCostRD
REDISPATCH_CONSTRAINT_UNITS = False
REDISPATCH_THRESHOLD = 0


def dataset_root(scenario_name: str) -> Path:
    return UNIT_BASED_RESULTS_DIR / f"{scenario_name}_results"


def evaluation_root(scenario_name: str) -> Path:
    return dataset_root(scenario_name) / "evaluation" / "cost_plus_redispatch_cost_comparison"


def create_evaluation_output_dir(
    scenario_name: str,
    redispatch_algorithm: RedispatchAlgorithms,
    power_flow_models: tuple[PowerFlowModels, ...],
) -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    model_part = "_".join(model.name for model in power_flow_models)
    output_dir = evaluation_root(scenario_name) / f"{timestamp}_{redispatch_algorithm.name}_{model_part}"
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def run_cost_plus_redispatch_cost_comparison(
    dataset: UnitBased_Datasets = DATASET,
    power_flow_models: tuple[PowerFlowModels, ...] = POWER_FLOW_MODELS,
) -> tuple[pd.DataFrame, dict[str, dict[str, str]]]:
    scenario = _retrieve_data(dataset)
    scenario_name = scenario.name
    records: list[dict[str, object]] = []
    selected_runs: dict[str, dict[str, str]] = {}
    results_root = dataset_root(scenario_name)

    for power_flow_model in power_flow_models:
        power_flow_model_name = str(power_flow_model.value)

        if power_flow_model == PowerFlowModels.DCOPF:
            run_dir, source = ensure_welfare_run_for_configuration(
                results_root=results_root,
                repo_root=ROOT,
                dataset=dataset,
                power_flow_model=power_flow_model.value,
                power_flow_model_name=power_flow_model_name,
            )
            welfare = load_welfare_from_run(
                run_dir,
                scenario_name,
                power_flow_model_name=power_flow_model_name,
            )
            redispatch_costs = 0.0
        else:
            run_dir, source = ensure_redispatch_run_for_configuration(
                results_root=results_root,
                repo_root=ROOT,
                dataset=dataset,
                power_flow_model=power_flow_model.value,
                power_flow_model_name=power_flow_model_name,
                redispatch_algorithm=REDISPATCH_ALGORITHM,
                redispatch_constraint_units=REDISPATCH_CONSTRAINT_UNITS,
                redispatch_threshold=REDISPATCH_THRESHOLD,
            )
            welfare = load_welfare_from_run(
                run_dir,
                scenario_name,
                power_flow_model_name=power_flow_model_name,
            )
            redispatch_metrics = load_redispatch_metrics_from_run(
                run_dir,
                scenario_name,
                power_flow_model_name=power_flow_model_name,
                redispatch_algorithm=REDISPATCH_ALGORITHM,
                redispatch_constraint_units=REDISPATCH_CONSTRAINT_UNITS,
                redispatch_threshold=REDISPATCH_THRESHOLD,
            )
            redispatch_costs = float(
                redispatch_metrics.loc[redispatch_metrics["metric"] == "costs", "value"].iloc[0]
            )

        total_welfare = float(welfare.loc[welfare["welfare_scope"] == "total", "welfare"].iloc[0])
        total_cost = abs(total_welfare)
        records.append(
            {
                "dataset": scenario_name,
                "power_flow_model": power_flow_model_name,
                "total_cost": total_cost,
                "redispatch_costs": redispatch_costs,
                "cost_plus_redispatch_costs": total_cost + redispatch_costs,
            }
        )
        selected_runs[power_flow_model.name] = {
            "source": source,
            "run_dir": str(run_dir),
        }

    return pd.DataFrame(records), selected_runs


def main() -> None:
    comparison, selected_runs = run_cost_plus_redispatch_cost_comparison()
    scenario_name = comparison["dataset"].iloc[0]
    dataset_output_dir = create_evaluation_output_dir(
        scenario_name,
        REDISPATCH_ALGORITHM,
        POWER_FLOW_MODELS,
    )

    comparison = round_numeric_columns(comparison)
    power_flow_model_order = [str(model.value) for model in POWER_FLOW_MODELS]
    plot_file = dataset_output_dir / "cost_plus_redispatch_costs_by_power_flow_model.png"
    plot_value_by_power_flow_model(
        comparison,
        plot_file,
        value_column="cost_plus_redispatch_costs",
        ylabel="Cost + Redispatch Costs",
        title="Cost + Redispatch Costs by Power-Flow Model",
        power_flow_model_order=power_flow_model_order,
    )

    comparison.to_csv(dataset_output_dir / "cost_plus_redispatch_costs.csv", index=False)
    metadata = {
        "dataset": DATASET.name,
        "scenario_name": scenario_name,
        "power_flow_models": [model.name for model in POWER_FLOW_MODELS],
        "power_flow_model_names": [str(model.value) for model in POWER_FLOW_MODELS],
        "redispatch_algorithm": REDISPATCH_ALGORITHM.name,
        "redispatch_constraint_units": REDISPATCH_CONSTRAINT_UNITS,
        "redispatch_threshold": REDISPATCH_THRESHOLD,
        "cost_definition": "absolute_value_of_total_welfare",
        "comparison_csv_layout": "one_row_per_power_flow_model",
        "combined_value_plot": str(plot_file),
        "selected_runs": selected_runs,
        "evaluation_root": str(dataset_output_dir),
    }
    with open(dataset_output_dir / "metadata.json", "w", encoding="utf-8") as handle:
        json.dump(metadata, handle, indent=2)
    print(f"Outputs written to: {dataset_output_dir}")


if __name__ == "__main__":
    main()
