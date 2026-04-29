from typing import TYPE_CHECKING

import gurobipy as gp
from gurobipy import GRB

from apem.order_book_based_model.euphemia.utils.extraction import get

if TYPE_CHECKING:
    from apem.order_book_based_model.euphemia.master_problem.master_problem import MasterProblem


def add_objective(self: "MasterProblem") -> None:
    """Define the surplus-maximizing objective of the master problem.

    The objective aggregates the contribution of every supported order family:
    step orders, block orders, complex-order step rows, scalable-complex step
    rows, and piecewise-linear orders. The final model objective is posted as a
    maximization of total economic surplus using the sign conventions already
    encoded in the parsed bid tables.

    :param self: Active Euphemia master-problem instance whose Gurobi model is
        being populated.
    :return: ``None``.
    """

    # 1) step orders
    step_orders_obj = gp.quicksum(
        self.accept_step[i] * get(self.step_orders, 'q', i) * get(self.step_orders, 'p', i)
        for i in list(self.step_orders['id']))

    # 3) block orders
    block_orders_obj = gp.quicksum(
        self.accept_block[i] * gp.quicksum(get(self.block_orders, f'q{t}', i) for t in self.periods) *
        get(self.block_orders, 'p', i)
        for i in list(self.block_orders['id']))

    # 4) complex orders - consider step suborders
    complex_orders_obj = gp.quicksum(
        self.accept_complex_step[i] * get(self.complex_step_orders, 'q', i) * get(self.complex_step_orders, 'p', i)
        for i in list(self.complex_step_orders['id']))

    # 5) scalable complex orders
    scalable_orders_obj = gp.quicksum(
        self.accept_scalable_step[i] * get(self.scalable_step_orders, 'q', i) *
        get(self.scalable_step_orders, 'p', i) for i in list(self.scalable_step_orders['id']))

    # 6) piecewise linear orders
    piecewise_linear_orders_obj = gp.quicksum(
        self.accept_piecewise_linear[i] * get(self.piecewise_linear_orders, 'q', i) *
        (
                get(self.piecewise_linear_orders, 'p0', i) +
                self.accept_piecewise_linear[i] *
                (get(self.piecewise_linear_orders, 'p1', i)
                 - get(self.piecewise_linear_orders, 'p0', i))
                / 2)
        for i in list(self.piecewise_linear_orders['id']))

    self.model.setObjective(
        -step_orders_obj - block_orders_obj - complex_orders_obj - scalable_orders_obj - piecewise_linear_orders_obj,
        GRB.MAXIMIZE)


