"""
Example script for comparing real lost opportunity cost outputs from pricing algorithms.

The script:
1. parses one unit-based dataset,
2. reuses the latest matching run for each selected pricing algorithm, or computes it if missing,
3. loads the resulting lost opportunity cost values from each algorithm's `*_stats.txt`,
4. writes grouped lost opportunity cost tables and one plot per lost opportunity cost type.

You can adapt the evaluation by editing the constants near the top of the file:
- `DATASET`: choose the unit-based dataset to analyze.
- `POWER_FLOW_MODEL`: choose the power-flow model from `apem.unit_based_model.enums.PowerFlowModels`
  such as `PowerFlowModels.DCOPF`, `PowerFlowModels.Zonal_NTC_aggregated`,
  `PowerFlowModels.Zonal_NTC_multiedge`, or `PowerFlowModels.Zonal_FBMC`.
- `PRICING_ALGORITHMS`: choose the pricing algorithms to compare.

Each execution writes a new timestamped evaluation folder under:
`results/unit_based_model/<scenario>_results/evaluation/lost_opp_cost_comparison/`
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from apem.execution_chain import _retrieve_data
from apem.unit_based_model.enums import PowerFlowModels, PricingAlgorithms, UnitBased_Datasets
from apem.unit_based_model.evaluation import (
    ensure_lost_opp_cost_run_for_configuration,
    load_lost_opp_costs_from_run,
    plot_lost_opp_cost_by_component,
    round_numeric_columns,
)

UNIT_BASED_RESULTS_DIR = ROOT / "results" / "unit_based_model"

DATASET = UnitBased_Datasets.PyPSAEurLarge
POWER_FLOW_MODEL = PowerFlowModels.DCOPF
PRICING_ALGORITHMS = (
    PricingAlgorithms.IP,
    PricingAlgorithms.ELMP,
    PricingAlgorithms.Join,
)

POWER_FLOW_MODEL_NAME = str(POWER_FLOW_MODEL.value)


def dataset_root(scenario_name: str) -> Path:
    """Return the root results folder using the main pipeline naming convention."""
    return UNIT_BASED_RESULTS_DIR / f"{scenario_name}_results"


def evaluation_root(scenario_name: str) -> Path:
    """Return the folder used for lost opportunity cost evaluation outputs."""
    return dataset_root(scenario_name) / "evaluation" / "lost_opp_cost_comparison"


def create_evaluation_output_dir(
    scenario_name: str,
    power_flow_model: str,
    pricing_algorithms: tuple[PricingAlgorithms, ...],
) -> Path:
    """Create a timestamped output folder so lost opportunity cost evaluation results are not overwritten."""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    algorithm_part = "_".join(algorithm.name for algorithm in pricing_algorithms)
    output_dir = evaluation_root(scenario_name) / f"{timestamp}_{power_flow_model}_{algorithm_part}"
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def build_power_flow_model():
    """Build the power-flow model lazily to match the solve_unit_based_scenario signature."""
    return POWER_FLOW_MODEL.value


def run_lost_opp_cost_comparison(
    dataset: UnitBased_Datasets = DATASET,
    pricing_algorithms: tuple[PricingAlgorithms, ...] = PRICING_ALGORITHMS,
) -> tuple[pd.DataFrame, dict[str, dict[str, str]]]:
    """Reuse or compute pricing runs, then collect their lost opportunity cost tables."""
    scenario = _retrieve_data(dataset)
    scenario_name = scenario.name
    all_lost_opp_costs = []
    selected_runs: dict[str, dict[str, str]] = {}
    results_root = dataset_root(scenario_name)

    for pricing_algorithm in pricing_algorithms:
        run_dir, source = ensure_lost_opp_cost_run_for_configuration(
            results_root=results_root,
            repo_root=ROOT,
            dataset=dataset,
            pricing_algorithm=pricing_algorithm,
            power_flow_model=build_power_flow_model(),
            power_flow_model_name=POWER_FLOW_MODEL_NAME,
        )
        all_lost_opp_costs.append(
            load_lost_opp_costs_from_run(
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

    lost_opp_costs = pd.concat(all_lost_opp_costs, ignore_index=True)
    return lost_opp_costs[["dataset", "algorithm", "lost_opp_cost", "component", "value"]], selected_runs


def pivot_lost_opp_costs_by_component(lost_opp_costs: pd.DataFrame) -> pd.DataFrame:
    """Reshape long-form values to one row per dataset, lost_opp_cost, and component."""
    grouped = (
        lost_opp_costs.pivot(
            index=["dataset", "lost_opp_cost", "component"],
            columns="algorithm",
            values="value",
        )
        .reset_index()
        .rename_axis(columns=None)
    )

    ordered_columns = ["dataset", "lost_opp_cost", "component"] + [
        algorithm.name for algorithm in PRICING_ALGORITHMS if algorithm.name in grouped.columns
    ]
    return grouped.loc[:, ordered_columns]


def main() -> None:
    lost_opp_costs, selected_runs = run_lost_opp_cost_comparison()
    scenario_name = lost_opp_costs["dataset"].iloc[0]
    dataset_output_dir = create_evaluation_output_dir(scenario_name, POWER_FLOW_MODEL_NAME, PRICING_ALGORITHMS)

    grouped_lost_opp_costs = round_numeric_columns(pivot_lost_opp_costs_by_component(lost_opp_costs))
    algorithm_order = [algorithm.name for algorithm in PRICING_ALGORITHMS]
    plot_files: dict[str, str] = {}
    for lost_opp_cost_type in ("glocs", "llocs", "mwps"):
        plot_file = dataset_output_dir / f"{lost_opp_cost_type}_by_component.png"
        plot_lost_opp_cost_by_component(
            lost_opp_costs,
            plot_file,
            lost_opp_cost_type=lost_opp_cost_type,
            algorithm_order=algorithm_order,
        )
        plot_files[f"{lost_opp_cost_type}_plot"] = str(plot_file)

    grouped_lost_opp_costs.to_csv(dataset_output_dir / "lost_opp_costs.csv", index=False)
    metadata = {
        "dataset": DATASET.name,
        "scenario_name": scenario_name,
        "power_flow_model": POWER_FLOW_MODEL_NAME,
        "pricing_algorithms": [algorithm.name for algorithm in PRICING_ALGORITHMS],
        "lost_opp_costs_csv_layout": "grouped_by_dataset_lost_opp_cost_component",
        "selected_runs": selected_runs,
        "evaluation_root": str(dataset_output_dir),
        **plot_files,
    }
    with open(dataset_output_dir / "metadata.json", "w", encoding="utf-8") as handle:
        json.dump(metadata, handle, indent=2)


if __name__ == "__main__":
    main()


