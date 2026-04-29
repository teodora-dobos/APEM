# Cost Analysis

## Purpose

Compare welfare-derived costs and related cost metrics across models/algorithms.

## Scripts

- [`scripts/unit_based_model/example_cost_evaluation.py`](https://github.com/teodora-dobos/APEM/blob/main/scripts/unit_based_model/example_cost_evaluation.py)
- [`scripts/unit_based_model/example_cost_plus_redispatch_cost_evaluation.py`](https://github.com/teodora-dobos/APEM/blob/main/scripts/unit_based_model/example_cost_plus_redispatch_cost_evaluation.py)
- [`scripts/unit_based_model/example_lost_opp_cost_evaluation.py`](https://github.com/teodora-dobos/APEM/blob/main/scripts/unit_based_model/example_lost_opp_cost_evaluation.py)

## Key Inputs

- Dataset and model selections (`DATASET`, `POWER_FLOW_MODELS`, `POWER_FLOW_MODEL`).
- Redispatch settings when relevant (`REDISPATCH_ALGORITHM`, `REDISPATCH_CONSTRAINT_UNITS`, `REDISPATCH_THRESHOLD`).
- Pricing algorithm selections for lost opportunity cost analysis (`PRICING_ALGORITHMS`).

## Command Example

```bash
python scripts/unit_based_model/example_cost_evaluation.py
```

## Outputs

- Grouped cost and lost opportunity cost tables.
- Comparison plots.
- Timestamped folders under:
  - `evaluation/cost_comparison/`
  - `evaluation/cost_plus_redispatch_cost_comparison/`
  - `evaluation/lost_opp_cost_comparison/`