def add_market_constraints(self: "MasterProblem") -> None:
    """Add market-clearing and order-linking constraints to the master problem.

    This routine builds the core allocation structure of the Euphemia master
    problem. It enforces:

    - market balance for the active network representation
    - block-order acceptance logic including MAR, exclusive, linked, and
      flexible blocks
    - linkage between parent complex/scalable-complex orders and their step
      rows
    - load-gradient and MAP restrictions for complex-order variants

    Balance is formulated differently depending on the current network mode:

    - no network constraints: one global balance equation per period
    - ``ATC``: zonal injection balanced with directed interconnector flows
    - ``FBMC``: zonal net-position definitions plus global balance

    :param self: Active Euphemia master-problem instance whose Gurobi model is
        being populated.
    :return: ``None``.
    """

    def order_zone(df, order_id):
        if "zone" not in df.columns:
            return self.default_zone
        return self.resolve_zone(get(df, "zone", order_id))

    def zonal_injection(z, t):
        return (
            gp.quicksum(
                self.accept_step[i] * get(self.step_orders, "q", i)
                for i in list(self.step_orders["id"])
                if get(self.step_orders, "t", i) == t and order_zone(self.step_orders, i) == z
            )
            + gp.quicksum(
                self.accept_block[i] * get(self.block_orders, f"q{t}", i)
                for i in list(self.block_orders["id"])
                if get(self.block_orders, "block_type", i) != "flexible" and order_zone(self.block_orders, i) == z
            )
            + gp.quicksum(
                self.accept_block[i] * self.flex_period[i, t] * get(self.block_orders, f"q{t}", i)
                for i in list(self.block_orders["id"])
                if get(self.block_orders, "block_type", i) == "flexible" and order_zone(self.block_orders, i) == z
            )
            + gp.quicksum(
                self.accept_complex_step[i] * get(self.complex_step_orders, "q", i)
                for i in list(self.complex_step_orders["id"])
                if get(self.complex_step_orders, "t", i) == t and order_zone(self.complex_step_orders, i) == z
            )
            + gp.quicksum(
                self.accept_scalable_step[i] * get(self.scalable_step_orders, "q", i)
                for i in list(self.scalable_step_orders["id"])
                if get(self.scalable_step_orders, "t", i) == t and order_zone(self.scalable_step_orders, i) == z
            )
            + gp.quicksum(
                self.accept_piecewise_linear[i] * get(self.piecewise_linear_orders, "q", i)
                for i in list(self.piecewise_linear_orders["id"])
                if get(self.piecewise_linear_orders, "t", i) == t and order_zone(self.piecewise_linear_orders, i) == z
            )
        )

    if not self.network_constraints_enabled:
        # single-zone market clearing
        self.model.addConstrs(
            (gp.quicksum(self.accept_step[i] * get(self.step_orders, 'q', i)
                         for i in list(self.step_orders['id']) if get(self.step_orders, 't', i) == t) +
             gp.quicksum(self.accept_block[i] * get(self.block_orders, f'q{t}', i)
                         for i in list(self.block_orders['id']) if get(self.block_orders, 'block_type', i) != 'flexible') +
             gp.quicksum(self.accept_block[i] * self.flex_period[i, t] * get(self.block_orders, f'q{t}', i)
                         for i in list(self.block_orders['id']) if get(self.block_orders, 'block_type', i) == 'flexible') +
             gp.quicksum(self.accept_complex_step[i] * get(self.complex_step_orders, 'q', i)
                         for i in list(self.complex_step_orders['id']) if get(self.complex_step_orders, 't', i) == t) +
             gp.quicksum(self.accept_scalable_step[i] * get(self.scalable_step_orders, 'q', i)
                         for i in list(self.scalable_step_orders['id']) if get(self.scalable_step_orders, 't', i) == t) +
             gp.quicksum(self.accept_piecewise_linear[i] * get(self.piecewise_linear_orders, 'q', i) for i in
                         list(self.piecewise_linear_orders['id']) if get(self.piecewise_linear_orders, 't', i) == t)
             == 0
             for t in self.periods), name='power_balance')
    elif self.network_model == "ATC":
        # zonal market clearing with directed ATC flows
        self.model.addConstrs(
            (
                zonal_injection(z, t)
                - gp.quicksum(
                    self.f_atc[i, j, tt] for (i, j, tt) in self.atc_index if i == z and tt == t
                )
                + gp.quicksum(
                    self.f_atc[i, j, tt] for (i, j, tt) in self.atc_index if j == z and tt == t
                )
                == 0
                for z in self.zones
                for t in self.periods
            ),
            name="zonal_power_balance",
        )
    else:
        # FBMC zonal net positions linked to accepted quantities
        self.model.addConstrs(
            (
                self.net_position[z, t] == zonal_injection(z, t)
                for z in self.zones
                for t in self.periods
            ),
            name="fbmc_net_position_def",
        )
        self.model.addConstrs(
            (gp.quicksum(self.net_position[z, t] for z in self.zones) == 0 for t in self.periods),
            name="fbmc_global_balance",
        )

    # block order acceptance
    # accept_block[i] = 0 or accept_block[i] >= MAR
    self.model.addConstrs(
        self.accept_block[i] >= get(self.block_orders, 'MAR', i) * self.MAR_aux[i] for i in
        list(self.block_orders['id']))

    self.model.addConstrs(self.accept_block[i] <= self.M * self.MAR_aux[i] for i in list(self.block_orders['id']))

    # exclusive groups
    exclusive_groups = list(self.block_orders[self.block_orders['block_type'] == 'exclusive']['code_prm'])
    exclusive_blocks = list(self.block_orders[self.block_orders['block_type'] == 'exclusive']['id'])

    self.model.addConstrs(
        gp.quicksum(
            self.MAR_aux[i] for i in exclusive_blocks if get(self.block_orders, 'code_prm', i) == eg) <= 1
        for eg in exclusive_groups)

    # linked blocks
    linked_blocks = list(self.block_orders[self.block_orders['block_type'] == 'linked']['id'])
    block_to_parent = {i: get(self.block_orders, 'code_prm', i) for i in linked_blocks}

    self.model.addConstrs(self.accept_block[i] <= self.accept_block[block_to_parent[i]] for i in linked_blocks)

    # flexible blocks
    flexible_blocks = list(self.block_orders[self.block_orders['block_type'] == 'flexible']['id'])
    self.model.addConstrs(self.accept_block[i] == gp.quicksum(self.flex_period[i, t] for t in self.periods)
                          for i in flexible_blocks)

    # complex orders
    complex_step_orders = list(self.complex_step_orders['id'])

    self.model.addConstrs(
        self.accept_complex_step[i] <= self.accept_complex[get(self.complex_step_orders, 'complex_order_id', i)]
        for i in complex_step_orders)

    # scalable complex orders
    scalable_step_orders = list(self.scalable_step_orders['id'])

    self.model.addConstrs(
        self.accept_scalable_step[i] <= self.accept_scalable[get(self.scalable_step_orders, 'scalable_order_id', i)]
        for i in scalable_step_orders)

    # load gradient condition
    # complex orders
    load_gradient_complex_ids = self.complex_orders.loc[self.complex_orders['load_gradient'].notna(), 'id'].tolist()

    for i in load_gradient_complex_ids:
        periods_orders = {}
        inc_dec = get(self.complex_orders, 'load_gradient', i)
        for t in self.periods:
            # for a specific complex order sum over all associated step orders from the current period
            orders_i_t = self.complex_step_orders.loc[
                (self.complex_step_orders['complex_order_id'] == i) & (
                        self.complex_step_orders['t'] == t), 'id'].tolist()

            periods_orders[t] = gp.quicksum(
                self.accept_complex_step[j] * abs(get(self.complex_step_orders, 'q', j)) for j in orders_i_t)

        self.model.addConstrs(
            periods_orders[t] - periods_orders[t - 1] <= inc_dec * self.accept_complex[i] for t in
            self.periods[1:])
        self.model.addConstrs(
            periods_orders[t - 1] - periods_orders[t] <= inc_dec * self.accept_complex[i] for t in
            self.periods[1:])

    # scalable complex orders
    load_gradient_scalable_ids = self.scalable_complex_orders.loc[
        self.scalable_complex_orders['load_gradient'].notna(), 'id'].tolist()

    for i in load_gradient_scalable_ids:
        periods_orders = {}
        inc_dec = get(self.scalable_complex_orders, 'load_gradient', i)
        for t in self.periods:
            orders_i_t = self.scalable_step_orders.loc[
                (self.scalable_step_orders['scalable_order_id'] == i) & (
                        self.scalable_step_orders['t'] == t), 'id'].tolist()

            periods_orders[t] = gp.quicksum(
                self.accept_scalable_step[j] * abs(get(self.scalable_step_orders, 'q', j)) for j in orders_i_t)

        self.model.addConstrs(
            periods_orders[t] - periods_orders[t - 1] <= inc_dec * self.accept_scalable[i] for t in
            self.periods[1:])
        self.model.addConstrs(
            periods_orders[t - 1] - periods_orders[t] <= inc_dec * self.accept_scalable[i] for t in
            self.periods[1:])

        # MAP
        self.model.addConstrs(
            periods_orders[t] >= get(self.scalable_complex_orders, f'MAP{t}', i) * self.accept_scalable[i]
            for t in self.periods)

    # MAP for scalable complex orders that do not have the load gradient condition
    for i in self.scalable_complex_orders['id'].tolist():
        if i not in load_gradient_scalable_ids:
            periods_orders = {}
            for t in self.periods:
                orders_i_t = self.scalable_step_orders.loc[
                    (self.scalable_step_orders['scalable_order_id'] == i) & (
                            self.scalable_step_orders['t'] == t), 'id'].tolist()

                periods_orders[t] = gp.quicksum(
                    self.accept_scalable_step[i] * abs(get(self.scalable_step_orders, 'q', i)) for i in orders_i_t)

            self.model.addConstrs(
                periods_orders[t] >= get(self.scalable_complex_orders, f'MAP{t}', i) * self.accept_scalable[i]
                for t in self.periods)

