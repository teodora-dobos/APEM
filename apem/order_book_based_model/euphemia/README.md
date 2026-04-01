# EUPHEMIA Module

This README is intentionally **module-scoped**.
For installation, global config format, and top-level run instructions, use the repository root README.

## Scope

This folder contains the order-book-based model implementation (EUPHEMIA-style flow):
- surplus-maximizing master problem
- price determination subproblem
- cut strategies
- optional reinsertion logic
- order-book-based dataset parsing/conversion helpers

## Public API

Primary entrypoint:
- `runner.py` -> `solve_euphemia(dataset, cut_type, config_overrides=None)`

Key enums:
- `enums/datasets.py` -> `OrderBookBased_Datasets`
- `enums/cut_types.py` -> `CutTypes`

## Internal Structure

- `master_problem/`: core MIP + callback orchestration
- `pricing/`: pricing subproblem (MCP recovery)
- `cutting_strategies/`: NG / CB / PB cut logic
- `reinsertions/`: PRMIC / PRB reinsertion routines
- `model/`: objective and constraint builders
- `data/parsing/`: order-book CSV dataset loading
- `data/conversion/`: unit-based -> order-book bidding-language conversion

## Order Types Description

Canonical order families (enum):
- `STEP`
- `PLO` (piecewise linear order)
- `BLOCK`
- `COMPLEX`
- `SCALABLE_COMPLEX`

Defined in:
- `enums/order_types.py`

### Step Orders (`step_orders.csv`)
- Piecewise constant bid/offer segments per period and zone.
- Sign convention: positive `q` behaves as sell-side volume, negative `q` as buy-side volume.
- Cleared with continuous acceptance `0..1`.

### Piecewise Linear Orders (`piecewise_linear_orders.csv`)
- Linear bid/offer segments with prices interpolated between `p0` and `p1`.
- Cleared with continuous acceptance `0..1`.

### Block Orders (`block_orders.csv`)
- Multi-period indivisible/partially indivisible structures with acceptance constrained by `MAR`.
- `block_type` values:
  - `normal`: independent block order.
  - `exclusive`: members sharing `code_prm` form an exclusive group (at most one accepted).
  - `linked`: child references parent in `code_prm`; child acceptance cannot exceed parent acceptance.
  - `flexible`: one-period activation chosen via `flex_period`.

### Complex Orders (`complex_orders.csv` + `complex_step_orders.csv`)
- Parent order with associated step orders.
- Uses `fixed_term`, `variable_term`, and `condition`.
- Typical `condition` values used in diagnostics/cuts:
  - `MIC` (minimum income condition)
  - `MP` (minimum profit condition)
  - `load gradient`
- `load_gradient` limits inter-temporal volume changes.

### Scalable Complex Orders (`scalable_complex_orders.csv` + `scalable_step_orders.csv`)
- Complex-order variant with scalable activation and optional minimum acceptance per period.
- Uses `MAP1..MAPT` for period-wise minimum acceptance when active.
- Supports `load_gradient` similarly to complex orders.

### Where Behavior Is Enforced

Model constraints:
- `model/setup_model.py`
  - market balance and acceptance linkage
  - block subtypes (`exclusive`, `linked`, `flexible`)
  - complex/scalable load-gradient and MAP constraints

Post-solve economic checks and cut candidate extraction:
- `master_problem/master_problem.py`
  - PAB detection
  - MIC/MP checks for complex and scalable complex orders

### Network Inputs
- ATC mode (default): optional `atc.csv` with directed capacities (`from_zone,to_zone,t,cap`) and optional `ramp_up,ramp_down`.
- FBMC mode: optional `fb_constraints.csv` (`cnec_id,t,ram[,lb]`) plus `fb_ptdf.csv` (`cnec_id,t,zone,ptdf`).

## Cut Types

Cut-type enum values:
- `price based` (`PB`)
- `combinatorial benders` (`CB`)
- `no good` (`NG`)

Defined in:
- `enums/cut_types.py`

Selection and callback dispatch:
- `master_problem/master_problem.py`

### Price Based (`PB`)
- Solves an unconstrained pricing subproblem (step + piecewise-linear orders only).
- If feasible, updates provisional prices and adds cuts that deactivate paradoxically accepted/rejected patterns (PAB/PAMIC/PAMP-style logic).
- Falls back to a no-good cut if no useful price-based cut can be built.
- Implementation: `cutting_strategies/price_based.py`.

### Combinatorial Benders (`CB`)
- Computes an IIS of the infeasible pricing subproblem.
- Builds a cut from IIS-linked master binaries (block/complex/scalable-complex acceptances), forcing at least one of them to change.
- Falls back to a no-good cut if no IIS-linked terms are found.
- Implementation: `cutting_strategies/combinatorial_benders.py`.

### No Good (`NG`)
- Generic exclusion cut on current binary assignment.
- Enforces that at least one binary variable flips in future incumbents.
- Most conservative strategy; useful as baseline/fallback.
- Implementation: `cutting_strategies/no_good.py`.

## Euphemia-Specific Config Keys

Defined in `euphemia_config.py` and passed via `order_book_based_model.euphemia_configuration`:
- `disable_reinsertion`
- `calculate_corrected_welfare`
- `price_lower_bound`, `price_upper_bound`
- `beta_MIC`, `delta_load_gradient`, `delta_PAB`, `epsilon`
- `max_iterations`
- `reinsertion_max_iterations`
- `max_prb_reinsertion_attempts` (`null`/`None` = unlimited)
- `big_m`
- `network_model` (`"ATC"` or `"FBMC"`)
- `lazy_constraints`, `output_flag`, `time_limit`, `mip_gap`, `threads`, `seed`

## Output

Per run:
- `results/order_book_based_model/euphemia/<DATASET>/<RUN_ID>/<CUT_TYPE>/`

Core artifacts:
- `allocation/results.csv`: incumbent master variables (`variable,value`)
- `prices/prices.csv`: MCP variables from feasible pricing subproblems (`variable,value`)
- `evaluation/evaluation.txt`: human-readable run summary (iterations, welfare, runtime, prices, optional corrected welfare)
- `debug/master_problem.lp`, `debug/pricing_model.lp`: solver model dumps
- `run.json`: machine-readable run metadata
- `run.log`: chronological run log

Diagnostics (`iteration_k.txt` IDs):
- `pab/`: paradoxically accepted blocks
- `block_inm_threshold/`: near-threshold INM block candidates for cuts
- `complex_mic/`: complex MIC/MP violations
- `complex_mic_inm_threshold/`: thresholded complex MIC/MP candidates
- `scalable_mic/`: scalable complex MIC/MP violations
- `scalable_mic_inm_threshold/`: thresholded scalable MIC/MP candidates

Notes:
- diagnostics folders are created for every run, even when empty
- populated diagnostics depend on cut type and triggered checks
