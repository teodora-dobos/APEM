# Market Scores

Market-output scoring functions, including PTDF construction and node-level
scores from dispatch, prices, and congestion duals.

## Score Definitions

The table below introduces the notation used throughout the market-based
scores.

```{eval-rst}
.. list-table::
   :header-rows: 1

   * - Symbol
     - Meaning
   * - :math:`g`
     - Generator
   * - :math:`v`
     - Node
   * - :math:`G(v)`
     - Set of generators connected to node :math:`v`
   * - :math:`d_g`
     - Dispatch of generator :math:`g`
   * - :math:`c_g`
     - Marginal cost of generator :math:`g`
   * - :math:`\lambda_v`
     - Nodal price at node :math:`v`
   * - :math:`\gamma_g`
     - Generator-capacity dual value
   * - :math:`P_g^{\max}`
     - Maximum capacity of generator :math:`g`
   * - :math:`L_v`
     - Load at node :math:`v`
   * - :math:`\mu_{vw}^{+}, \mu_{vw}^{-}`
     - Congestion duals on line :math:`(v,w)`
   * - :math:`F_{vw}^{\max}`
     - Capacity of line :math:`(v,w)`
   * - :math:`\delta(v)`
     - Set of lines incident to node :math:`v`
   * - :math:`\mathrm{PTDF}_{\ell,v}`
     - PTDF coefficient of line :math:`\ell` with respect to node :math:`v`
   * - :math:`m_\ell`
     - Residual margin on line :math:`\ell`
   * - :math:`\varepsilon`
     - Small positive constant to avoid division by zero
```

The main market-based scores are summarized below.

```{eval-rst}
.. list-table::
   :header-rows: 1
   :widths: 24 46 30

   * - Score
     - Definition
     - Interpretation
   * - Rent-Weighted Dispatch
     - :math:`s_g = \max(0, \lambda_{n(g)} - c_g)d_g,\quad S_v = \sum_{g \in G(v)} s_g`
     - Rewards nodes whose dispatched generators earn positive margin at the baseline prices.
   * - Dispatch Volume
     - :math:`S_v = \sum_{g \in G(v)} d_g`
     - Measures how much generation is dispatched at each node.
   * - Gamma-Capacity
     - :math:`s_g = \gamma_g P_g^{\max},\quad S_v = \sum_{g \in G(v)} s_g`
     - Emphasizes nodes with generators that are scarce in the baseline solution.
   * - Gamma-Capacity-Congestion
     - :math:`S_v = \sum_{g \in G(v)} \gamma_g P_g^{\max} + \sum_{(v,w) \in \delta(v)} F_{vw}^{\max}(\mu_{vw}^{+} + \mu_{vw}^{-})`
     - Combines generator scarcity with congestion on adjacent lines.
   * - Load-Weighted LMP
     - :math:`S_v = \lambda_v L_v`, or :math:`S_v = \min(\lambda_v, \mathrm{VOLL})L_v` when capping is used
     - Highlights nodes where high prices coincide with high demand.
   * - PTDF Stress
     - :math:`S_v = \left(\sum_{g \in G(v)} P_g^{\max}\right)\sum_{\ell}\frac{|\mathrm{PTDF}_{\ell,v}|}{m_\ell + \varepsilon}`
     - Captures how strongly a node's installed capacity is exposed to tight transmission constraints.
```

API path: `node_ranking.market_scores`

```{eval-rst}
.. automodule:: node_ranking.market_scores
   :members:
   :show-inheritance:
```