def add_network_constraints(self: "MasterProblem") -> None:
    """Add network feasibility constraints for the selected network model.

    The function is a no-op when ``network_constraints_enabled`` is ``False``.
    Otherwise it complements :func:`add_market_constraints` with the physical
    transmission limits implied by the configured network representation:

    - ``ATC``: capacity bounds on directed interconnectors plus optional
      ramp-up and ramp-down limits between consecutive periods
    - ``FBMC``: PTDF-based upper RAM limits and optional lower-bound limits on
      zonal net positions

    :param self: Active Euphemia master-problem instance whose Gurobi model is
        being populated.
    :return: ``None``.
    """
    if not self.network_constraints_enabled:
        return

    if self.network_model == "ATC":
        # ATC capacity limits for directed interconnectors
        self.model.addConstrs(
            (self.f_atc[i, j, t] <= self.atc_cap[(i, j, t)] for (i, j, t) in self.atc_index),
            name="atc_capacity",
        )

        # Optional directional flow ramping limits
        if self.atc_ramp_up:
            for (i, j), ramp_up in self.atc_ramp_up.items():
                for prev_t, t in zip(self.periods[:-1], self.periods[1:]):
                    if (i, j, prev_t) in self.atc_cap and (i, j, t) in self.atc_cap:
                        self.model.addConstr(
                            self.f_atc[i, j, t] - self.f_atc[i, j, prev_t] <= ramp_up,
                            name=f"atc_ramp_up_{i}_{j}_{t}",
                        )

        if self.atc_ramp_down:
            for (i, j), ramp_down in self.atc_ramp_down.items():
                for prev_t, t in zip(self.periods[:-1], self.periods[1:]):
                    if (i, j, prev_t) in self.atc_cap and (i, j, t) in self.atc_cap:
                        self.model.addConstr(
                            self.f_atc[i, j, prev_t] - self.f_atc[i, j, t] <= ramp_down,
                            name=f"atc_ramp_down_{i}_{j}_{t}",
                        )
        return

    # FBMC PTDF * net_position <= RAM constraints
    self.model.addConstrs(
        (
            gp.quicksum(self.fb_ptdf_map.get((cnec_id, t, z), 0.0) * self.net_position[z, t] for z in self.zones)
            <= self.fb_ram[(cnec_id, t)]
            for (cnec_id, t) in self.fb_index
        ),
        name="fbmc_ram",
    )
    if self.fb_lb:
        self.model.addConstrs(
            (
                gp.quicksum(self.fb_ptdf_map.get((cnec_id, t, z), 0.0) * self.net_position[z, t] for z in self.zones)
                >= self.fb_lb[(cnec_id, t)]
                for (cnec_id, t) in self.fb_index
                if (cnec_id, t) in self.fb_lb
            ),
            name="fbmc_lb",
        )
