# APEM Core

The APEM Core layer coordinates configuration, model selection, and execution flow.

```{toctree}
:maxdepth: 1

unit_based_model
order_book_based_model
```

## Scope

Core responsibilities:

- Normalize and validate runtime configuration from `config.json`.
- Map high-level model selections to concrete implementations.
- Orchestrate allocation, pricing, redispatch, and result analysis runs.
- Persist run metadata and output directory structure.

## Execution Flow

1. `ConfigLoader` reads and validates model-scoped configuration.
2. `MarketModels` / `market_models` resolve selected market model.
3. `execution_chain` dispatches to:
   - unit-based solve flow, or
   - order-book Euphemia flow.
4. Results and metadata are written under `results/...`.

## Extension Points

Common extension points in the core layer:

- Add new config fields in `apem.config_loader.ConfigLoader`.
- Add/adjust core model registry in `apem.core` / `apem.market_models`.
- Extend execution orchestration in `apem.execution_chain`.

## API: `apem.config_loader`

```{eval-rst}
.. automodule:: apem.config_loader
   :members:
   :show-inheritance:
```

## API: `apem.core`

```{eval-rst}
.. automodule:: apem.core
   :members:
   :show-inheritance:
```

## API: `apem.market_models`

```{eval-rst}
.. automodule:: apem.market_models
   :members:
   :show-inheritance:
```

## API: `apem.execution_chain`

```{eval-rst}
.. automodule:: apem.execution_chain
   :members:
   :show-inheritance:
```
