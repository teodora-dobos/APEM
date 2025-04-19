import re
from typing import Optional
import gurobipy as gp
from gurobipy import GRB
import pandas as pd


class Price_Subproblem:
    def __init__(self, master_problem, solution_dict):
        self.master_problem = master_problem
        self.solution_dict_df = pd.DataFrame(solution_dict)
        self.epsilon =master_problem.epsilon
        self.cuts = {}

        self.pricing_model = gp.Model('Price-Subproblem')

        # MCPs have to be in the range of upper and lower bounds for specific bidding zone
        self.MCP = self.pricing_model.addVars(self.master_problem.periods, name="MCP", lb=self.master_problem.price_lower_bound, ub=self.master_problem.price_upper_bound, vtype=GRB.CONTINUOUS)

    def solve_price_determination_subproblem(self, reinsertion: Optional[bool] = False) -> None:
        """
        Compute shadow prices.
        """

        self.pricing_model.setObjective(gp.quicksum(((self.MCP[t] - (self.master_problem.price_upper_bound - self.master_problem.price_lower_bound) / 2) ** 2) for t in self.master_problem.periods), GRB.MINIMIZE)


        self.add_block_price_limits()
        self.add_step_price_limits()

        self.pricing_model.write(f"{self.master_problem.paths['debug']}/pricing_model.lp")

        self.pricing_model.optimize()



        prices = {}
        # for i in [i for i in pricing_model.getConstrs() if "power_balance" in i.ConstrName]:
        #     match = re.search(r'\[(\d+)\]', i.ConstrName)
        #     period = int(match.group(1))
        #     prices[period] = -i.getAttr("Pi")

        #self.set_prices(prices, reinsertion=reinsertion)
        # with open('pricing_subproblem' + f'/test.txt', 'w') as file:
        #     for key, value in prices.items():
        #         file.write(f"{key}: {value}\n")

    def add_step_price_limits(self):

        # Step order DataFrame with acceptance values
        step_order_df = self.master_problem.step_orders.copy()
        accept_step_order_columns = [col for col in self.solution_dict_df.columns if 'accept_step' in col]
        accept_step_values = self.solution_dict_df[accept_step_order_columns].values.flatten()
        step_order_df['acceptance'] = accept_step_values

        for i in range(len(step_order_df)):
            p = step_order_df['p'][i]
            q = step_order_df['q'][i]
            t = step_order_df['t'][i]
            acceptance = step_order_df['acceptance'][i]


            gurobi_acceptance_var = None
            # save gurobi accept variable object in order to use it for cuts
            for index, value in self.master_problem.accept_step.items():
                if value.VarName == f"accept_step[{i+1}]":
                    gurobi_acceptance_var = value
                    break


            if q == 0:
                continue

            # INM → must have been accepted
            if acceptance >= 1.0 - self.epsilon:
                if q > 0:
                    # Sale: INM → p <= MCP
                    self.pricing_model.addConstr(self.MCP[t] >= p - self.epsilon, name=f"sell_step_accepted_{i+1}")
                    #self.cuts[f"sell_step_INM_accept_{i}"] = gurobi_acceptance_var <= 1 - self.epsilon
                else:
                    # Purchase: INM → p >= MCP
                    self.pricing_model.addConstr(self.MCP[t] <= p + self.epsilon, name=f"buy_step_accepted_{i+1}")
                    #self.cuts[f"buy_step_INM_accept_{i}"] = gurobi_acceptance_var <= 1 - self.epsilon

            # OTM → must have been rejected
            elif acceptance <= self.epsilon:
                if q > 0:
                    # Sale: OTM → p >= MCP
                    self.pricing_model.addConstr(self.MCP[t] <= p + self.epsilon, name=f"sell_step_rejected_{i+1}")
                    #self.cuts[f"sell_step_OTM_reject_{i}"] = gurobi_acceptance_var >= 0 + self.epsilon
                else:
                    # Purchase: OTM → p <= MCP
                    self.pricing_model.addConstr(self.MCP[t] >= p - self.epsilon, name=f"buy_step_rejected_{i+1}")
                    #self.cuts[f"buy_step_OTM_reject_{i}"] = gurobi_acceptance_var >= 0 + self.epsilon

            # ATM → must be exactly at the money
            elif 0.0 < acceptance < 1.0:
                self.pricing_model.addConstr(self.MCP[t] >= p - self.epsilon, name=f"step_partially_accepted_lower_{i+1}")
                self.pricing_model.addConstr(self.MCP[t] <= p + self.epsilon, name=f"step_partially_accepted_upper_{i+1}")
                #if q > 0:
                    # negative surplus -> accept less
                    #self.cuts[f"step_ATM_lower_{i}"] = gurobi_acceptance_var <= acceptance - self.epsilon
                    # positive surplus -> accept more
                    #self.cuts[f"step_ATM_upper_{i}"] = gurobi_acceptance_var >= acceptance + self.epsilon
                #else:
                    # positive surplus -> accept more
                    #self.cuts[f"step_ATM_lower_{i}"] = gurobi_acceptance_var >= acceptance + self.epsilon
                    # negative surplus -> accept less
                    #self.cuts[f"step_ATM_upper_{i}"] = gurobi_acceptance_var <= acceptance - self.epsilon


    """
    Add constraints in order to avoid the paradoxical acceptance of block orders (PABs)
    """
    def add_block_price_limits(self):
        accept_block_columns = [col for col in self.solution_dict_df.columns if 'accept_block' in col]
        accept_block_values = self.solution_dict_df[accept_block_columns].values.flatten()

        block_order_df = self.master_problem.block_orders.copy()
        block_order_df['acceptance'] = accept_block_values

        for i in range(len(block_order_df)):
            if block_order_df['acceptance'][i] > self.epsilon:  # Only accepted blocks relevant
                p_value = block_order_df['p'][i]
                q_columns = [col for col in block_order_df.columns if col.startswith('q')]
                q_values = block_order_df.loc[i, q_columns].values

                total_quantity = sum(abs(q) for q in q_values)
                if total_quantity == 0:
                    continue  # No relevance with q = 0 for all

                weighted_mcp = gp.quicksum(
                    self.MCP[t] * q for t, q in zip(self.master_problem.periods, q_values)
                ) / total_quantity

                # set right weighted_mcp in case of flexible block order
                if block_order_df['block_type'][i] == 'flexible':

                    # list with flex_period variables for current order
                    flex_vars = [
                        (t, var) for (oid, t), var in self.master_problem.flex_period.items()
                        if oid == i + 1
                    ]

                    # Dictionary with values for each time period
                    flex_vals = {
                        t: self.master_problem.model.cbGetSolution(var)
                        for (t, var) in flex_vars
                    }

                    # Find time period with value 1
                    active_period = next((t for t, val in flex_vals.items() if val > 0.5), None)

                    # overwrite weighted MCP with correct value considering flex_period variable
                    weighted_mcp = self.MCP[active_period] * q_values[0]

                # Sales or purchase order
                is_sale = any(q > 0 for q in q_values)

                gurobi_acceptance_var = None
                # save gurobi accept variable object in order to use it for cuts
                for index, value in self.master_problem.accept_block.items():
                    if value.VarName == f"accept_block[{i + 1}]":
                        gurobi_acceptance_var = value
                        break

                if is_sale:
                    # Sales order: INM, if p < avg(MCP)
                    self.pricing_model.addConstr(weighted_mcp >= p_value, f"sell_block_INM_{i+1}")
                    self.cuts[f"sell_block_INM_{i+1}"] = gurobi_acceptance_var == 0.0
                else:
                    # Purchase order: INM, if p > avg(MCP)
                    self.pricing_model.addConstr(weighted_mcp <= p_value, f"buy_block_INM_{i+1}")
                    self.cuts[f"buy_block_INM_{i+1}"] = gurobi_acceptance_var == 0.0
