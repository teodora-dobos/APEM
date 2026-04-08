# Configuration

APEM is configured through a single file at the repository root: [`config.json`](https://github.com/teodora-dobos/APEM/blob/main/config.json).

If you are new to the project, the most important thing to understand is this:

- you do **not** create a separate config per run,
- you edit `config.json`,
- then you run APEM,
- and APEM reads the settings from that file.

## How `config.json` Is Used

`config.json` is the runtime input for `main.py`.

In practice, a normal workflow looks like this:

1. Open [`config.json`](https://github.com/teodora-dobos/APEM/blob/main/config.json).
2. Choose which market model you want to run under `run.market_model`.
3. Edit the settings for that model.
4. Save the file and run:

```bash
python main.py
```

APEM then loads `config.json`, validates it, and runs the selected workflow with those settings.

## Basic Structure

The configuration file is model-scoped and has three main sections:

- `run`: global run selection
- `unit_based_model`: settings used when `run.market_model = "unit_based_model"`
- `order_book_based_model`: settings used when `run.market_model = "order_book_based_model"`

Only one market model is active in a given run. The inactive section can stay in the file, but it is not used for that run.

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

This example runs the **unit-based workflow** because `run.market_model` is set to `unit_based_model`. More specifically, APEM will load the `PyPSAEurLarge` dataset, solve the market-clearing problem with the `DCOPF` power-flow model, and apply the `ELMP` pricing algorithm. The `order_book_based_model` section remains in the file as an inactive configuration block for future runs, but it is ignored in this run.

## What To Edit First

If you only want to get started, focus on these fields:

### Global run selection

- `run.market_model`
  - choose `unit_based_model` or `order_book_based_model`
- `run.verbosity`
  - enables or reduces console output during the run

### Unit-based workflow

If `run.market_model` is `unit_based_model`, the most important fields are:

- `unit_based_model.dataset`
- `unit_based_model.power_flow_model.type`
- `unit_based_model.pricing_algorithm`

If you use a **zonal** power-flow model, you will also adjust:

- `unit_based_model.redispatch.algorithm`
- `unit_based_model.zonal_configuration`

```{note}
Redispatch is only used for zonal power-flow models such as `Zonal_NTC_aggregated`, `Zonal_NTC_multiedge`, and `Zonal_FBMC`. It is **not** used with `DCOPF`. These zonal models are only supported for `PyPSAEurSmall` and `PyPSAEurLarge`.
```

You will mainly adjust `solver_configuration` when you need to change runtime limits, tolerances, or solver behavior.

### Order-book workflow

If `run.market_model` is `order_book_based_model`, the most important fields are:

- `order_book_based_model.dataset`
- `order_book_based_model.cut_type`
- `order_book_based_model.euphemia_configuration.network_model`

The rest of `euphemia_configuration` controls details such as iteration limits, reinsertion behavior, price bounds, and solver options.

## Two Common Starting Points

### Example: unit-based run

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

Use this when you want to run a **zonal** unit-based market model with redispatch. If you instead want a nodal `DCOPF` run, you typically omit `redispatch` and `zonal_configuration`.

### Example: order-book-based run

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

Use this when you want to run the simplified EUPHEMIA-style order-book workflow.

## Main Option Groups

### Market models

- `unit_based_model`
- `order_book_based_model`

### Unit-based datasets

- `IEEE_RTS`
- `PJM`
- `PyPSAEurSmall`
- `PyPSAEurLarge`
- `ARPA`

### Order-book datasets

- `GENERATED_SMALL`
- `GENERATED_LARGE`
- `OMIE`
- `GME`
- `TEST_3NODE`
- `TEST_3NODE_LOWCAP`
- `IEEE_RTS`
- `ARPA`

### Unit-based power-flow models

- `DCOPF`
- `Zonal_NTC_aggregated`
- `Zonal_NTC_multiedge`
- `Zonal_FBMC`

### Pricing algorithms

- `ELMP`
- `IP`
- `MinMWP`
- `Join`
- `Markup`

### Redispatch algorithms

These are only relevant for zonal unit-based models, not for `DCOPF`.

- `MinCostRD`
- `MinAbsCostRD`
- `MinAbsVolRD`

### Order-book cut types

- `price based`
- `combinatorial benders`
- `no good`

```{warning}
Not every configuration combination is supported.

For the **unit-based workflow**:

- `DCOPF` is the nodal model. Use it without redispatch.
- `Zonal_NTC_aggregated`, `Zonal_NTC_multiedge`, and `Zonal_FBMC` are zonal models. They only work with `PyPSAEurSmall` and `PyPSAEurLarge`.
- `redispatch` and `zonal_configuration` are only relevant for those zonal runs.

In practice:

- choose `DCOPF` if you want a nodal run
- choose a zonal model only together with `PyPSAEurSmall` or `PyPSAEurLarge`
```

## Validation

APEM validates the configuration before running. If something is missing or inconsistent, it will raise an error instead of silently using a broken setup.

Validation is implemented in `apem.config_loader.ConfigLoader`.
