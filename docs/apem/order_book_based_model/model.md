# Model Formulation

Core Euphemia formulation helpers for the master problem.

This module contains the functions that populate the mathematical structure of
the order-book-based optimization model after variable creation. In practice,
these helpers define:

- the surplus-maximizing objective
- the market-clearing and order-linking constraints
- the network constraints for `ATC` and `FBMC`

## Model Formulation

API path: `apem.order_book_based_model.euphemia.model.setup_model`

```{eval-rst}
.. automodule:: apem.order_book_based_model.euphemia.model.setup_model
   :members:
   :show-inheritance:
```
