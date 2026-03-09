"""
Utility to run a full matrix of APEM EU_model configurations.

Matrix:
- Datasets (EU_Datasets):
  GENERATED_SMALL, GENERATED_LARGE, OMIE, GME, IEEE_RTS, ARPA, PyPSAEurSmall, PyPSAEurLarge, PJM
- Cut types (CutTypes):
  "price based", "combinatorial benders", "no good"

The script executes every dataset x cut-type combination and reports successes/failures.
"""

import os
import sys
import traceback
from pathlib import Path
from typing import Iterable, List, Tuple

# Ensure repo root is on sys.path when run directly
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from apem.execution_chain import solve_and_analyse_scenario
from apem.enums import MarketModels, PricingAlgorithms, RedispatchAlgorithms, US_Datasets
from apem.US_market_model.allocation.algorithms.nodal_clearing.dcopf import DCOPF
from apem.EU_market_model.euphemia.enums.cut_types import CutTypes
from apem.EU_market_model.euphemia.enums.datasets import EU_Datasets


def _ensure_matplotlib_dir() -> None:
    """Set MPLCONFIGDIR to a writable path if not already set (avoids font cache errors)."""
    if "MPLCONFIGDIR" not in os.environ:
        cache_dir = os.path.join(os.getcwd(), ".matplotlib_cache")
        os.makedirs(cache_dir, exist_ok=True)
        os.environ["MPLCONFIGDIR"] = cache_dir


def run_single(dataset: EU_Datasets, cut_type: CutTypes) -> None:
    """Run one EU_model configuration through solve_and_analyse_scenario."""
    _ensure_matplotlib_dir()
    solve_and_analyse_scenario(
        US_dataset=US_Datasets.IEEE_RTS,  # unused for EU_model but required by signature
        EU_dataset=dataset,
        market_model=MarketModels.EU_model,
        power_flow_model=DCOPF(),  # unused for EU_model but required by signature
        cut_type=cut_type,
        pricing_algorithm=PricingAlgorithms.IP,  # unused for EU_model
        redispatch_algorithm=RedispatchAlgorithms.MinCostRD,  # unused for EU_model
        redispatch_constraint_units=False,  # unused for EU_model
        redispatch_threshold=0.0,  # unused for EU_model
        alpha=0.0,  # unused for EU_model
    )


def _matrix() -> Iterable[Tuple[EU_Datasets, CutTypes]]:
    """Return all dataset x cut-type combinations."""
    return [(dataset, cut_type) for dataset in EU_Datasets for cut_type in CutTypes]


def main() -> None:
    _ensure_matplotlib_dir()
    runs: List[Tuple[EU_Datasets, CutTypes]] = list(_matrix())
    successes = []
    failures = []

    for idx, (dataset, cut_type) in enumerate(runs, start=1):
        print(f"[{idx}/{len(runs)}] Running {dataset.name} with cut='{cut_type.value}'...")
        try:
            run_single(dataset, cut_type)
            successes.append((dataset, cut_type))
            print(f"✔ Success: {dataset.name} | {cut_type.value}")
        except Exception as exc:  # noqa: BLE001
            traceback.print_exc()
            failures.append((dataset, cut_type, exc))
            print(f"✖ Failed: {dataset.name} | {cut_type.value} | {exc}")

    print("\n=== Summary ===")
    print(f"Total runs: {len(runs)}")
    print(f"Successes: {len(successes)}")
    print(f"Failures: {len(failures)}")
    if failures:
        for dataset, cut_type, exc in failures:
            print(f"- {dataset.name} | {cut_type.value} -> {exc}")


if __name__ == "__main__":
    main()
