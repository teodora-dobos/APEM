"""
Utility to run a full matrix of APEM order-book-based-model configurations.

Matrix:
- Datasets (OrderBookBased_Datasets):
  GENERATED_SMALL, GENERATED_LARGE, OMIE, GME,
  TEST_3NODE, TEST_3NODE_LOWCAP,
  IEEE_RTS, ARPA
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
from apem.core import MarketModels
from apem.unit_based_model.enums import PricingAlgorithms, RedispatchAlgorithms, UnitBased_Datasets
from apem.unit_based_model.allocation.algorithms.nodal_clearing.dcopf import DCOPF
from apem.order_book_based_model.euphemia.enums.cut_types import CutTypes
from apem.order_book_based_model.euphemia.enums.datasets import OrderBookBased_Datasets


def _ensure_matplotlib_dir() -> None:
    """Set MPLCONFIGDIR to a writable path if not already set (avoids font cache errors)."""
    if "MPLCONFIGDIR" not in os.environ:
        cache_dir = os.path.join(os.getcwd(), ".matplotlib_cache")
        os.makedirs(cache_dir, exist_ok=True)
        os.environ["MPLCONFIGDIR"] = cache_dir


def run_single(dataset: OrderBookBased_Datasets, cut_type: CutTypes) -> None:
    """Run one order-book-based-model configuration through solve_and_analyse_scenario."""
    _ensure_matplotlib_dir()
    solve_and_analyse_scenario(
        unit_based_dataset=UnitBased_Datasets.IEEE_RTS,  # unused for order-book-based-model runs
        order_book_based_dataset=dataset,
        market_model=MarketModels.order_book_based_model,
        power_flow_model=DCOPF(),  # unused for order-book-based-model runs
        cut_type=cut_type,
        pricing_algorithm=PricingAlgorithms.IP,  # unused for order-book-based-model runs
        redispatch_algorithm=RedispatchAlgorithms.MinCostRD,  # unused for order-book-based-model runs
        redispatch_constraint_units=False,  # unused for order-book-based-model runs
        redispatch_threshold=0.0,  # unused for order-book-based-model runs
        alpha=0.0,  # unused for order-book-based-model runs
    )


def _matrix() -> Iterable[Tuple[OrderBookBased_Datasets, CutTypes]]:
    """Return all dataset x cut-type combinations."""
    return [(dataset, cut_type) for dataset in OrderBookBased_Datasets for cut_type in CutTypes]


def main() -> None:
    _ensure_matplotlib_dir()
    runs: List[Tuple[OrderBookBased_Datasets, CutTypes]] = list(_matrix())
    successes = []
    failures = []

    for idx, (dataset, cut_type) in enumerate(runs, start=1):
        print(f"[{idx}/{len(runs)}] Running {dataset.name} with cut='{cut_type.value}'...")
        try:
            run_single(dataset, cut_type)
            successes.append((dataset, cut_type))
            print(f"[OK] Success: {dataset.name} | {cut_type.value}")
        except Exception as exc:  # noqa: BLE001
            traceback.print_exc()
            failures.append((dataset, cut_type, exc))
            print(f"[FAIL] Failed: {dataset.name} | {cut_type.value} | {exc}")

    print("\n=== Summary ===")
    print(f"Total runs: {len(runs)}")
    print(f"Successes: {len(successes)}")
    print(f"Failures: {len(failures)}")
    if failures:
        for dataset, cut_type, exc in failures:
            print(f"- {dataset.name} | {cut_type.value} -> {exc}")


if __name__ == "__main__":
    main()

