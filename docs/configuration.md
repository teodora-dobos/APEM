# Configuration

APEM is configured through a single file at the repository root: [`config.json`](https://github.com/teodora-dobos/APEM/blob/main/config.json).

If you are new to the project, the most important thing to understand is this:

- you do **not** create a separate config per run,
- you edit `config.json`,
- then you run APEM,
- and APEM reads the settings from that file.

## How `config.json` Is Used

`config.json` is the runtime input for `main.py`.

1. Open [`config.json`](https://github.com/teodora-dobos/APEM/blob/main/config.json).
2. Set `run.market_model`.
3. Edit the corresponding model section.
4. Run:

```bash
python main.py
```

APEM loads the file, validates it, and executes the selected workflow.

## Basic Structure

`config.json` is model-scoped and has three main sections:

- `run`: global run selection
- `unit_based_model`: used when `run.market_model = "unit_based_model"`
- `order_book_based_model`: used when `run.market_model = "order_book_based_model"`

```text
config.json
├── run
├── unit_based_model
└── order_book_based_model
```

## Minimal Example

```json
{
  "run": {
    "market_model": "unit_based_model",
    "verbosity": true
  },
  "unit_based_model": {
    "dataset": "PyPSAEurLarge",
    "power_flow_model": { "type": "DCOPF" },
    "pricing_algorithm": "ELMP",
    "solver_configuration": {
      "time_limit": 3600,
      "slack_penalty": 1e15
    }
  },
  "order_book_based_model": {
    "dataset": "TEST_3NODE",
    "cut_type": "price based",
    "euphemia_configuration": {
      "network_model": "FBMC",
      "max_iterations": 50
    }
  }
}
```

This example runs the unit-based workflow because `run.market_model` is `unit_based_model`.

## What To Edit First

::::{tab-set}
:::{tab-item} Global (`run`)
| field | required | purpose | typical values |
|---|---|---|---|
| `run.market_model` | yes | Select active workflow. | `unit_based_model`, `order_book_based_model` |
| `run.verbosity` | recommended | Control console output level. | `true`, `false` |
:::

:::{tab-item} Unit-Based
If `run.market_model = "unit_based_model"`, edit these first:

| field | required | purpose | examples |
|---|---|---|---|
| `unit_based_model.dataset` | yes | Choose input dataset. | `PyPSAEurLarge`, `PJM` |
| `unit_based_model.power_flow_model.type` | yes | Choose nodal vs zonal power-flow model. | `DCOPF`, `Zonal_NTC_aggregated` |
| `unit_based_model.pricing_algorithm` | yes | Choose pricing method. | `ELMP`, `IP` |
| `unit_based_model.solver_configuration` | recommended | Runtime, tolerance, and solver behavior. | `time_limit`, `MIP_gap`, `threads` |

For zonal runs, also configure:

- `unit_based_model.redispatch`
- `unit_based_model.zonal_configuration`
:::

:::{tab-item} Order-Book
If `run.market_model = "order_book_based_model"`, edit these first:

| field | required | purpose | examples |
|---|---|---|---|
| `order_book_based_model.dataset` | yes | Select order-book dataset. | `TEST_3NODE`, `OMIE` |
| `order_book_based_model.cut_type` | yes | Select cut strategy. | `price based`, `no good` |
| `order_book_based_model.euphemia_configuration.network_model` | yes | Select network representation. | `ATC`, `FBMC` |
| `order_book_based_model.euphemia_configuration` | recommended | Iteration/reinsertion/solver controls. | `max_iterations`, `time_limit`, `price_lower_bound` |
:::
::::

```{note}
Redispatch is only used for zonal unit-based models (`Zonal_NTC_aggregated`, `Zonal_NTC_multiedge`, `Zonal_FBMC`). It is not used with `DCOPF`. These zonal models are only supported for `PyPSAEurSmall` and `PyPSAEurLarge`.
```

## Two Common Starting Points

::::{tab-set}
:::{tab-item} Unit-Based Template
```json
{
  "run": {
    "market_model": "unit_based_model",
    "verbosity": true
  },
  "unit_based_model": {
    "dataset": "PyPSAEurLarge",
    "power_flow_model": { "type": "Zonal_NTC_aggregated" },
    "pricing_algorithm": "ELMP",
    "redispatch": {
      "algorithm": "MinCostRD",
      "constraint_units": false,
      "threshold": 0.001,
      "alpha": 0.01
    },
    "solver_configuration": {
      "time_limit": 3600,
      "slack_penalty": 1e15
    },
    "zonal_configuration": {
      "type": "zonal_DE2-s",
      "factor": 0.8,
      "base_case": "BC4"
    }
  }
}
```
Use this for zonal unit-based runs with redispatch.

For nodal runs, switch `power_flow_model.type` to `DCOPF` and usually omit `redispatch` and `zonal_configuration`.
:::

:::{tab-item} Order-Book Template
```json
{
  "run": {
    "market_model": "order_book_based_model",
    "verbosity": true
  },
  "order_book_based_model": {
    "dataset": "TEST_3NODE",
    "cut_type": "price based",
    "euphemia_configuration": {
      "network_model": "FBMC",
      "max_iterations": 50
    }
  }
}
```
Use this for the simplified EUPHEMIA-style order-book workflow.
:::
::::

## Main Option Groups

::::{tab-set}
:::{tab-item} Model + Datasets
`run.market_model`

- `unit_based_model`
- `order_book_based_model`

`unit_based_model.dataset`

- `IEEE_RTS`
- `PJM`
- `PyPSAEurSmall`
- `PyPSAEurLarge`
- `ARPA`

`order_book_based_model.dataset`

- `GENERATED_SMALL`
- `GENERATED_LARGE`
- `OMIE`
- `GME`
- `TEST_3NODE`
- `TEST_3NODE_LOWCAP`
- `IEEE_RTS`
- `ARPA`
:::

:::{tab-item} Unit-Based Algorithms
`unit_based_model.power_flow_model.type`

- `DCOPF`
- `Zonal_NTC_aggregated`
- `Zonal_NTC_multiedge`
- `Zonal_FBMC`

`unit_based_model.pricing_algorithm`

- `ELMP`
- `IP`
- `MinMWP`
- `Join`
- `Markup`

`unit_based_model.redispatch.algorithm` (zonal only)

- `MinCostRD`
- `MinAbsCostRD`
- `MinAbsVolRD`
:::

:::{tab-item} Order-Book Algorithms
`order_book_based_model.cut_type`

- `price based`
- `combinatorial benders`
- `no good`
:::
::::

```{warning}
Not every combination is supported.

For the unit-based workflow:

- `DCOPF` is nodal. Use it without redispatch.
- `Zonal_NTC_aggregated`, `Zonal_NTC_multiedge`, and `Zonal_FBMC` are zonal and only supported with `PyPSAEurSmall` and `PyPSAEurLarge`.
- `redispatch` and `zonal_configuration` are relevant only for zonal runs.

In practice:

- choose `DCOPF` for nodal runs
- choose zonal models only with `PyPSAEurSmall` or `PyPSAEurLarge`
```

## Validation

APEM validates `config.json` before running. Missing or inconsistent settings raise errors instead of running with a broken setup.

Validation is implemented in `apem.config_loader.ConfigLoader`.
