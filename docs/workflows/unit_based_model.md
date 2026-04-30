# Unit-Based Workflows

Task-oriented entry points for unit-based runs and evaluations.

## Prerequisites

- Run from the repository root.
- Use the project virtual environment.
- Ensure datasets referenced by each script are available.

## Workflow Map

- [Price Analysis](unit_based_model/price_analysis): compare pricing outcomes
  across pricing algorithms or zonal models.
- [Cost Analysis](unit_based_model/cost_analysis): compare welfare-derived costs
  and related metrics.
- [Redispatch Analysis](unit_based_model/redispatch_analysis): compare
  redispatch algorithms and redispatch costs.
- [Node Ranking](unit_based_model/node_ranking): compute graph-based and
  market-metric-based node rankings.

## Results Location

Most scripts write timestamped outputs under:

`results/unit_based_model/<scenario>_results/evaluation/`

```{toctree}
:maxdepth: 1
:hidden:

unit_based_model/price_analysis
unit_based_model/cost_analysis
unit_based_model/redispatch_analysis
unit_based_model/node_ranking
```
