"""Master-problem package exports.

This package re-exports :class:`MasterProblem` from the canonical implementation
module so the codebase has a single source of truth.
"""

from apem.order_book_based_model.euphemia.master_problem.master_problem import MasterProblem

__all__ = ["MasterProblem"]
