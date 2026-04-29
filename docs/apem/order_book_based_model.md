# Order-Book-Based Model

The order-book-based model represents the market through submitted buy and sell
orders rather than explicit generator-unit identities. In APEM, this workflow is
implemented by the `apem.order_book_based_model.euphemia` package and is designed
for Euphemia-style day-ahead clearing studies where accepted order sets, price
feasibility, and decomposition behavior are central outputs.

This page is the documentation entry point for the order-book-based Euphemia
workflow, including its public solver entrypoint and the main supporting
components.

## What This Module Covers

- Euphemia-style order-book clearing workflow.
- Public runner entrypoint for executing Euphemia scenarios.
- Solver core covering orchestration and model formulation.
- Cut strategy, pricing, and reinsertion routines.
- Dataset parsing and conversion for order-book inputs.

## Typical Execution Flow

1. Parse and normalize order-book and network input files.
2. Build the Euphemia-style optimization model and constraints.
3. Solve the master problem with configured cut/reinsertion strategy.
4. Run pricing and feasibility checks on accepted orders.
5. Export accepted orders, prices, and diagnostics for analysis.

## See Also

- Main APEM framework overview and conceptual description of this workflow:
  [APEM: Allocation and Pricing in Electricity Markets](../index.md)
- Module-level implementation overview:
  `apem.order_book_based_model.euphemia`
- Direct section reference:
  {ref}`Two Main Modeling Workflows -> Order-Book-Based Model <main-order-book-based-model>`

```{toctree}
:maxdepth: 1
:hidden:

order_book_based_model/data_parsing
order_book_based_model/solver_core
order_book_based_model/pricing
order_book_based_model/cutting_strategies
order_book_based_model/reinsertions
```

## Support APIs

### Euphemia Configuration

API path: `apem.order_book_based_model.euphemia.euphemia_config`

```{eval-rst}
.. automodule:: apem.order_book_based_model.euphemia.euphemia_config
   :members:
   :show-inheritance:
```

### Runner

API path: `apem.order_book_based_model.euphemia.runner`

```{eval-rst}
.. automodule:: apem.order_book_based_model.euphemia.runner
   :members:
   :show-inheritance:
```

### Enums

Enum definitions used in Euphemia configuration and solver flow.

#### Cut Types

API path: `apem.order_book_based_model.euphemia.enums.cut_types`

```{eval-rst}
.. automodule:: apem.order_book_based_model.euphemia.enums.cut_types
   :members:
   :show-inheritance:
```

#### Datasets

API path: `apem.order_book_based_model.euphemia.enums.datasets`

```{eval-rst}
.. automodule:: apem.order_book_based_model.euphemia.enums.datasets
   :members:
   :show-inheritance:
```

#### Order Types

API path: `apem.order_book_based_model.euphemia.enums.order_types`

```{eval-rst}
.. automodule:: apem.order_book_based_model.euphemia.enums.order_types
   :members:
   :show-inheritance:
```
