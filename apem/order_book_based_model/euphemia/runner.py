from typing import Any, Dict, Optional

from apem.order_book_based_model.euphemia.enums.datasets import OrderBookBased_Datasets
from apem.order_book_based_model.euphemia.enums.cut_types import CutTypes
from apem.order_book_based_model.euphemia.euphemia_config import EuphemiaConfig
from apem.order_book_based_model.euphemia.master_problem.master_problem import MasterProblem


def solve_euphemia(
    dataset: OrderBookBased_Datasets,
    cut_type: CutTypes,
    config_overrides: Optional[Dict[str, Any]] = None,
):
    """
    Solves an Euphemia scenario.
    Args:
        dataset (Datasets): Used dataset.
        cut_type (CutTypes): Cutting strategy to be used in the solver.

    Returns:

    """
    config = EuphemiaConfig()
    config.apply_overrides(config_overrides or {})
    config.set_dataset(dataset)
    config.cutting_strategy = cut_type
    euphemia = MasterProblem(config)
    euphemia.run()
    return str(euphemia.run_root)

