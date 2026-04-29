# Power Flow Relaxations

Runner for DCOPF/ACOPF relaxations (DCOPF, Shor, ChordalShor, Jabr, QC variants) on ARPA subscenarios.

## Quick start
- From repo root:
  ```bash
  PYTHONPATH=. MPLCONFIGDIR=/tmp/mplcache ./.venv/bin/python -m power_flow_relaxations.run_relaxations
  ```
- From this folder:
  ```bash
  PYTHONPATH=.. MPLCONFIGDIR=/tmp/mplcache ../.venv/bin/python -m power_flow_relaxations.run_relaxations
  ```

## Requirements
- Python venv with: `mosek` (solver) **plus a valid Mosek license**, `numpy`, `pandas`, `scipy`, `networkx`, `tqdm`, `psutil`, `matplotlib`.
- Mosek license: place at `~/.mosek/mosek.lic` or set `MOSEKLM_LICENSE_FILE=/path/to/mosek.lic`.
- Convenience: install the extras via `pip install -r power_flow_relaxations/requirements.txt`.

## CLI flags
- `--batch-size` (default 1): subscenarios per size.
- `--model` (default all): comma-separated tags (`DCOPF,Shor,QC6`, etc.).
- `--model-start-index/--model-end-index`: slice the model list.
- `--scenario-start-index/--scenario-end-index`: slice the default subscenario-size list (`32`, `160`), skipping sizes above the network size.
