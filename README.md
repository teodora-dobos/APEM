# APEM - Allocation and Pricing in Electricity Markets
![alt text](framework_overview.png)


## Installation
<details>
  <summary> After cloning the code, the following setup steps need to be performed once before running the code. </summary>

  <br>**Note:** The setup instructions assume macOS, Linux, or Windows and require Python 3.10 (or higher). 

  ### 1. Virtual environment
  - Create a virtual environment (alternatively, you can use `virtualenv` or whatever you prefer) - you may choose any name (e.g., "apem-venv"):
  ```bash
  python -m venv <venv_name>   # Example: python -m venv apem-venv
  ```

  **Note:** You can specify the Python version for the virtual environment, e.g., `python3.11 -m venv <venv_name>`. The specified version already needs to be installed in the system. If you only specify "python3", the venv uses the standard python3 version from the system. When working with _virtualenv_, the command would be _virtualenv - p python3 <venv_name>_.

  - Activate the virtual environment:
  ```bash
  # macOS / Linux:
  source ./<venv-name>/bin/activate        # Example: source ./apem-venv/bin/activate

  # Windows (PowerShell):
  .\<venv-name>\Scripts\Activate.ps1       # Example: .\apem-venv\Scripts\Activate.ps1

  # Windows (cmd.exe):
  .\<venv-name>\Scripts\activate.bat       # Example: .\apem-venv\Scripts\activate.bat
  ```

  **Note:** The virtual environment can be deactivated using `deactivate`- however, for the next steps, we want the virtual environment to be active.


  ### 2. Install required packages
  - Install all requirements from the `requirements.txt` file:
  ```bash
  pip install -r <path-to-requirements.txt>   # Example: pip install -r requirements.txt
  ```

  ### 3. Gurobi license
  To run the code, a valid academic or commercial Gurobi license is required ([more information](https://gurobi.com/unrestricted)).
  - If you do not already have such a license, you first need to create one together with API keys: 
    - Log into the Gurobi [user portal](https://portal.gurobi.com/iam/home/) > Licenses > Request > Choose your license (for academic, you can either use _WLS Academic_ - e.g., required when using WSL - or _Named-User Academic_) > Generate Now! &rarr; license is now listed under "Licenses"
    - Open Gurobi [Web License Manager](https://license.gurobi.com/manager/licenses/) > API Keys > Create API Key (make sure you create them for your new license: check ID) > Download keys
  - Finally place the `gurobi.lic` file in your `home directory`
</details>

## Usage
**Note:** Make sure to always activate your virtual environment before running the code!

Before running the code, update the [`config.json`](./config.json) file.
The config is model-scoped:
- `run`: global run selection
- `unit_based_model`: unit-based-model-specific settings
- `order_book_based_model`: order-book-based-model-specific settings
Only this model-scoped format is supported.

```jsonc
{
  "run": {
    "market_model": "order_book_based_model",  // unit_based_model or order_book_based_model
    "verbosity": true
  },
  "unit_based_model": {
    "dataset": "ARPA",
    "power_flow_model": { "type": "DCOPF" },
    "pricing_algorithm": "IP",
    "redispatch": {
      "algorithm": "MinCostRD",
      "constraint_units": false,
      "threshold": 0.001,
      "alpha": 0.01
    },
    "solver_configuration": {
      "time_limit": 3600,
      "slack_penalty": 1e15
    },
    "zonal_configuration": {
      "type": "zonal_DE2-s",
      "factor": 0.8,
      "base_case": "BC4"
    }
  },
  "order_book_based_model": {
    "dataset": "GME",
    "cut_type": "price based",
    "euphemia_configuration": {
      "max_iterations": 50
    }
  }
}
```

### Available options

- **Market models**: `unit_based_model`, `order_book_based_model`
- **Datasets**
  - unit-based: `IEEE_RTS`, `PJM`, `PyPSAEurSmall`, `PyPSAEurLarge`, `ARPA`
  - order-book-based: `Generated Small`, `Generated Large`, `OMIE`, `GME`, `IEEE_RTS`, `ARPA`
- **Power flow models** (only for ``unit_based_model``): `DCOPF`, `Zonal_NTC_aggregated`, `Zonal_NTC_multiedge`, `Zonal_FBMC` (base cases: `BC1`, `BC2`, `BC3.1`, `BC3.2`, `BC4`)
- **Cut types** (only for `order_book_based_model`): `price based`, `combinatorial benders`, `no good`
- **Pricing algorithms** (only for `unit_based_model`): `ELMP`, `IP`, `MinMWP`, `Join`
- **Redispatch algorithms** (only for `unit_based_model/Zonal_NTC_aggregated`): `MinCostRD`, `MinAbsCostRD`, `MinAbsVolRD`
- **Zonal configurations** (only for `unit_based_model/Zonal_NTC_aggregated`, `unit_based_model/Zonal_NTC_multiedge` and `unit_based_model/Zonal_FBMC`): `national`, `zonal_DE2-k`, `zonal_DE2-s`, `zonal_DE3`, `zonal_DE4`, `zonal_DE5`

Unit-based-model solver settings like tolerances, runtime limits, and slack-penalty scaling can be adjusted under `unit_based_model.solver_configuration`.
Order-book-based-model-specific hyperparameters can be adjusted under `order_book_based_model.euphemia_configuration` (for example `max_iterations`,
`reinsertion_max_iterations`, price bounds, cut thresholds, and Gurobi parameters such as `time_limit`, `mip_gap`,
`threads`, `seed`, `output_flag`).
For order-book-based-model internals (module structure, API, and run output contract), see [`apem/order_book_based_model/euphemia/README.md`](./apem/order_book_based_model/euphemia/README.md).
Zonal-specific settings are under `unit_based_model.zonal_configuration`.

---
To run the configuration, execute:
```bash
python main.py
```

Once the execution is done, outputs are written under a shared `results/` directory:
- `results/unit_based_model/...` for unit-based-model runs
- `results/order_book_based_model/...` for order-book-based-model runs

For unit-based-model-specific evaluation and comparison workflows, see the example scripts in
[`scripts/unit_based_model`](./scripts/unit_based_model). These cover, for example, comparisons of
pricing algorithms, lost opportunity costs, redispatch costs, and cost-based
comparisons across power-flow models.

**Note:** If you run into `ModuleNotFoundError: No module named 'apem'`, run commands from the repository root and install the package in editable mode once:
`pip install -e .`

## Unit-Based-to-Order-Book Dataset Conversion

APEM includes a converter that transforms unit-based `Scenario` data into the CSV format expected by the Euphemia implementation (`step_orders.csv`, `block_orders.csv`, etc.).

Use this when you want to run `order_book_based_model` on converted datasets such as `IEEE_RTS` or `ARPA`.
In this repository, the `order_book_based_model` versions of `IEEE_RTS` and `ARPA` are obtained via this conversion step (unit-based parser output converted into order-book-based input CSVs).

### High-level entrypoint: `run_unit_based_to_order_based_conversion.py`

Module: `apem/order_book_based_model/euphemia/data/conversion/`

Run with its default (`ParseIEEERTS`):

```bash
python - <<'PY'
from apem.order_book_based_model.euphemia.data.conversion import run_unit_based_to_order_based_conversion
from apem.unit_based_model.data.parsing.parse_ieee_rts import ParseIEEERTS

run_unit_based_to_order_based_conversion(ParseIEEERTS)
PY
```

Run for a specific unit-based parser:

```bash
python - <<'PY'
from apem.unit_based_model.data.parsing.parse_arpa import ParseARPA
from apem.order_book_based_model.euphemia.data.conversion import run_unit_based_to_order_based_conversion

run_unit_based_to_order_based_conversion(
    ParseARPA,
    generate_uptime_patterns=True,
    reduce_linked_blocks=True,
    use_contiguous_patterns=True,
    compress_identical_blocks=True,
)
PY
```

### Advanced customization

If you need custom conversion behavior, use `DataConversion` directly:
`apem/order_book_based_model/euphemia/data/conversion/data_conversion.py`.
For standard usage, prefer `run_unit_based_to_order_based_conversion(...)`.

### What gets written

The high-level converter writes these files:

- `periods.csv`
- `step_orders.csv`
- `block_orders.csv`
- `scalable_complex_orders.csv`
- `scalable_step_orders.csv`
- `complex_orders.csv` (empty placeholder)
- `complex_step_orders.csv` (empty placeholder)
- `piecewise_linear_orders.csv` (empty placeholder)

Output folders are chosen via `CONVERTED_DATASET_PATH_MAP` in
`apem/order_book_based_model/euphemia/utils/paths.py` (for example `.../data/datasets/ieee_rts`).

### Notes

- `generate_uptime_patterns=True` regenerates files in `.../data/conversion/patterns/`.
- `compress_identical_blocks=True` merges identical linked-block chains to reduce model size.
- Conversion complexity can be high on large instances: one seller can generate many commitment-pattern-based exclusive and linked block bids, so conversion time and output size can grow quickly with the number of units, periods, and bid blocks.

## Using Your Own Data for the Unit-Based Model

Besides the datasets that are already provided in APEM, you can run the available methods using other datasets.
This guide shows how to plug **your custom dataset** into APEM so you can run allocation, pricing, and redispatch on top of your own bids and networks.

---

### What APEM expects at runtime

Your parser must return a `Scenario` object with the following pieces:

- **df_sellers (DataFrame)** - one row per (seller, period).
  - Required columns (minimum):
    - `seller` *(int/str)* - unique generator/unit id  
    - `period` *(int >= 1)* - time index (1..T)  
    - `node` *(int/str)* - network bus or zone id  
    - `max_prod` *(float, MW)* - total available production in the period  
    - `min_prod` *(float, MW)* - technical minimum  
    - `min_uptime` *(int, hours or periods)* - minimum up time (0 if not modeled)  
    - `no_load_cost` *(float, cost/unit time)* - fixed on-cost  
    - **Block offers used to create a stepwise cost curve:** `size1..sizeK` *(MW)* and `cost1..costK` *(currency/MWh)*

- **df_buyers (DataFrame)** - one row per (buyer, period).
  - Required columns (minimum):
    - `buyer` *(int/str)* - unique demand id  
    - `period` *(int >= 1)*  
    - `node` *(int/str)*  
    - `inelastic_dem` *(float, MW)* - must-serve part of demand  
    - **Block bids (if any) used to create a stepwise valuation curve:** `size1..sizeL` *(MW)* and `val1..valL` *(currency/MWh)*  
    - `max_dem` *(float, MW)* - inelastic + sum of `size*`

- **network (networkx.Graph)** - buses as nodes, branches as edges.
  - Edge attributes (for `unit_based_model/DCOPF`):  
    - `B` *(float)* - line susceptance  
    - `F_max` *(float, MW)* - thermal limit 
  - For zonal networks you may pass a single node graph.

- **nodes_agents (dict)** - mapping `node -> {"sellers": [...], "buyers": [...]}`.

- **periods (list[int])** - e.g., `[1, 2, ..., 24]`.

- **blocks_buyers (range)** - e.g., `range(1, 3+1)` for 3 buyer blocks.

- **blocks_sellers (range)** - e.g., `range(1, 4+1)` for 4 seller blocks.

- **r_star** - reference node (slack) id.

Return them via:

```python
return Scenario(dataset_name, df_buyers, df_sellers, network, nodes_agents, periods, blocks_buyers, blocks_sellers, r_star)
```

Note: Period indexing in APEM examples starts at 1. Keep it consistent.

### Where to put your raw data

Place your files under:
```python 
apem/unit_based_model/data/raw_data/<your_dataset_name>/
```

### Minimal template:
```python
from collections import defaultdict
import pandas as pd
import networkx as nx

from apem.unit_based_model.data.parsing.parse_data import ParseData
from apem.unit_based_model.data.parsing.scenario import Scenario
from apem.unit_based_model.utils.paths import RAW_DATA_DIR

class ParseMyDataset(ParseData):
    def parse_data(self, day=None) -> Scenario:
        path = RAW_DATA_DIR / "my_dataset"  # folder with your raw files

        # --- Sellers ---
        df_sellers = pd.read_csv(path / "sellers.csv")
        # ensure required columns exist / are computed
        # e.g., build block columns size1..sizeK and cost1..costK

        # --- Buyers ---
        df_buyers = pd.read_csv(path / "buyers.csv")
        # compute inelastic_dem, val*, max_dem, etc.

        # --- Network ---
        network = nx.read_edgelist(path / "network.csv", delimiter=",", nodetype=str)
        # For DCOPF add edge attributes B and F_max

        # --- Nodes->agents mapping ---
        nodes_agents = defaultdict(lambda: {"sellers": [], "buyers": []})
        for n, group in df_sellers.groupby("node"):
            nodes_agents[n]["sellers"].extend(sorted(group["seller"].unique()))
        for n, group in df_buyers.groupby("node"):
            nodes_agents[n]["buyers"].extend(sorted(group["buyer"].unique()))

        periods = sorted(df_buyers["period"].unique().tolist())  # or define explicitly
        r_star = str(periods and df_sellers["node"].iloc[0])      # pick a slack bus sensibly
        blocks_buyers = range(1, 1 + 1)   # adjust to your data
        blocks_sellers = range(1, 4 + 1)

        return Scenario("MY_DATASET", df_buyers, df_sellers, network, nodes_agents, periods, blocks_buyers, blocks_sellers, r_star)
```

### Concrete examples (from the repo)

Use these patterns when adapting your own sources:

#### 1. PJM pattern (single-node market with many seller blocks)
* Collapses the network to a single node (pure energy market case).
* Ensures every (seller, period) has a row; missing periods are filled with zeros.
* Uses ``valuations.csv`` to mock buyer valuations.
* See: ``ParsePJM``.

#### 2. ARPA pattern (rich network + 4 seller blocks, 3 buyer blocks)
* Sellers and buyers are read from ``case.json`` (with ``cblocks``), enriched with CSVs.
* Susceptance `B` is computed from resistance/reactance and clamped: `B = Im(1/(R + jX))` with bounds `[0.01, 2]`.
* See: `ParseARPA`.

### Hooking your dataset into `config.json`
1. Add your parser class (e.g., ParseMyDataset) in the `unit_based_model/data/parsing` package.
2. Add your dataset to `enums.py` in the `UnitBased_Datasets` class.
3. Select your dataset in `config.json`.

## Using Your Own Data for the Order-Book-Based Model

Besides the datasets already bundled in APEM, you can run `order_book_based_model` with your own Euphemia-style CSV dataset.
This section describes the expected dataset folder and how to register it.

---

### What APEM expects at runtime

`order_book_based_model` uses `ParseOrderBook` and expects a dataset folder with CSV files that are loaded into a `ZonalScenario`.

Folder location:

```text
apem/order_book_based_model/euphemia/data/datasets/<your_dataset_name>/
```

Required files:

- `periods.csv` with column: `period`
- `step_orders.csv` with columns: `id,t,p,q,zone`
- `block_orders.csv` with columns:
  - `id,block_type,code_prm,p,MAR,zone`
  - plus one quantity column per period: `q1..qT` (matching `periods.csv`)
- `complex_orders.csv` with columns: `id,step_orders,fixed_term,variable_term,condition,load_gradient`
- `complex_step_orders.csv` with columns: `id,complex_order_id,t,p,q,zone`
- `scalable_complex_orders.csv` with columns:
  - `id,step_orders,fixed_term,condition,load_gradient`
  - plus one MAP column per period: `MAP1..MAPT`
- `scalable_step_orders.csv` with columns: `id,scalable_order_id,t,p,q,zone`
- `piecewise_linear_orders.csv` with columns: `id,t,p0,p1,q,zone`

Optional files:

- `zones.csv` with column `zone` (or `z`); if missing, zones are inferred from order tables
- `atc.csv` with columns `from_zone,to_zone,t,cap` (optional: `ramp_up`, `ramp_down`)

Notes:

- `zone` can also be provided as aliases such as `z`, `bidding_zone`, `country`, or `node`; it is normalized to `zone`.
- If you do not use a specific order family (for example complex orders), keep the CSV present with header-only columns.
- If `atc.csv` is omitted, the model runs as a single-zone clearing problem.

### Quick template

Use [`test_3node`](./apem/order_book_based_model/euphemia/data/datasets/test_3node/) as a minimal reference dataset.
Copy the folder structure and replace contents with your own orders/periods/zones/ATC.

### Hooking your dataset into `config.json`

1. Add your dataset entry to [`datasets.py`](./apem/order_book_based_model/euphemia/enums/datasets.py), e.g.:

```python
MY_DATASET = ParseOrderBook(DATA_DIR / "my_dataset", "My Dataset")
```

2. Set `run.market_model` to `order_book_based_model` and choose your dataset under `order_book_based_model.dataset` in [`config.json`](./config.json).
3. Run:

```bash
python main.py
```

For Euphemia internals and run-output details, see
[`apem/order_book_based_model/euphemia/README.md`](./apem/order_book_based_model/euphemia/README.md).
For order-book order-type semantics, see the
[`Order Types Glossary`](./apem/order_book_based_model/euphemia/README.md#order-types-glossary).
