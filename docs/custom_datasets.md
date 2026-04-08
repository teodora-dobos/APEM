# Using Your Own Datasets

APEM can work with your own data, but not by pointing `config.json` at an arbitrary file path.

The usual workflow is:

1. Put your dataset into the expected folder structure.
2. Register it in the relevant dataset enum.
3. Select that dataset name in [`config.json`](https://github.com/teodora-dobos/APEM/blob/main/config.json).

## Two Ways To Add Data

The setup depends on which market workflow you want to run.

- Use a **unit-based dataset** if your data describes generators, buyers, and a network.
- Use an **order-book dataset** if your data is already in Euphemia-style order tables.

If you start from unit-based data but want to run the order-book workflow, APEM also includes a converter.

## Option 1: Add A Unit-Based Dataset

For the unit-based workflow, APEM loads data through parser classes that return a `Scenario`.

### Step 1: Add your raw data

Place your files under:

```text
apem/unit_based_model/data/raw_data/<your_dataset_name>/
```

### Step 2: Create a parser

Add a parser class in `apem/unit_based_model/data/parsing/` that subclasses `ParseData` and returns a `Scenario`.

Your parser should construct:

- `df_sellers`
- `df_buyers`
- `network`
- `nodes_agents`
- `periods`
- `blocks_buyers`
- `blocks_sellers`
- `r_star`

The parser entry point is:

```python
from apem.unit_based_model.data.parsing.parse_data import ParseData

class ParseMyDataset(ParseData):
    def parse_data(self, day=None):
        ...
```

Useful references in the repo:

- [`apem/unit_based_model/data/parsing/parse_pjm.py`](https://github.com/teodora-dobos/APEM/blob/main/apem/unit_based_model/data/parsing/parse_pjm.py)
- [`apem/unit_based_model/data/parsing/parse_arpa.py`](https://github.com/teodora-dobos/APEM/blob/main/apem/unit_based_model/data/parsing/parse_arpa.py)

### Step 3: Register the dataset

Add your parser to [`apem/unit_based_model/enums/datasets.py`](https://github.com/teodora-dobos/APEM/blob/main/apem/unit_based_model/enums/datasets.py), following the existing pattern:

```python
class UnitBased_Datasets(Enum):
    ...
    MY_DATASET = ParseMyDataset()
```

### Step 4: Select it in `config.json`

```json
{
  "run": {
    "market_model": "unit_based_model"
  },
  "unit_based_model": {
    "dataset": "MY_DATASET",
    "power_flow_model": { "type": "DCOPF" },
    "pricing_algorithm": "ELMP"
  }
}
```

### Limitation

For a **new custom unit-based dataset**, the safe supported choice is `DCOPF`.

More precisely:

- your custom dataset can be used in the unit-based workflow with `DCOPF`
- your custom dataset cannot currently be used with the zonal power-flow models `Zonal_NTC_aggregated`, `Zonal_NTC_multiedge`, or `Zonal_FBMC`
- redispatch is part of those zonal workflows, so it is also not available for a new custom unit-based dataset

```{note}
At the moment, the zonal unit-based workflows are only supported for the two built-in PyPSA datasets: `PyPSAEurSmall` and `PyPSAEurLarge`.
```

#### What would be needed for zonal support on a new dataset?

To make a new unit-based dataset work with zonal models, it is not enough to only add a parser.

You would also need to:

- provide node coordinates so APEM can map nodes to zones
- define or extend the zonal mapping logic for your geography
- ensure the dataset contains the network information needed to aggregate a nodal network into a zonal one
- remove the current PyPSA-only restrictions in the zonal execution path
- test the full zonal workflow, including allocation, pricing, and redispatch

In other words, adding a new dataset for `DCOPF` is mostly a data-integration task, while adding a new dataset for zonal models also requires extending the current zonal-model implementation.

## Option 2: Add An Order-Book Dataset

For the order-book workflow, APEM expects a Euphemia-style dataset folder made of CSV files.

### Step 1: Add the dataset folder

Place your dataset under:

```text
apem/order_book_based_model/euphemia/data/datasets/<your_dataset_name>/
```

At minimum, this folder should contain the order and period tables expected by `ParseOrderBook`, including:

- `periods.csv`
- `step_orders.csv`
- `block_orders.csv`
- `complex_orders.csv`
- `complex_step_orders.csv`
- `scalable_complex_orders.csv`
- `scalable_step_orders.csv`
- `piecewise_linear_orders.csv`

Optional files such as `zones.csv`, `atc.csv`, `fb_constraints.csv`, and `fb_ptdf.csv` can be included depending on the network model.

The best small reference dataset is [`apem/order_book_based_model/euphemia/data/datasets/test_3node/`](https://github.com/teodora-dobos/APEM/tree/main/apem/order_book_based_model/euphemia/data/datasets/test_3node) in the repository.

### Step 2: Register the dataset

Add your dataset to [`apem/order_book_based_model/euphemia/enums/datasets.py`](https://github.com/teodora-dobos/APEM/blob/main/apem/order_book_based_model/euphemia/enums/datasets.py):

```python
MY_DATASET = ParseOrderBook(DATA_DIR / "my_dataset", "My Dataset")
```

### Step 3: Select it in `config.json`

```json
{
  "run": {
    "market_model": "order_book_based_model"
  },
  "order_book_based_model": {
    "dataset": "MY_DATASET",
    "cut_type": "price based",
    "euphemia_configuration": {
      "network_model": "FBMC"
    }
  }
}
```

## Summary

- `config.json` only selects datasets that APEM already knows about.
- To use your own data, you first register it in code.
- For unit-based data, you add a parser returning a `Scenario`.
- For order-book data, you add a dataset folder and register it with `ParseOrderBook`.
- If needed, you can convert unit-based data into the order-book format before running the order-book workflow.
