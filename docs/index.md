# APEM: Allocation and Pricing in Electricity Markets

APEM is a research and experimentation framework for electricity-market clearing, pricing, and analysis. It brings together optimization-based market models, pricing methods, network-aware post-processing, and supporting evaluation tools in a single codebase.

```{toctree}
:maxdepth: 1
:caption: Getting Started
:hidden:

introduction
installation
configuration
project_structure
```

```{toctree}
:maxdepth: 3
:caption: API
:hidden:

apem/index
node_ranking/index
```

```{toctree}
:maxdepth: 1
:caption: Workflows
:hidden:

workflows/unit_based_model
workflows/order_book_based_model
```

![Framework overview](_static/framework_overview.png)

## What APEM Includes

APEM is organized around three main modules.

- **APEM Core** is the main modeling framework. It contains the unit-based and order-book-based market workflows, scenario handling, allocation and pricing pipelines, redispatch logic, and evaluation utilities.
- **APEM Node Ranking** is an analysis module for scoring nodes in the network. It combines graph-based indicators with market-based metrics to highlight structurally important, congested, or economically stressed locations.
- **APEM PF Relaxations** is a power-flow-analysis module that groups alternative relaxation formulations, including quadratic convex, semidefinite, and second-order-cone approaches.

APEM also includes built-in datasets for both modeling workflows.

## What The Framework Does

At a high level, APEM supports the full path from input data to interpretable market results.

1. It parses market and network data from supported datasets and converts them into model-ready scenarios.
2. It solves an allocation or market-clearing problem using the workflow that matches the chosen market representation.
3. It computes prices with interchangeable pricing rules and pricing algorithms.
4. It evaluates outcomes such as dispatch, prices, congestion effects, redispatch costs, and node-level importance metrics.

## Two Main Modeling Workflows

### Unit-Based Model

In a unit-based model, bids are tied to physical generation units. The market sees individual plants together with their technical and economic characteristics, such as capacity, marginal cost, and operational limits.

This is a bottom-up representation: the workflow starts from physical assets, builds market bids from them, and then solves allocation, pricing, and redispatch problems on top of that representation.

The unit-based workflow is the part of the framework used for questions such as:

- How does a market clear under nodal or zonal representations?
- How do different zonal clearing approaches affect welfare, prices, and redispatch?
- How do pricing rules such as Integer Programming (`IP`) and Extended Locational Marginal Pricing (`ELMP`) change the final price signals?

### Order-Book-Based Model

In an order-book-based model, the market is represented through buy and sell orders rather than explicit plant identities. The market sees prices, quantities, and order structures such as step orders, block orders, complex orders, and scalable orders, but not the full physical detail behind each bid.

This is a top-down representation: the workflow starts from the submitted order book and clears the market from those bids, which makes it closer to how exchange-based European day-ahead markets are actually represented.

In APEM, this workflow is implemented as a simplified simulation of the EUPHEMIA algorithm ([EUPHEMIA Public Description](https://www.nemo-committee.eu/assets/files/euphemia-public-description.pdf)).

The order-book workflow is useful when you want to study:

- bid-based market clearing behavior,
- the interaction between accepted orders and feasible prices,
- reinsertion and decomposition strategies in Euphemia-style market formulations.

## Additional Analysis Modules

Beyond the two main market models included in APEM Core, APEM includes two analysis-focused modules.

- **Node Ranking** combines structural network metrics such as degree centrality, betweenness centrality, and PTDF contribution with market-oriented scores such as rent-weighted dispatch, dispatch volume, gamma-capacity, load-weighted LMP, and PTDF stress.
- **PF Relaxations** groups alternative relaxations including quadratic convex, semidefinite programming, and second-order cone programming approaches for power-flow-related studies.

## How To Read This Documentation

Use the sidebar to move between the main parts of the project:

- start with the conceptual and setup pages if you are new to the repository,
- move into the API pages if you want module-level details,
- use the workflow pages and example scripts if you want runnable entry points and experiment patterns.
