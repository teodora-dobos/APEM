# APEM Node Ranking

The `node_ranking` package provides tools for ranking network nodes by structural importance and market relevance.

It combines:

- graph-based scores that describe how important a node is in the network topology
- market-based scores that use baseline dispatch and pricing outputs
- a DC economic-dispatch baseline that supplies the inputs required by several of those scores

```{toctree}
:maxdepth: 1
:hidden:

rank_nodes
network_scores
market_scores
economic_dispatch
```

## Scope

- Compute structural network scores (degree, betweenness, PTDF-based contributions).
- Compute market-informed node scores from baseline dispatch outputs.
- Solve baseline DC economic dispatch with optional generator-node interdictions.

## What This Module Is For

The node-ranking module is useful when you want to identify nodes that matter most under different definitions of "importance".

Depending on the metric, a high-ranked node may be:

- structurally central in the network
- strongly exposed to congestion or PTDF-driven flow impacts
- economically important because of dispatch, scarcity, or congestion rents

This makes the module useful for screening studies, vulnerability analysis, congestion analysis, and comparative scenario evaluation.

## Package Structure

The package is organized around a small wrapper layer for producing sorted rankings, a set of topology-based scoring functions, a set of market-based scoring functions, and a baseline dispatch model that provides the inputs required by several economic scores.

## Typical Workflow

1. Prepare the network, node, generator, and line inputs.
2. If needed, solve the baseline economic dispatch problem to obtain prices, dispatch, and congestion information.
3. If needed, compute PTDFs for the network representation.
4. Call the relevant ranking helper to obtain a sorted node ranking.
