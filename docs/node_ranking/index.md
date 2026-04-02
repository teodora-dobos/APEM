# APEM Node Ranking

The `node_ranking` package provides graph-based and market-based node scoring
tools, plus a DC economic-dispatch baseline used by several ranking metrics.

```{toctree}
:maxdepth: 1

rank_nodes
graph_metrics
market_metrics
economic_dispatch
```

## Scope

- Compute structural graph scores (degree, betweenness, PTDF-based contributions).
- Compute market-informed node scores from baseline dispatch outputs.
- Solve baseline DC economic dispatch with optional generator-node interdictions.
