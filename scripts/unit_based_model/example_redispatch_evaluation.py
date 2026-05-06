"""
Example script for comparing redispatch algorithms for one dataset and power-flow model.

The script:
1. parses one unit-based dataset,
2. reuses the latest matching run for each selected redispatch algorithm, or computes it if missing,
3. loads redispatch costs and volumes from each run,
4. writes grouped redispatch tables and one plot per metric.

You can adapt the evaluation by editing the constants near the top of the file.
- `DATASET`: choose the unit-based dataset to analyze.
- `POWER_FLOW_MODEL`: choose the power-flow model used for all redispatch runs.
- `REDISPATCH_ALGORITHMS`: choose and order the redispatch algorithms to compare.
- `REDISPATCH_CONSTRAINT_UNITS`: decide whether redispatch is limited to selected units.
- `REDISPATCH_THRESHOLD`: choose the threshold used when unit constraints are enabled.

The script does not compute prices. Missing runs are generated through the
allocation-plus-redispatch path only.

Each execution writes a new timestamped evaluation folder under:
`results/unit_based_model/<scenario>_results/evaluation/redispatch_comparison/`
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
    load_redispatch_metrics_from_run,
    plot_redispatch_metric_by_algorithm,
    round_numeric_columns,
)

UNIT_BASED_RESULTS_DIR = ROOT / "results" / "unit_based_model"

DATASET = UnitBased_Datasets.PyPSAEurLarge
POWER_FLOW_MODEL = PowerFlowModels.Zonal_NTC_multiedge
REDISPATCH_ALGORITHMS = (
    RedispatchAlgorithms.MinCostRD,
    RedispatchAlgorithms.MinAbsCostRD,
    RedispatchAlgorithms.MinAbsVolRD,
)
REDISPATCH_CONSTRAINT_UNITS = False
REDISPATCH_THRESHOLD = 0

POWER_FLOW_MODEL_NAME = str(POWER_FLOW_MODEL.value)


def dataset_root(scenario_name: str) -> Path:
    return UNIT_BASED_RESULTS_DIR / f"{scenario_name}_results"


def evaluation_root(scenario_name: str) -> Path:
    return dataset_root(scenario_name) / "evaluation" / "redispatch_comparison"


def create_evaluation_output_dir(
    scenario_name: str,
    power_flow_model_name: str,
    redispatch_algorithms: tuple[RedispatchAlgorithms, ...],
) -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    algorithm_part = "_".join(algorithm.name for algorithm in redispatch_algorithms)
    output_dir = evaluation_root(scenario_name) / f"{timestamp}_{power_flow_model_name}_{algorithm_part}"
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def run_redispatch_comparison(
    dataset: UnitBased_Datasets = DATASET,
    redispatch_algorithms: tuple[RedispatchAlgorithms, ...] = REDISPATCH_ALGORITHMS,
) -> tuple[pd.DataFrame, dict[str, dict[str, str]]]:
    scenario = _retrieve_data(dataset)
    scenario_name = scenario.name
    all_metrics = []
    selected_runs: dict[str, dict[str, str]] = {}
    results_root = dataset_root(scenario_name)

    for redispatch_algorithm in redispatch_algorithms:
        run_dir, source = ensure_redispatch_run_for_configuration(
            results_root=results_root,
            repo_root=ROOT,
            dataset=dataset,
            power_flow_model=POWER_FLOW_MODEL.value,
            power_flow_model_name=POWER_FLOW_MODEL_NAME,
            redispatch_algorithm=redispatch_algorithm,
            redispatch_constraint_units=REDISPATCH_CONSTRAINT_UNITS,
            redispatch_threshold=REDISPATCH_THRESHOLD,
        )
        all_metrics.append(
            load_redispatch_metrics_from_run(
                run_dir,
                scenario_name,
                power_flow_model_name=POWER_FLOW_MODEL_NAME,
                redispatch_algorithm=redispatch_algorithm,
                redispatch_constraint_units=REDISPATCH_CONSTRAINT_UNITS,
                redispatch_threshold=REDISPATCH_THRESHOLD,
            )
        )
        selected_runs[redispatch_algorithm.name] = {
            "source": source,
            "run_dir": str(run_dir),
        }

    redispatch_metrics = pd.concat(all_metrics, ignore_index=True)
    return redispatch_metrics, selected_runs


def pivot_redispatch_metrics(redispatch_metrics: pd.DataFrame) -> pd.DataFrame:
    grouped = (
        redispatch_metrics.pivot(
            index=["dataset", "power_flow_model", "metric"],
            columns="redispatch_algorithm",
            values="value",
        )
        .reset_index()
        .rename_axis(columns=None)
    )

    ordered_columns = ["dataset", "power_flow_model", "metric"] + [
        algorithm.name for algorithm in REDISPATCH_ALGORITHMS if algorithm.name in grouped.columns
    ]
    return grouped.loc[:, ordered_columns]


def main() -> None:
    if POWER_FLOW_MODEL == PowerFlowModels.DCOPF:
        raise ValueError("Redispatch comparison requires a zonal power-flow model.")

    redispatch_metrics, selected_runs = run_redispatch_comparison()
    scenario_name = redispatch_metrics["dataset"].iloc[0]
    dataset_output_dir = create_evaluation_output_dir(
        scenario_name,
        POWER_FLOW_MODEL_NAME,
        REDISPATCH_ALGORITHMS,
    )

    grouped_metrics = round_numeric_columns(pivot_redispatch_metrics(redispatch_metrics))
    algorithm_order = [algorithm.name for algorithm in REDISPATCH_ALGORITHMS]
    plot_files: dict[str, str] = {}
    for metric in ("costs", "volumes"):
        plot_file = dataset_output_dir / f"redispatch_{metric}_by_algorithm.png"
        plot_redispatch_metric_by_algorithm(
            redispatch_metrics,
            plot_file,
            metric=metric,
            redispatch_algorithm_order=algorithm_order,
        )
        plot_files[f"{metric}_plot"] = str(plot_file)

    grouped_metrics.to_csv(dataset_output_dir / "redispatch_metrics.csv", index=False)
    metadata = {
        "dataset": DATASET.name,
        "scenario_name": scenario_name,
        "power_flow_model": POWER_FLOW_MODEL_NAME,
        "redispatch_algorithms": [algorithm.name for algorithm in REDISPATCH_ALGORITHMS],
        "redispatch_constraint_units": REDISPATCH_CONSTRAINT_UNITS,
        "redispatch_threshold": REDISPATCH_THRESHOLD,
        "redispatch_metrics_csv_layout": "grouped_by_dataset_power_flow_model_metric",
        "selected_runs": selected_runs,
        "evaluation_root": str(dataset_output_dir),
        **plot_files,
    }
    with open(dataset_output_dir / "metadata.json", "w", encoding="utf-8") as handle:
        json.dump(metadata, handle, indent=2)
    print(f"Outputs written to: {dataset_output_dir}")


if __name__ == "__main__":
    main()
