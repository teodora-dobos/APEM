# EUPHEMIA Module

This README is intentionally **module-scoped**.
For installation, global config format, and top-level run instructions, use the repository root README.

## Scope

This folder contains the EU market model implementation (EUPHEMIA-style flow):
- surplus-maximizing master problem
- price determination subproblem
- cut strategies
- optional reinsertion logic
- EU-format dataset parsing/conversion helpers

## Public API

Primary entrypoint:
- `runner.py` -> `solve_euphemia(dataset, cut_type, config_overrides=None)`

Key enums:
- `enums/datasets.py` -> `EU_Datasets`
- `enums/cut_types.py` -> `CutTypes`

## Internal Structure

- `master_problem/`: core MIP + callback orchestration
- `pricing/`: pricing subproblem (MCP recovery)
- `cutting_strategies/`: NG / CB / PB cut logic
- `reinsertions/`: PRMIC / PRB reinsertion routines
- `model/`: objective and constraint builders
- `data/parsing/`: EU CSV dataset loading
- `data/conversion/`: US -> EU bidding-language conversion

## Euphemia-Specific Config Keys

Defined in `euphemia_config.py` and passed via `eu_model.euphemia_configuration`:
- `disable_reinsertion`
- `calculate_corrected_welfare`
- `price_lower_bound`, `price_upper_bound`
- `beta_MIC`, `delta_load_gradient`, `delta_PAB`, `epsilon`
- `max_iterations`
- `reinsertion_max_iterations`
- `max_prb_reinsertion_attempts` (`null`/`None` = unlimited)
- `big_m`
- `lazy_constraints`, `output_flag`, `time_limit`, `mip_gap`, `threads`, `seed`

## Output Contract

Per run:
- `EU_results/euphemia/<DATASET>/<CUT_TYPE>/<RUN_ID>/`

Main artifacts:
- `allocation/results.csv` (`variable,value`)
- `prices/prices.csv` (`variable,value`)
- `evaluation/evaluation.txt`
- `debug/master_problem.lp`
- `debug/pricing_model.lp`
- `run.json`
- `run.log`

Diagnostics folders (created for all runs, may be empty):
- `pab/`
- `block_inm_threshold/`
- `complex_mic/`
- `complex_mic_inm_threshold/`
- `scalable_mic/`
- `scalable_mic_inm_threshold/`

### Artifact Semantics

- `allocation/results.csv`:
  stores the current incumbent master solution variables (for example acceptance variables and ATC flow variables).
- `prices/prices.csv`:
  stores MCP variables from pricing subproblems that solved to optimality.
- `evaluation/evaluation.txt`:
  human-readable run summary (iterations, welfare, runtime, prices, and optional corrected welfare).
- `run.json`:
  machine-readable run metadata (status, timestamps, objective, paths).
- `run.log`:
  chronological execution log for the run.
- `debug/master_problem.lp`, `debug/pricing_model.lp`:
  dumped solver models for debugging and reproducibility.

### Diagnostics Semantics

- `pab/iteration_k.txt`:
  IDs of currently paradoxically accepted block bids (as checked in iteration `k`).
- `block_inm_threshold/iteration_k.txt`:
  IDs of block bids close to the in-the-money threshold used for threshold-based block cuts.
- `complex_mic/iteration_k.txt`:
  IDs of accepted complex orders that violate MIC/MP consistency at current prices.
- `complex_mic_inm_threshold/iteration_k.txt`:
  thresholded complex MIC/MP candidates used for cutting decisions.
- `scalable_mic/iteration_k.txt`:
  IDs of accepted scalable complex orders that violate MIC/MP consistency.
- `scalable_mic_inm_threshold/iteration_k.txt`:
  thresholded scalable MIC/MP candidates used for cutting decisions.

Notes:
- diagnostics folders are created for every run, even when empty.
- which diagnostics are populated depends on cut type and whether the corresponding checks are triggered.
