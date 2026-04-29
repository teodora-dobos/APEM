# APEM - Allocation and Pricing in Electricity Markets

APEM is a Python framework for electricity-market clearing, pricing, and analysis. It brings together optimization-based market models, pricing methods, network-aware post-processing, and evaluation tools in one codebase.

![APEM framework overview](framework_overview.png)

## What APEM Includes

APEM is organized around two main market-modeling workflows and supporting analysis modules.

- **Unit-based model**: models physical generation units, buyers, networks, allocation, pricing, and redispatch.
- **Order-book-based model**: models Euphemia-style market clearing from buy and sell orders, including step orders, block orders, complex orders, scalable orders, cuts, and reinsertion logic.
- **Node ranking**: scores network nodes using graph-based and market-based indicators.
- **Power-flow relaxations**: groups alternative power-flow relaxation formulations for related studies.

The power-flow-relaxations experiments require MOSEK and a valid MOSEK license. See [power_flow_relaxations/README.md](power_flow_relaxations/README.md).

## Installation

APEM requires Python 3.10 or newer and a valid Gurobi license for the main market-clearing optimization workflows. The separate power-flow-relaxations module also requires MOSEK and a valid MOSEK license.

```bash
git clone https://github.com/teodora-dobos/APEM.git
cd APEM

python -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt
pip install -e .
```

On Windows PowerShell, activate the virtual environment with:

```powershell
.\.venv\Scripts\Activate.ps1
```

For more setup details, see [docs/installation.md](docs/installation.md).

## Gurobi

Most APEM workflows require Gurobi through `gurobipy`. Make sure Gurobi is installed in the active Python environment and that your license is available on the machine.

If needed:

```bash
pip install gurobipy
```

More information about academic and commercial licenses is available from [Gurobi](https://gurobi.com/unrestricted).

## MOSEK For Power-Flow Relaxations

The `power_flow_relaxations` module uses MOSEK through its Fusion API for the DCOPF, Shor, chordal Shor, Jabr, and QC relaxation experiments. To run this module, install the extra requirements and configure a MOSEK license:

```bash
pip install -r power_flow_relaxations/requirements.txt
```

Place the license at `~/.mosek/mosek.lic` or set:

```bash
export MOSEKLM_LICENSE_FILE=/path/to/mosek.lic
```

See [power_flow_relaxations/README.md](power_flow_relaxations/README.md) and [docs/pf_relaxations/index.md](docs/pf_relaxations/index.md) for details.

## Usage

APEM is configured through [config.json](config.json). The config has three main sections:

- `run`: selects the active market model.
- `unit_based_model`: settings for the unit-based workflow.
- `order_book_based_model`: settings for the order-book-based workflow.

After editing `config.json`, run:

```bash
python main.py
```

Outputs are written under:

- `results/unit_based_model/...`
- `results/order_book_based_model/...`

For the full configuration reference, see [docs/configuration.md](docs/configuration.md).

## Available Workflows

### Unit-Based Model

Use the unit-based workflow when your data describes physical generators, buyers, and a network. It supports nodal and zonal clearing, multiple pricing algorithms, and redispatch analysis.

Common options include:

- datasets: `IEEE_RTS`, `PJM`, `PyPSAEurSmall`, `PyPSAEurLarge`, `ARPA`
- power-flow models: `DCOPF`, `Zonal_NTC_aggregated`, `Zonal_NTC_multiedge`, `Zonal_FBMC`
- pricing algorithms: `ELMP`, `IP`, `MinMWP`, `Join`, `Markup`
- redispatch algorithms: `MinCostRD`, `MinAbsCostRD`, `MinAbsVolRD`

Example scripts are available in [scripts/unit_based_model](scripts/unit_based_model).

### Order-Book-Based Model

Use the order-book-based workflow when your data is represented as market orders. This workflow implements a simplified Euphemia-style clearing process.

Common options include:

- datasets: `GENERATED_SMALL`, `GENERATED_LARGE`, `OMIE`, `GME`, `TEST_3NODE`, `TEST_3NODE_LOWCAP`, `IEEE_RTS`, `ARPA`
- cut types: `price based`, `combinatorial benders`, `no good`

For internals, order types, and run-output details, see [apem/order_book_based_model/euphemia/README.md](apem/order_book_based_model/euphemia/README.md).

## Custom Data

APEM can run on custom datasets, but datasets must be added in the structure expected by the selected workflow.

- For unit-based data, add a parser that returns a `Scenario`.
- For order-book data, provide Euphemia-style CSV tables and register the dataset.
- For converting unit-based scenarios into order-book CSV inputs, use the conversion utilities under `apem/order_book_based_model/euphemia/data/conversion/`.

See [docs/custom_datasets.md](docs/custom_datasets.md) for the full custom data guide.

## Documentation

The Sphinx documentation lives in [docs](docs).

Build it with:

```bash
python -m pip install -r docs/requirements.txt
cd docs
make html
```

Open the generated documentation at:

```text
docs/_build/html/index.html
```

## Troubleshooting

If you see `ModuleNotFoundError: No module named 'apem'`, run commands from the repository root and install the package in editable mode:

```bash
pip install -e .
```

If optimization runs fail, check that `gurobipy` is installed in the active environment and that your Gurobi license is configured.
