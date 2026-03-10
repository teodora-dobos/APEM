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

## Output

Per run:
- `EU_results/euphemia/<DATASET>/<CUT_TYPE>/<RUN_ID>/`

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
