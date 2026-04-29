# Order-Book Workflows

Task-oriented entry points for order-book model experiments.

## Purpose

Compare Euphemia outcomes across cut types for one dataset and network setup.

## Scripts

- [`scripts/order_book_based_model/example_cut_type_comparison.py`](https://github.com/teodora-dobos/APEM/blob/main/scripts/order_book_based_model/example_cut_type_comparison.py)

## Key Inputs

- Dataset and network setup (`DATASET`, `NETWORK_MODEL`).
- Cut-type selection (`CUT_TYPES`).
- Euphemia override settings (`CONFIG_OVERRIDES`).
- Run reuse behavior (`REUSE_EXISTING_RUNS`).

## Command Example

```bash
python scripts/order_book_based_model/example_cut_type_comparison.py
```

Writes to `results/order_book_based_model/euphemia/<DATASET>/evaluation/cut_type_comparison/`.

## Outputs

- Cut-type summary table (`summary_by_cut_type.csv`).
- Final-price tables and pairwise price-difference reports.
- Comparison plots under the run `plots/` folder.
