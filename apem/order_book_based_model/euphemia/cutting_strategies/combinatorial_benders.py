from typing import TYPE_CHECKING

import gurobipy as gp

import apem.order_book_based_model.euphemia.cutting_strategies.no_good as no_good_cutting
from apem.order_book_based_model.euphemia.enums.order_types import OrderType
from apem.order_book_based_model.euphemia.pricing.price_determination_subproblem import PriceSubproblem

if TYPE_CHECKING:
    from apem.order_book_based_model.euphemia.master_problem.master_problem import MasterProblem


def _log(self: "MasterProblem", message: str) -> None:
    if hasattr(self, "run_logger"):
        self.run_logger.info(message)
    elif hasattr(self, "_emit"):
        self._emit(message)


def add_combinatorial_benders_cut(
    self: "MasterProblem",
    callback_model: gp.Model,
    price_subproblem: PriceSubproblem,
) -> None:
    """Post a combinatorial Benders cut derived from an infeasible price model.

    The routine computes an irreducible infeasible subset (IIS) of the pricing
    subproblem, maps IIS constraints back to master-problem acceptance
    variables, and posts a lazy cut that forces at least one implicated binary
    decision to change in future incumbents. If no master variables can be
    recovered from the IIS, it falls back to a no-good cut.

    :param self: Active Euphemia master-problem instance.
    :param callback_model: Gurobi callback model used to post the lazy cut.
    :param price_subproblem: Infeasible pricing model associated with the
        current incumbent allocation.
    :return: ``None``.
    """
    price_subproblem.pricing_model.computeIIS()
    terms = []
    for constr in price_subproblem.pricing_model.getConstrs():
        if constr.IISConstr:
            _log(self, f"Infeasible constraint: {constr}")
            constr_name = constr.ConstrName

            if constr_name in price_subproblem.constraint_meta_data.keys():
                metadata = price_subproblem.constraint_meta_data[constr_name]

                # Combinatorial Benders Cut
                if metadata[0] == OrderType.BLOCK:
                    terms.append(1 - self.MAR_aux[metadata[1]])
                elif metadata[0] == OrderType.COMPLEX:
                    terms.append(1 - self.accept_complex[metadata[1]])
                elif metadata[0] == OrderType.SCALABLE_COMPLEX:
                    terms.append(1 - self.accept_scalable[metadata[1]])

    if terms:
        callback_model.cbLazy(gp.quicksum(terms) >= 1)
        _log(self, f"Added combinatorial benders cut {gp.quicksum(terms)} >= 1")
    else:
        no_good_cutting.add_no_good_cut(self=self, callback_model=callback_model)
