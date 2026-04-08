# Order-Book-Based Model

The order-book-based model represents the market through submitted buy and sell
orders rather than explicit generator-unit identities. It is designed for
Euphemia-style day-ahead clearing studies where accepted order sets, price
feasibility, and decomposition behavior are central outputs.

This page is the documentation entry point for the order-book-based workflow.

```{toctree}
:maxdepth: 1
:hidden:

order_book_based_model/runner
order_book_based_model/euphemia_config
order_book_based_model/cutting_strategies
order_book_based_model/data_parsing
order_book_based_model/data_conversion
order_book_based_model/enums
order_book_based_model/master_problem
order_book_based_model/model
order_book_based_model/pricing
order_book_based_model/reinsertions
order_book_based_model/utilities
```

## Scope

- Euphemia-style order-book clearing workflow.
- Master problem and supporting model-building components.
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
- Direct section reference:
  {ref}`Two Main Modeling Workflows -> Order-Book-Based Model <main-order-book-based-model>`
