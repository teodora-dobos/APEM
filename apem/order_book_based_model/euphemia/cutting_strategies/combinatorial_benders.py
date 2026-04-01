import gurobipy as gp

import apem.order_book_based_model.euphemia.cutting_strategies.no_good as no_good_cutting
from apem.order_book_based_model.euphemia.enums.order_types import OrderType


def _log(self, message: str) -> None:
    if hasattr(self, "run_logger"):
        self.run_logger.info(message)
    elif hasattr(self, "_emit"):
        self._emit(message)


def add_combinatorial_benders_cut(self, callback_model, price_subproblem) -> None:
    """
    Add a combinatorial Benders cut to exclude the current solution from future consideration.
    Force at least one variable included in a constraint from an Irreducible Infeasible Subset (IIS) to change value.
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

