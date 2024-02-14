import gurobipy as gp
from gurobipy import *

class Euphemia(object):

    def __init__(self, hourly_orders, block_orders):
        self.hourly_orders = hourly_orders
        self.block_orders = block_orders
        self.nbuy = len(hourly_orders['buy'])
        self.nsell = len(hourly_orders['sell'])
        self.nblock = len(block_orders['blocks'])
        self.model = gp.Model("euphemia")
        self.rejected_bo_constrs = []
        self.i = 1
        self.test = []

    def run_milp(self):
        self.add_variables()
        self.add_constraints()
        self.set_objective()
        while self.i > 0:
            self.model.reset(1)
            self.optimize()
            self.determine_clearing_prices()
            self.determine_paradoxically_accepted()

    def add_variables(self):
        self.x_buy = self.model.addVars(self.nbuy, name="x_buy", vtype=gp.GRB.CONTINUOUS)
        self.x_sell = self.model.addVars(self.nsell, name="x_sell", vtype=gp.GRB.CONTINUOUS)
        self.x_bo = self.model.addVars(self.nblock, name="x_bo", vtype=gp.GRB.CONTINUOUS)
        self.u_bo = self.model.addVars(self.nblock, name="u_bo", vtype=gp.GRB.BINARY)

    def add_constraints(self):
        self.clearing_buy = self.model.addConstrs(self.x_buy[i] <= 1  for i in range(self.nbuy) for t in range(24))
        self.clearing_sell = self.model.addConstrs(self.x_sell[i]  <= 1 for i in range(self.nsell) for t in range(24))
        self.max_bo = self.model.addConstrs(self.x_bo[i] <= self.u_bo[i] for i in range(self.nblock))
        self.min_bo = self.model.addConstrs(self.x_bo[i] >= self.block_orders['blocks'][i]['accRatio'] * self.u_bo[i] for i in range(self.nblock))
        self.exclusive_groups = self.model.addConstrs(gp.quicksum(self.x_bo[i] * (1 if self.block_orders['blocks'][i]['id'] in self.block_orders['exclusive_groups'][eg] else 0) for i in range(self.nblock)) <= 1
            for eg in range(len(self.block_orders['exclusive_groups'])))
        self.linked_blocks = self.model.addConstrs(
            self.x_bo[i] >= self.x_bo[j]
            for link in range(len(self.block_orders['linked']))
            for i in [i for i in range(self.nblock) if self.block_orders['blocks'][i]['id'] == self.block_orders['linked'][link]['parent']]
            for j in [i for i in range(self.nblock) if self.block_orders['blocks'][i]['id'] == self.block_orders['linked'][link]['child']]
        )
        self.power_balance = self.model.addConstrs(
            (gp.quicksum(self.x_buy[i] * self.hourly_orders['buy'][i]['quantity'] * (1 if self.hourly_orders['buy'][i]['hour'] == t else 0) for i in range(self.nbuy)) + 
            gp.quicksum(self.x_bo[i] * self.block_orders['blocks'][i]['hours'][t] for i in range(self.nblock)) ==
            gp.quicksum(self.x_sell[i] * self.hourly_orders['sell'][i]['quantity'] * (1 if self.hourly_orders['sell'][i]['hour'] == t else 0) for i in range(self.nsell))
            for t in range(24)), name='power_balance'
            )

    def set_objective(self):
        total_utility = gp.quicksum(self.x_buy[i] * self.hourly_orders['buy'][i]['quantity'] * self.hourly_orders['buy'][i]['price']
            for i in range(self.nbuy))
        supply_cost = gp.quicksum(self.x_sell[i] * self.hourly_orders['sell'][i]['quantity'] * self.hourly_orders['sell'][i]['price']
            for i in range(self.nsell))
        block_utility = gp.quicksum(self.x_bo[i] * self.block_orders['blocks'][i]['hours'][t] * self.block_orders['blocks'][i]['price'] for i in range(self.nblock) for t in range(24))
        self.model.setObjective(total_utility - supply_cost + block_utility, gp.GRB.MAXIMIZE)

    def optimize(self):
        self.model.setParam('MIPGap', 0.0001)
        self.model.setParam('IntFeasTol', 0.000000001)
        self.model.optimize()

    def determine_clearing_prices(self):
        fixed = self.model.fixed()
        fixed.optimize()
        prices = []
        for i in [i for i in fixed.getConstrs() if "power_balance" in i.ConstrName]:
            prices.append(i.getAttr("Pi"))
        self.prices = prices
        print(round(self.model.getObjective().getValue(),2))
        print(round(self.get_welfare_demand(),2))
        print(round(self.get_welfare_supply(),2))
        print(prices)

    def determine_paradoxically_accepted(self):
        reject = []
        for i in self.u_bo:
            utility = self.get_block_profit(i)
            if utility < 0:
                reject.append(i)
        rejected_bo = self.model.addConstrs(self.u_bo[i] <= 0 for i in reject) # Simplified cut: rejects every PAB bid instead of combination of PABs 
        self.rejected_bo_constrs.append(rejected_bo)
        self.i = len(reject)
        self.test.append(reject)

    def get_clearing_prices(self):
        return [round(i, 2) for i in self.prices]

    def get_block_acceptance_ratio(self, block_id):
        i = next((i for i, block in enumerate(self.block_orders['blocks']) if block['id'] == block_id), -1)
        return self.x_bo[i].x if i >= 0 else 0

    def get_objective(self):
        return self.model.getObjective().getValue()

    def get_welfare_demand(self, with_blocks=True):
        welfare = 0
        for i in range(len(self.hourly_orders['buy'])):
            order = self.hourly_orders['buy'][i]
            if order['hour'] < 25:
                welfare += (order['price'] - self.prices[order['hour']]) * self.x_buy[i].x * order['quantity']
        if with_blocks:
            for i in self.u_bo:
                if sum(self.block_orders['blocks'][i]['hours']) > 0:
                    welfare += self.get_block_profit(i)
        return welfare

    def get_welfare_supply(self, with_blocks=True):
        welfare = 0
        for i in range(len(self.hourly_orders['sell'])):
            order = self.hourly_orders['sell'][i]
            if order['hour'] < 25:
                welfare += (self.prices[order['hour']] - order['price']) * self.x_sell[i].x * order['quantity']
        if with_blocks:
            for i in self.u_bo:
                if sum(self.block_orders['blocks'][i]['hours']) < 0:
                    welfare += self.get_block_profit(i)
        return welfare

    def get_welfare_blocks(self):
        welfare = 0
        for i in self.u_bo:
            if self.u_bo[i].x > 0:
                utility = self.get_block_profit(i)
                welfare += utility
        return welfare

    def get_block_profit(self, i):
        utility = 0
        for j in range(24):
            q = self.block_orders['blocks'][i]['hours'][j]
            if q > 0:
                utility += q * (self.block_orders['blocks'][i]['price'] - self.prices[j]) * self.x_bo[i].x
            else:
                utility += q * (self.prices[j] - self.block_orders['blocks'][i]['price']) * -1 * self.x_bo[i].x
        return utility