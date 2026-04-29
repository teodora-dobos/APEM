# APEM: Allocation and Pricing in Electricity Markets

APEM is a framework for electricity-market clearing, pricing, and analysis. It brings together optimization-based market models, pricing methods, network-aware post-processing, and supporting evaluation tools in a single codebase.

![APEM framework overview](framework_overview.png)

## Modules

- **APEM Core**: market-clearing workflows for unit-based and order-book-based models. Uses [config.json](config.json), runs allocation/pricing/redispatch pipelines, and writes results under `results/...`.
- **APEM Node Ranking**: structural and market-based node-ranking tools, including network scores, market scores, PTDF indicators, and DC economic-dispatch baselines.
- **APEM PF Relaxations**: DCOPF and ACOPF relaxation experiments on ARPA-derived subscenarios, including `DCOPF`, `Shor SDP`, `Chordal SDP`, `Jabr SOCP`, and `QC` variants.

## Requirements

- Python 3.10+
- Gurobi + valid license for APEM Core optimization workflows
- MOSEK + valid license for APEM PF Relaxations

MOSEK licenses can be placed at `~/.mosek/mosek.lic` or configured with `MOSEKLM_LICENSE_FILE`.

## Install

```bash
git clone https://github.com/teodora-dobos/APEM.git
cd APEM

python -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt
pip install -e .
```

The commands above are for macOS/Linux shells. On Windows PowerShell, activate the environment with:

```powershell
.\.venv\Scripts\Activate.ps1
```

For PF relaxation experiments, also install:

```bash
pip install -r power_flow_relaxations/requirements.txt
```

## Run APEM Core

Edit [config.json](config.json), then run:

```bash
python main.py
```

Core outputs are written under:

- `results/unit_based_model/...`
- `results/order_book_based_model/...`

Configuration details: [docs/configuration.md](docs/configuration.md)

## Run PF Relaxations

After installing MOSEK requirements and configuring a license:

```bash
PYTHONPATH=. MPLCONFIGDIR=/tmp/mplcache ./.venv/bin/python -m power_flow_relaxations.run_relaxations
```

Results are written under `relaxation_results/...`.

PF relaxation details: [docs/pf_relaxations/index.md](docs/pf_relaxations/index.md)

## Documentation

Build the Sphinx docs locally:

```bash
python -m pip install -r docs/requirements.txt
cd docs
make html
```

Open `docs/_build/html/index.html`.

Useful entry points:

- Core docs: [docs/apem/index.md](docs/apem/index.md)
- Node ranking docs: [docs/node_ranking/index.md](docs/node_ranking/index.md)
- PF relaxation docs: [docs/pf_relaxations/index.md](docs/pf_relaxations/index.md)
- Custom datasets: [docs/custom_datasets.md](docs/custom_datasets.md)
- Order-book internals: [apem/order_book_based_model/euphemia/README.md](apem/order_book_based_model/euphemia/README.md)

## Troubleshooting

If `apem` cannot be imported, run from the repository root and reinstall in editable mode:

```bash
pip install -e .
```

If optimization fails, first check the relevant solver package and license: `gurobipy` for APEM Core, `mosek` for APEM PF Relaxations.
