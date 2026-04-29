# Price Analysis

## Purpose

Analyze and compare market prices for unit-based runs.

## Scripts

- [`scripts/unit_based_model/example_price_evaluation.py`](https://github.com/teodora-dobos/APEM/blob/main/scripts/unit_based_model/example_price_evaluation.py)
- [`scripts/unit_based_model/example_zonal_price_evaluation.py`](https://github.com/teodora-dobos/APEM/blob/main/scripts/unit_based_model/example_zonal_price_evaluation.py)

## Key Inputs

- Dataset selection (`DATASET`).
- Pricing selection (`PRICING_ALGORITHMS` or `PRICING_ALGORITHM`).
- Power-flow setup (`POWER_FLOW_MODEL`, `ZONAL_CONFIGURATION`, `NTC_FACTOR`, `FBMC_BASE_CASE`).
- Plot statistic (`PLOT_STATISTIC_FN`).

## Command Example

```bash
python scripts/unit_based_model/example_price_evaluation.py
```

## Outputs

- Price comparison tables and summaries.
- Pairwise comparisons and plots.
- Timestamped folders under `evaluation/price_comparison/` or `evaluation/zonal_price_comparison/`.
