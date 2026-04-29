from typing import TYPE_CHECKING

from gurobipy import GRB
import gurobipy as gp

if TYPE_CHECKING:
    from apem.order_book_based_model.euphemia.master_problem.master_problem import MasterProblem


def _log(self: "MasterProblem", message: str) -> None:
    if hasattr(self, "run_logger"):
        self.run_logger.info(message)
    elif hasattr(self, "_emit"):
        self._emit(message)


def add_no_good_cut(self: "MasterProblem", callback_model: gp.Model) -> None:
    """Post a generic no-good cut for the current master-problem incumbent.

    The cut inspects all binary master variables in the callback model and
    constructs an exclusion constraint requiring at least one of them to flip
    value in future incumbents.

    :param self: Active Euphemia master-problem instance.
    :param callback_model: Gurobi callback model used to post the lazy cut.
    :return: ``None``.
    """
    terms = []
    # match variable from current solution with Gurobi variable from model
    for gurobi_acceptance_var in callback_model.getVars():
        if gurobi_acceptance_var.VType == GRB.BINARY:
            solution_value = self.current_alloc_solution.get(gurobi_acceptance_var.VarName)
            if solution_value is None:
                _log(self, f"{gurobi_acceptance_var.VarName} not found in solution dict")
                continue
            if solution_value[0] > 0.5:
                terms.append(1 - gurobi_acceptance_var)
            else:
                terms.append(gurobi_acceptance_var)
    if terms:
        expr = gp.quicksum(terms)
        callback_model.cbLazy(expr >= 1)
        _log(self, f"Added no good cut: {expr} >= 1")
