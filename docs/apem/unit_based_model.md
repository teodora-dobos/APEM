# Unit-Based Model

The unit-based model represents the market at the level of individual generating
units and demand blocks. It combines operational constraints, network
constraints, and pricing algorithms to study how market design choices affect
dispatch, prices, welfare, and redispatch outcomes.

This page is the API entry point for `apem.unit_based_model`.

## What This Module Covers

- **Allocation**: market-clearing formulations (nodal and zonal), including
  redispatch extensions.
- **Data**: scenario loading/parsing and model-ready data structures.
- **Pricing**: post-allocation pricing algorithms (for example `ELMP`, `IP`,
  `Join`, `Markup`, `Min-MWP`).
- **Evaluation**: post-run analysis of prices, welfare, redispatch, and lost
  opportunity costs.

## Typical Execution Flow

1. Parse or load a dataset into a `Scenario`.
2. Choose allocation settings (power-flow model, redispatch, solver config).
3. Solve allocation/dispatch.
4. Run a pricing algorithm on the solved allocation.
5. Evaluate outputs across runs and configurations.

## See Also

- Main APEM framework overview and conceptual description of this workflow:
  [APEM: Allocation and Pricing in Electricity Markets](../index.md)
- Direct section reference:
  {ref}`Two Main Modeling Workflows -> Unit-Based Model <main-unit-based-model>`

```{toctree}
:maxdepth: 1
:hidden:

unit_based_model/allocation
unit_based_model/data
unit_based_model/evaluation
unit_based_model/pricing
```
