# Node Ranking

## Purpose

Rank nodes using graph-topology metrics and market-metric signals.

## Scripts

- [`scripts/unit_based_model/example_graph_node_rankings.py`](https://github.com/teodora-dobos/APEM/blob/main/scripts/unit_based_model/example_graph_node_rankings.py)
- [`scripts/unit_based_model/example_market_node_rankings.py`](https://github.com/teodora-dobos/APEM/blob/main/scripts/unit_based_model/example_market_node_rankings.py)

## Key Inputs

- Dataset selection (`DATASET`).
- PTDF setup (`SLACK_NODE`, `PTDF_METHODS` where applicable).
- Display controls (`TOP_K_PRINT`, `TOP_K_PLOT`).
- Market-metric settings (`PERIOD`, `VOLL` for market ranking script).

## Command Example

```bash
python scripts/unit_based_model/example_graph_node_rankings.py
```

## Outputs

- Ranking CSV files.
- Top-k node plots.
- Metadata files in timestamped evaluation folders under node-ranking result paths.
