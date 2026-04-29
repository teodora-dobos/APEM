# Using Your Own Datasets

APEM can work with your own data, but not by pointing `config.json` at an arbitrary file path.

The usual workflow is:

1. Put your dataset into the expected folder structure.
2. Register it in the relevant dataset enum.
3. Select that dataset name in [`config.json`](https://github.com/teodora-dobos/APEM/blob/main/config.json).

## Two Ways To Add Data

The setup depends on which market workflow you want to run.

- Use a **unit-based dataset** if your data describes generators, buyers, and a network.
- Use an **order-book dataset** if your data is already in Euphemia-style order tables.

## Option 1: Add A Unit-Based Dataset

For the unit-based workflow, APEM loads data through parser classes that return a `Scenario`.

### Step 1: Add your raw data

Place your files under:

```text
apem/unit_based_model/data/raw_data/<your_dataset_name>/
```

### Step 2: Create a parser

Add a parser class in `apem/unit_based_model/data/parsing/` that subclasses `ParseData` and returns a `Scenario`.

Your parser should build and return one `Scenario` object.

::::{grid} 1 1 2 2
:::{grid-item-card} {bdg-primary}`Required` Scenario Pieces
`df_sellers`, `df_buyers`, `network`, `nodes_agents`,
`periods`, `blocks_buyers`, `blocks_sellers`, `r_star`.
:::
:::{grid-item-card} {bdg-info}`Recommended` Defaults
- Keep periods indexed as `1..T`.
- Start with `DCOPF` when adding a new unit-based dataset.
- Use one row per `(agent, period)` in buyers/sellers tables.
:::
::::

#### Parser Output Contract

::::{tab-set}
:::{tab-item} `df_sellers`
`df_sellers` {bdg-primary}`Required`

One row per `(seller, period)`.

| column | type | required | meaning | example |
|---|---|---|---|---|
| `seller` | str/int | yes | Seller (unit) id. | `101` |
| `period` | int | yes | Time index. | `1` |
| `node` | str/int | yes | Network node where seller is located. | `N1` |
| `max_prod` | float | yes | Available production in period. | `120.0` |
| `min_prod` | float | yes | Minimum stable production. | `20.0` |
| `min_uptime` | int | yes | Minimum up-time. | `2` |
| `no_load_cost` | float | yes | Fixed no-load cost. | `30.0` |
| `size1..sizeK` | float | yes | Seller bid-block quantities. | `size1=40` |
| `cost1..costK` | float | yes | Seller bid-block prices/costs. | `cost1=25` |

```text
seller,period,node,max_prod,min_prod,min_uptime,no_load_cost,size1,cost1,size2,cost2
101,1,N1,120,20,2,30,40,25,80,40
```
:::

:::{tab-item} `df_buyers`
`df_buyers` {bdg-primary}`Required`

One row per `(buyer, period)`.

| column | type | required | meaning | example |
|---|---|---|---|---|
| `buyer` | str/int | yes | Buyer id. | `B1` |
| `period` | int | yes | Time index. | `1` |
| `node` | str/int | yes | Network node where buyer is located. | `N2` |
| `inelastic_dem` | float | yes | Must-serve demand. | `50.0` |
| `size1..sizeL` | float | yes | Buyer bid-block quantities. | `size1=20` |
| `val1..valL` | float | yes | Buyer bid-block valuations. | `val1=200` |
| `max_dem` | float | yes | Total demand cap (`inelastic_dem + sum(size*)`). | `70.0` |

```text
buyer,period,node,inelastic_dem,size1,val1,max_dem
B1,1,N2,50,20,200,70
```
:::

:::{tab-item} `network`
`network` {bdg-primary}`Required`

Type: `networkx.Graph`.

| element | required | meaning | example |
|---|---|---|---|
| node ids | yes | Must match nodes used in buyers/sellers tables. | `N1`, `N2` |
| edge attr `B` | yes for `DCOPF` | Line susceptance. | `7.5` |
| edge attr `F_max` | yes for `DCOPF` | Line capacity limit. | `100` |

For single-node market data, a graph with one node is valid.
:::

:::{tab-item} Other Scenario Fields
`nodes_agents`, `periods`, `blocks_*`, `r_star` {bdg-primary}`Required`

| field | type | required | meaning | example |
|---|---|---|---|---|
| `nodes_agents` | `dict` | yes | `node -> {"sellers": [...], "buyers": [...]}` | `{"N1": {"sellers": [101], "buyers": []}}` |
| `periods` | `list[int]` | yes | Period list used by the model. | `[1,2,...,24]` |
| `blocks_buyers` | `range` | yes | Buyer block index set. | `range(1, 3+1)` |
| `blocks_sellers` | `range` | yes | Seller block index set. | `range(1, 4+1)` |
| `r_star` | str/int | yes | Reference/slack node. | `N1` |
:::
::::

Use this parser skeleton:

```python
from collections import defaultdict

import networkx as nx
import pandas as pd

from apem.unit_based_model.data.parsing.parse_data import ParseData
from apem.unit_based_model.data.parsing.scenario import Scenario
from apem.unit_based_model.utils.paths import RAW_DATA_DIR


class ParseMyDataset(ParseData):
    def parse_data(self, day=None) -> Scenario:
        path = RAW_DATA_DIR / "my_dataset"

        # 1) Read and normalize sellers/buyers.
        df_sellers = pd.read_csv(path / "sellers.csv")
        df_buyers = pd.read_csv(path / "buyers.csv")

        # 2) Build network with DCOPF-required edge attributes.
        network = nx.Graph()
        # network.add_edge(u, v, B=<susceptance>, F_max=<capacity>)

        # 3) Build node -> agents mapping.
        nodes_agents = defaultdict(lambda: {"sellers": [], "buyers": []})
        for node, group in df_sellers.groupby("node"):
            nodes_agents[node]["sellers"] = sorted(group["seller"].unique().tolist())
        for node, group in df_buyers.groupby("node"):
            nodes_agents[node]["buyers"] = sorted(group["buyer"].unique().tolist())

        periods = sorted(df_buyers["period"].unique().tolist())
        blocks_buyers = range(1, 3 + 1)   # replace 3 with your buyer block count
        blocks_sellers = range(1, 4 + 1)  # replace 4 with your seller block count
        r_star = df_sellers.iloc[0]["node"]

        return Scenario(
            "MY_DATASET",
            df_buyers,
            df_sellers,
            network,
            nodes_agents,
            periods,
            blocks_buyers,
            blocks_sellers,
            r_star,
        )
```

Before registering the dataset, verify:

- period indices are consistent across buyers and sellers (prefer `1..T`)
- each `(seller, period)` and `(buyer, period)` combination expected by your model is present
- each `node` in buyers/sellers exists in `network`
- `blocks_buyers` and `blocks_sellers` match the number of `size*`/`val*`/`cost*` columns
- `max_dem` is correctly computed

Useful references in the repo:

- [`apem/unit_based_model/data/parsing/parse_pjm.py`](https://github.com/teodora-dobos/APEM/blob/main/apem/unit_based_model/data/parsing/parse_pjm.py)
- [`apem/unit_based_model/data/parsing/parse_arpa.py`](https://github.com/teodora-dobos/APEM/blob/main/apem/unit_based_model/data/parsing/parse_arpa.py)

### Step 3: Register the dataset

Add your parser to [`apem/unit_based_model/enums/datasets.py`](https://github.com/teodora-dobos/APEM/blob/main/apem/unit_based_model/enums/datasets.py), following the existing pattern:

```python
class UnitBased_Datasets(Enum):
    ...
    MY_DATASET = ParseMyDataset()
```

### Step 4: Select it in `config.json`

```json
{
  "run": {
    "market_model": "unit_based_model"
  },
  "unit_based_model": {
    "dataset": "MY_DATASET",
    "power_flow_model": { "type": "DCOPF" },
    "pricing_algorithm": "ELMP"
  }
}
```

### Limitation

For a **new custom unit-based dataset**, the safe supported choice is `DCOPF`.

More precisely:

- your custom dataset can be used in the unit-based workflow with `DCOPF`
- your custom dataset cannot currently be used with the zonal power-flow models `Zonal_NTC_aggregated`, `Zonal_NTC_multiedge`, or `Zonal_FBMC`
- redispatch is part of those zonal workflows, so it is also not available for a new custom unit-based dataset

```{note}
At the moment, the zonal unit-based workflows are only supported for the two built-in PyPSA datasets: `PyPSAEurSmall` and `PyPSAEurLarge`.
```

#### What would be needed for zonal support on a new dataset?

To make a new unit-based dataset work with zonal models, it is not enough to only add a parser.

You would also need to:

- provide node coordinates so APEM can map nodes to zones
- define or extend the zonal mapping logic for your geography
- ensure the dataset contains the network information needed to aggregate a nodal network into a zonal one
- remove the current PyPSA-only restrictions in the zonal execution path
- test the full zonal workflow, including allocation, pricing, and redispatch

In other words, adding a new dataset for `DCOPF` is mostly a data-integration task, while adding a new dataset for zonal models also requires extending the current zonal-model implementation.

## Option 2: Add An Order-Book Dataset

For the order-book workflow, APEM expects a Euphemia-style dataset folder made of CSV files.
In most cases, you do not write a new parser class: you use `ParseOrderBook` and provide the expected files.

### Step 1: Add the dataset folder

Place your dataset under:

```text
apem/order_book_based_model/euphemia/data/datasets/<your_dataset_name>/
```

`ParseOrderBook` reads fixed filenames and builds a `ZonalScenario` from them.
Use the contracts below.

::::{grid} 1 1 2 2
:::{grid-item-card} {bdg-primary}`Required` Core Dataset
You must provide:
`periods.csv`, `step_orders.csv`, `block_orders.csv`,
`complex_orders.csv`, `complex_step_orders.csv`,
`scalable_complex_orders.csv`, `scalable_step_orders.csv`,
`piecewise_linear_orders.csv`.
:::
:::{grid-item-card} {bdg-secondary}`Optional` Network + Zones
You can add:
`zones.csv`, `atc.csv`, `fb_constraints.csv`, `fb_ptdf.csv`.

If omitted or empty, network constraints may be disabled and the model can fall back to unconstrained single-zone clearing.
:::
::::

```{note}
If you do not use one order family (for example complex orders), keep that CSV as a header-only file with the expected columns.
```

#### File Specifications

::::{tab-set}
:::{tab-item} Core
`periods.csv` {bdg-primary}`Required`

| column | type | required | meaning | example |
|---|---|---|---|---|
| `period` | int | yes | Market period index. | `1` |

```text
period
1
2
```

`step_orders.csv` {bdg-primary}`Required`

| column | type | required | meaning | example |
|---|---|---|---|---|
| `id` | str/int | yes | Unique step-order id. | `S1` |
| `t` | int | yes | Period index (must exist in `periods.csv`). | `1` |
| `p` | float | yes | Limit price. | `75.0` |
| `q` | float | yes | Quantity (`q>0` sell, `q<0` buy). | `-20.0` |
| `zone` | str | yes | Bidding zone. Aliases accepted: `z`, `bidding_zone`, `country`, `node`. | `Z1` |

```text
id,t,p,q,zone
S1,1,75,-20,Z1
S2,1,25,30,Z2
```

`block_orders.csv` {bdg-primary}`Required`

| column | type | required | meaning | example |
|---|---|---|---|---|
| `id` | str/int | yes | Unique block id. | `B1` |
| `block_type` | str | yes | `normal`, `exclusive`, `linked`, `flexible`. | `normal` |
| `code_prm` | str/int | conditional | Group/parent code (`exclusive`/`linked`). | `GRP_A` |
| `p` | float | yes | Block price. | `90` |
| `q1..qT` | float | yes | Per-period quantities, matching `periods.csv`. | `q1=-10` |
| `MAR` | float | yes | Minimum acceptance ratio (0..1). | `1` |
| `zone` | str | yes | Bidding zone. Same aliases as step orders are accepted. | `Z3` |

```text
id,block_type,code_prm,p,q1,q2,MAR,zone
B1,normal,,500,-10,-10,1,Z3
```
:::

:::{tab-item} Complex Orders
`complex_orders.csv` {bdg-primary}`Required`

| column | type | required | meaning | example |
|---|---|---|---|---|
| `id` | str/int | yes | Complex parent id. | `C1` |
| `step_orders` | str | yes | Comma-separated child step ids. | `CS1,CS2` |
| `fixed_term` | float | yes | Fixed MIC/MP term. | `100` |
| `variable_term` | float | yes | Variable MIC/MP term (complex orders). | `5` |
| `condition` | str | yes | Typical values: `MIC`, `MP`, `load gradient`. | `MIC` |
| `load_gradient` | float/empty | yes | Ramp-like limit if used. | `200` |

```text
id,step_orders,fixed_term,variable_term,condition,load_gradient
C1,"CS1,CS2",100,5,MIC,
```

`complex_step_orders.csv` {bdg-primary}`Required`

| column | type | required | meaning | example |
|---|---|---|---|---|
| `id` | str/int | yes | Complex-step id. | `CS1` |
| `complex_order_id` | str/int | yes | Parent id in `complex_orders.id`. | `C1` |
| `t` | int | yes | Period index. | `1` |
| `p` | float | yes | Step price. | `60` |
| `q` | float | yes | Step quantity. | `30` |
| `zone` | str | yes | Zone (aliases accepted). | `Z1` |

```text
id,complex_order_id,t,p,q,zone
CS1,C1,1,60,30,Z1
CS2,C1,2,65,25,Z1
```
:::

:::{tab-item} Scalable Complex
`scalable_complex_orders.csv` {bdg-primary}`Required`

| column | type | required | meaning | example |
|---|---|---|---|---|
| `id` | str/int | yes | Scalable parent id. | `SC1` |
| `step_orders` | str | yes | Comma-separated scalable step ids. | `SS1,SS2` |
| `fixed_term` | float | yes | Fixed term. | `0` |
| `condition` | str | yes | Typical values: `MIC`, `MP`, `load gradient`. | `MIC` |
| `load_gradient` | float/empty | yes | Gradient limit if used. | `150` |
| `MAP1..MAPT` | float | yes | Period-wise minimum acceptance profile. | `MAP1=10` |

```text
id,step_orders,fixed_term,condition,load_gradient,MAP1,MAP2
SC1,"SS1,SS2",0,MIC,,10,10
```

`scalable_step_orders.csv` {bdg-primary}`Required`

| column | type | required | meaning | example |
|---|---|---|---|---|
| `id` | str/int | yes | Scalable-step id. | `SS1` |
| `scalable_order_id` | str/int | yes | Parent id in `scalable_complex_orders.id`. | `SC1` |
| `t` | int | yes | Period index. | `1` |
| `p` | float | yes | Step price. | `55` |
| `q` | float | yes | Step quantity. | `20` |
| `zone` | str | yes | Zone (aliases accepted). | `Z2` |

```text
id,scalable_order_id,t,p,q,zone
SS1,SC1,1,55,20,Z2
SS2,SC1,2,58,20,Z2
```
:::

:::{tab-item} Piecewise Linear
`piecewise_linear_orders.csv` {bdg-primary}`Required`

| column | type | required | meaning | example |
|---|---|---|---|---|
| `id` | str/int | yes | PLO id. | `P1` |
| `t` | int | yes | Period index. | `1` |
| `p0` | float | yes | Start price. | `20` |
| `p1` | float | yes | End price. | `80` |
| `q` | float | yes | Quantity (`q>0` sell, `q<0` buy). | `15` |
| `zone` | str | yes | Zone (aliases accepted). | `Z1` |

```text
id,t,p0,p1,q,zone
P1,1,20,80,15,Z1
```
:::

:::{tab-item} Network + Zones
`zones.csv` {bdg-secondary}`Optional`

| column | type | required | meaning | example |
|---|---|---|---|---|
| `zone` | str | no | Explicit zone list. If missing, zones are inferred. | `Z1` |

Aliases accepted: `z`, or first column fallback.

```text
zone
Z1
Z2
```

`atc.csv` {bdg-secondary}`Optional` {bdg-info}`ATC`

| column | type | required | meaning | example |
|---|---|---|---|---|
| `from_zone` | str | yes | Source zone. | `Z1` |
| `to_zone` | str | yes | Sink zone. | `Z2` |
| `t` | int | yes | Period index. | `1` |
| `cap` | float | yes | Directed transfer capacity. | `400` |
| `ramp_up` | float | no | Inter-temporal upward ramp bound. | `50` |
| `ramp_down` | float | no | Inter-temporal downward ramp bound. | `50` |

Aliases accepted:
`from/to`, `source_zone/sink_zone`, `period/time`, `capacity/atc`.

```text
from_zone,to_zone,t,cap
Z1,Z2,1,400
Z2,Z1,1,400
```

`fb_constraints.csv` {bdg-secondary}`Optional` {bdg-info}`FBMC`

| column | type | required | meaning | example |
|---|---|---|---|---|
| `cnec_id` | str | yes | CNEC identifier. | `NP_Z1` |
| `t` | int | yes | Period index. | `1` |
| `ram` | float | yes | Remaining available margin (upper bound). | `800` |
| `lb` | float | no | Optional lower bound. | `-800` |

Aliases accepted:
`cnec`, `constraint_id`, `period/time`, `capacity`; lower bound aliases `ram_lb`, `min_ram`.

```text
cnec_id,t,ram,lb
NP_Z1,1,800,-800
```

`fb_ptdf.csv` {bdg-secondary}`Optional` {bdg-info}`FBMC`

| column | type | required | meaning | example |
|---|---|---|---|---|
| `cnec_id` | str | yes | CNEC identifier. | `NP_Z1` |
| `t` | int | yes | Period index. | `1` |
| `zone` | str | yes | Zone label. | `Z1` |
| `ptdf` | float | yes | PTDF coefficient for `(cnec, t, zone)`. | `1.0` |

Aliases accepted:
`cnec`, `constraint_id`, `period/time`, `z/bidding_zone`, `value/factor`.

```text
cnec_id,t,zone,ptdf
NP_Z1,1,Z1,1.0
NP_Z1,1,Z2,0.0
```
:::
::::

#### Network Model Mapping

- `network_model = "ATC"`: uses `atc.csv` for multi-zone transfer constraints.
- `network_model = "FBMC"`: uses `fb_constraints.csv` + `fb_ptdf.csv`.
- If required network files are missing or empty, APEM can run with unconstrained single-zone clearing.

#### Validation Checklist

- `periods.csv` contains integers and every `t` in every orders file belongs to `periods`.
- `block_orders.csv` contains all `q1..qT` columns for defined periods.
- `scalable_complex_orders.csv` contains all `MAP1..MAPT` columns for defined periods.
- Linked blocks are valid: each `linked` block has `code_prm` pointing to an existing parent `id`.
- `complex_step_orders.complex_order_id` references existing `complex_orders.id`.
- `scalable_step_orders.scalable_order_id` references existing `scalable_complex_orders.id`.

#### Quick Start

- Copy [`apem/order_book_based_model/euphemia/data/datasets/test_3node/`](https://github.com/teodora-dobos/APEM/tree/main/apem/order_book_based_model/euphemia/data/datasets/test_3node).
- Replace CSV contents while keeping filenames and headers.

### Step 2: Register the dataset

Add your dataset to [`apem/order_book_based_model/euphemia/enums/datasets.py`](https://github.com/teodora-dobos/APEM/blob/main/apem/order_book_based_model/euphemia/enums/datasets.py):

```python
from enum import Enum

from apem.order_book_based_model.euphemia.data.parsing.parse_order_book import ParseOrderBook
from apem.order_book_based_model.euphemia.utils.paths import DATA_DIR


class OrderBookBased_Datasets(Enum):
    ...
    MY_DATASET = ParseOrderBook(DATA_DIR / "my_dataset", "My Dataset")
```

### Step 3: Select it in `config.json`

```json
{
  "run": {
    "market_model": "order_book_based_model"
  },
  "order_book_based_model": {
    "dataset": "MY_DATASET",
    "cut_type": "price based",
    "euphemia_configuration": {
      "network_model": "FBMC"
    }
  }
}
```

## Summary

- `config.json` only selects datasets that APEM already knows about.
- To use your own data, you first register it in code.
- For unit-based data, you add a parser returning a `Scenario`.
- For order-book data, you add a dataset folder and register it with `ParseOrderBook`.
