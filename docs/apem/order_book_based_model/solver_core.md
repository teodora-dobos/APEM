# Solver Core

The solver core groups the two modules that define and run the central
Euphemia master-problem workflow:

- `Master Problem`: orchestration, iteration flow, callback handling, logging,
  and output writing
- `Model Formulation`: helper functions that populate the objective and
  constraints of the optimization model

```{toctree}
:maxdepth: 1
:hidden:

master_problem
model
```
