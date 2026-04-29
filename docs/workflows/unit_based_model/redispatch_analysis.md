# Redispatch Analysis

## Purpose

Compare redispatch algorithms and redispatch costs in zonal workflows.

## Scripts

- [`scripts/unit_based_model/example_redispatch_evaluation.py`](https://github.com/teodora-dobos/APEM/blob/main/scripts/unit_based_model/example_redispatch_evaluation.py)
- [`scripts/unit_based_model/example_redispatch_cost_evaluation.py`](https://github.com/teodora-dobos/APEM/blob/main/scripts/unit_based_model/example_redispatch_cost_evaluation.py)

## Key Inputs

- Dataset and model selections (`DATASET`, `POWER_FLOW_MODEL` or `POWER_FLOW_MODELS`).
- Redispatch setup (`REDISPATCH_ALGORITHMS` or `REDISPATCH_ALGORITHM`).
- Constraint controls (`REDISPATCH_CONSTRAINT_UNITS`, `REDISPATCH_THRESHOLD`).

## Command Example

```bash
python scripts/unit_based_model/example_redispatch_evaluation.py
```

## Outputs

- Redispatch metric tables (costs/volumes) and plots.
- Timestamped folders under:
  - `evaluation/redispatch_comparison/`
  - `evaluation/redispatch_cost_comparison/`
