import gurobipy as gp
from gurobipy import GRB
import os


from implementation.utils.extraction import get


def add_objective(self) -> None:
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

    # sign(type(sco))FixedTerm_sco B_ACCEPT_sco

    # 7) tariff

    # 8) max curtailment

    self.model.setObjective(-step_orders_obj - block_orders_obj - complex_orders_obj - scalable_orders_obj,
                            GRB.MAXIMIZE)


def add_market_constraints(self) -> None:
    # supply - demand balance
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
                     for i in list(self.scalable_step_orders['id']) if get(self.scalable_step_orders, 't', i) == t)
         == 0
         for t in self.periods), name='power_balance')

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
            self.accept_block[i] for i in exclusive_blocks if get(self.block_orders, 'code_prm', i) == eg) <= 1
        for eg in exclusive_groups)

    # linked blocks
    linked_blocks = list(self.block_orders[self.block_orders['block_type'] == 'linked']['id'])
    block_to_parent = {i: int(get(self.block_orders, 'code_prm', i)) for i in linked_blocks}

    self.model.addConstrs(self.accept_block[i] <= self.accept_block[block_to_parent[i]] for i in linked_blocks)

    # flexible blocks
    flexible_blocks = list(self.block_orders[self.block_orders['block_type'] == 'flexible']['id'])
    self.model.addConstrs(gp.quicksum(self.flex_period[i, t] for t in self.periods) <= 1 for i in flexible_blocks)
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

    self.model.write(os.path.join(self.paths['debug'], f"master_{self.iteration}.lp"))
    self.model.setParam("OutputFlag", 0)


def add_network_constraints(self) -> None:
    # ATC

    # PTDF

    # ramping
    pass