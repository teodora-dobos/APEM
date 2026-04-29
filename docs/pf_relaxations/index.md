# APEM PF Relaxations

The `power_flow_relaxations` module provides a runner for comparing power-flow relaxation formulations on ARPA-derived subscenarios.

## Requirements

- A working MOSEK installation is required to run this module.
- A valid MOSEK license must be available in your environment.

## Scope

- Run DCOPF and ACOPF relaxation models on connected network subgraphs.
- Compare model behavior across runtime, solve time, memory footprint, welfare, and feasibility violations.
- Produce CSV result files per model and subscenario size.

## Implemented Relaxations

- `NodalBaseModel`: shared nodal optimization scaffold with common variables, bid constraints, and network-balance handling.
- `DCOPF`: linear DC approximation using voltage angles and active-power flow constraints.
- `Shor SDP`: semidefinite relaxation of AC power flow with a stronger but more expensive convex envelope.
- `Chordal SDP`: chordal decomposition of the SDP model to reduce computational cost on larger networks.
- `Jabr SOCP`: second-order-cone relaxation based on Jabr-type formulations, typically lighter than full SDP.
- `QC` variants: quadratic-convex relaxations with different approximation degrees and sampling modes (local/global).

```{toctree}
:maxdepth: 1
:hidden:

models/nodal_base_model
models/dcopf
Shor SDP <models/shor>
Chordal SDP <models/chordal_shor>
Jabr SOCP <models/jabr>
models/qc
```

## Default Run Behavior

`run_relaxations.py` currently defaults to:

- `--batch-size 1`
- subscenario sizes `32` and `160` nodes
- all available relaxation models

Results are written under:

- `relaxation_results/<MODEL_TAG>_<SIZE>_results.csv`

## Entrypoints

- `power_flow_relaxations.run_relaxations`: runs the relaxation experiments, builds subscenarios, solves selected models, and writes per-model CSV results.
- `power_flow_relaxations.create_figures`: reads the generated result CSV files and creates comparison plots (runtime, memory, welfare, and feasibility metrics).
