from typing import Any, Dict, Optional

from apem.order_book_based_model.euphemia.enums.datasets import OrderBookBased_Datasets
from apem.order_book_based_model.euphemia.enums.cut_types import CutTypes
from apem.order_book_based_model.euphemia.euphemia_config import EuphemiaConfig
from apem.order_book_based_model.euphemia.master_problem.master_problem import MasterProblem


def solve_euphemia(
    dataset: OrderBookBased_Datasets,
    cut_type: CutTypes,
    config_overrides: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Solve a Euphemia scenario and return the run output directory.
    Constructs a ``EuphemiaConfig`` object, applies configuration overrides, 
    loads the selected dataset into a ``ZonalScenario``, and starts the ``MasterProblem`` solve loop.

    :param dataset: Order-book dataset to parse and solve.
    :param cut_type: Cutting strategy used by the master problem.
    :param config_overrides: Optional overrides applied to ``EuphemiaConfig``
        before the solve starts.
    :return: Absolute path to the created run directory.
    """
    config = EuphemiaConfig()
    config.apply_overrides(config_overrides or {})
    config.set_dataset(dataset)
    config.cutting_strategy = cut_type
    euphemia = MasterProblem(config)
    euphemia.run()
    return str(euphemia.run_root)
