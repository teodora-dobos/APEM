import re
from typing import Optional
import gurobipy as gp
from gurobipy import GRB
import pandas as pd


class Price_Subproblem:
    def __init__(self, master_problem, solution_dict):
        self.master_problem = master_problem
        self.solution_dict_df = pd.DataFrame(solution_dict)

        self.pricing_model = gp.Model('Price-Subproblem')

        # MCPs have to be in the range of upper and lower bounds for specific bidding zone
        self.MCP = self.pricing_model.addVars(self.master_problem.periods, name="MCP", lb=self.master_problem.price_lower_bound, ub=self.master_problem.price_upper_bound, vtype=GRB.CONTINUOUS)

    def solve_price_determination_subproblem(self, reinsertion: Optional[bool] = False) -> None:
        """
        Compute shadow prices.
        """

        self.pricing_model.setObjective(gp.quicksum(((self.MCP[t] - (self.master_problem.price_upper_bound - self.master_problem.price_lower_bound) / 2) ** 2) for t in self.master_problem.periods), GRB.MINIMIZE)



        self.add_block_price_limits()
        self.pricing_model.optimize()
        if self.pricing_model.status == GRB.OPTIMAL:
            print("Found market clearing prices")
            for v in self.pricing_model.getVars():
                print(f"{v.varName}: {v.x}")
        if self.pricing_model.status == GRB.INFEASIBLE:
            print("Price subproblem is infeasible")


        prices = {}
        # for i in [i for i in pricing_model.getConstrs() if "power_balance" in i.ConstrName]:
        #     match = re.search(r'\[(\d+)\]', i.ConstrName)
        #     period = int(match.group(1))
        #     prices[period] = -i.getAttr("Pi")

        #self.set_prices(prices, reinsertion=reinsertion)
        # with open('pricing_subproblem' + f'/test.txt', 'w') as file:
        #     for key, value in prices.items():
        #         file.write(f"{key}: {value}\n")



    def add_block_price_limits(self):
        accept_block_columns = [col for col in self.solution_dict_df.columns if 'accept_block' in col]
        accept_block_values = self.solution_dict_df[accept_block_columns].values.flatten()

        block_order_df = self.master_problem.block_orders.copy()
        block_order_df['acceptance'] = accept_block_values

        for i in range(len(block_order_df)):
            if block_order_df['acceptance'][i] == 1.0:  # Only accepted blocks relevant
                # Extract price for current order
                p_value = block_order_df['p'][i]
                # Extract all periods for current order
                q_columns = [col for col in block_order_df.columns if col.startswith('q')]
                q_values = block_order_df.loc[i, q_columns].values

                sales_order = any(q > 0 for q in q_values)

                for t in self.master_problem.periods:
                    if not sales_order:
                        self.pricing_model.addConstr(self.MCP[t] <= p_value, f"buy_order_constraint_{i}_t{t}")
                    else:
                        self.pricing_model.addConstr(self.MCP[t] >= p_value, f"sell_order_constraint_{i}_t{t}")