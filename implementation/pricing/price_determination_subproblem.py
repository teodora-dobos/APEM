import re
from typing import Optional
import gurobipy as gp
from gurobipy import GRB
import pandas as pd
import random

from implementation.utils.calculations import calculate_flexible_order_active_period


class Price_Subproblem:
    def __init__(self, master_problem):
        self.master_problem = master_problem
        self.M = master_problem.M
        self.distance_factor = master_problem.distance_factor
        self.solution_dict_df = pd.DataFrame(self.master_problem.current_alloc_solution)
        self.epsilon = master_problem.epsilon
        self.cuts = {}

        self.pricing_model = gp.Model('Price-Subproblem')

        # MCPs have to be in the range of upper and lower bounds for specific bidding zone
        self.MCP = self.pricing_model.addVars(self.master_problem.periods, name="MCP",
                                              lb=self.master_problem.price_lower_bound,
                                              ub=self.master_problem.price_upper_bound, vtype=GRB.CONTINUOUS)

    def solve_price_determination_subproblem(self, reinsertion: Optional[bool] = False) -> None:

        self.pricing_model.setObjective(gp.quicksum(
            ((self.MCP[t] - (self.master_problem.price_upper_bound - self.master_problem.price_lower_bound) / 2) ** 2)
            for t in self.master_problem.periods), GRB.MINIMIZE)

        self.add_block_order_constraints()
        self.add_step_order_constraints()
        self.add_MIC_MP_constraints()
        self.add_piecewise_linear_order_constraints()

        self.pricing_model.write(f"{self.master_problem.paths['debug']}/pricing_model.lp")

        self.pricing_model.optimize()

    """
    Add constraints in order to avoid the paradoxical acceptance and rejection of period step orders
    """

    def add_step_order_constraints(self):
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
            gurobi_acceptance_var = self.master_problem.accept_step[i + 1]

            if q == 0:
                continue

            # INM → must have been accepted
            if acceptance >= 1.0 - self.epsilon:
                if q > 0:
                    # Sale: INM → p <= MCP
                    self.pricing_model.addConstr(self.MCP[t] >= p - self.epsilon, name=f"sell_step_accepted_{i + 1}")
                    self.cuts[f"sell_step_accepted_{i + 1}"] = [
                        gurobi_acceptance_var <= acceptance - random.uniform(0.8,
                                                                             1.2) * self.distance_factor * self.epsilon,
                        gurobi_acceptance_var >= acceptance + random.uniform(0.8,
                                                                             1.2) * self.distance_factor * self.epsilon]
                else:
                    # Purchase: INM → p >= MCP
                    self.pricing_model.addConstr(self.MCP[t] <= p + self.epsilon, name=f"buy_step_accepted_{i + 1}")
                    self.cuts[f"buy_step_accepted_{i + 1}"] = [
                        gurobi_acceptance_var <= acceptance - random.uniform(0.8,
                                                                             1.2) * self.distance_factor * self.epsilon,
                        gurobi_acceptance_var >= acceptance + random.uniform(0.8,
                                                                             1.2) * self.distance_factor * self.epsilon]

            # OTM → must have been rejected
            elif acceptance <= self.epsilon:
                if q > 0:
                    # Sale: OTM → p >= MCP
                    self.pricing_model.addConstr(self.MCP[t] <= p + self.epsilon, name=f"sell_step_rejected_{i + 1}")
                    self.cuts[f"sell_step_rejected_{i + 1}"] = [
                        gurobi_acceptance_var <= acceptance - random.uniform(0.8,
                                                                             1.2) * self.distance_factor * self.epsilon,
                        gurobi_acceptance_var >= acceptance + random.uniform(0.8,
                                                                             1.2) * self.distance_factor * self.epsilon]
                else:
                    # Purchase: OTM → p <= MCP
                    self.pricing_model.addConstr(self.MCP[t] >= p - self.epsilon, name=f"buy_step_rejected_{i + 1}")
                    self.cuts[f"buy_step_rejected_{i + 1}"] = [
                        gurobi_acceptance_var <= acceptance - random.uniform(0.8,
                                                                             1.2) * self.distance_factor * self.epsilon,
                        gurobi_acceptance_var >= acceptance + random.uniform(0.8,
                                                                             1.2) * self.distance_factor * self.epsilon]

            # ATM → must be exactly at the money
            elif 0.0 < acceptance < 1.0:
                self.pricing_model.addConstr(self.MCP[t] >= p - self.epsilon,
                                             name=f"step_partially_accepted_lower_{i + 1}")
                self.pricing_model.addConstr(self.MCP[t] <= p + self.epsilon,
                                             name=f"step_partially_accepted_upper_{i + 1}")
                self.cuts[f"step_partially_accepted_lower_{i + 1}"] = [
                    gurobi_acceptance_var <= acceptance - random.uniform(0.8,
                                                                         1.2) * self.distance_factor * self.epsilon,
                    gurobi_acceptance_var >= acceptance + random.uniform(0.8,
                                                                         1.2) * self.distance_factor * self.epsilon,
                    gurobi_acceptance_var == 0.0]
                self.cuts[f"step_partially_accepted_upper_{i + 1}"] = [
                    gurobi_acceptance_var <= acceptance - random.uniform(0.8,
                                                                         1.2) * self.distance_factor * self.epsilon,
                    gurobi_acceptance_var >= acceptance + random.uniform(0.8,
                                                                         1.2) * self.distance_factor * self.epsilon,
                    gurobi_acceptance_var == 0.0]

    def add_piecewise_linear_order_constraints(self):
        accept_piecewise_linear_order_columns = [col for col in self.solution_dict_df.columns if
                                                 'accept_piecewise_linear' in col]
        accept_piecewise_linear_order_values = self.solution_dict_df[
            accept_piecewise_linear_order_columns].values.flatten()

        piecewise_linear_order_df = self.master_problem.piecewise_linear_orders.copy()
        piecewise_linear_order_df['acceptance'] = accept_piecewise_linear_order_values

        for _, order in piecewise_linear_order_df.iterrows():
            order_id = int(order['id'])
            p0 = order['p0']
            p1 = order['p1']
            q = order['q']
            t = order['t']
            acceptance = order['acceptance']
            gurobi_acceptance_var = self.master_problem.accept_piecewise_linear[order_id]

            if acceptance >= 1.0 - self.epsilon:
                if q > 0:
                    # Sale: INM → p <= MCP
                    self.pricing_model.addConstr(self.MCP[t] >= p1 - self.epsilon, name=f"sell_PLO_accepted_{order_id}")
                    self.cuts[f"sell_PLO_accepted_{order_id}"] = [
                        gurobi_acceptance_var <= acceptance - random.uniform(0.8,
                                                                             1.2) * self.distance_factor * self.epsilon,
                        gurobi_acceptance_var >= acceptance + random.uniform(0.8,
                                                                             1.2) * self.distance_factor * self.epsilon]
                else:
                    # Purchase: INM → p >= MCP
                    self.pricing_model.addConstr(self.MCP[t] <= p1 + self.epsilon, name=f"buy_PLO_accepted_{order_id}")
                    self.cuts[f"buy_PLO_accepted_{order_id}"] = [
                        gurobi_acceptance_var <= acceptance - random.uniform(0.8,
                                                                             1.2) * self.distance_factor * self.epsilon,
                        gurobi_acceptance_var >= acceptance + random.uniform(0.8,
                                                                             1.2) * self.distance_factor * self.epsilon]

            # OTM → must have been rejected
            elif acceptance <= self.epsilon:
                if q > 0:
                    # Sale: OTM → p >= MCP
                    self.pricing_model.addConstr(self.MCP[t] <= p0 + self.epsilon,
                                                 name=f"sell_PLO_rejected_{order_id}")
                    self.cuts[f"sell_PLO_rejected_{order_id}"] = [
                        gurobi_acceptance_var <= acceptance - random.uniform(0.8,
                                                                             1.2) * self.distance_factor * self.epsilon,
                        gurobi_acceptance_var >= acceptance + random.uniform(0.8,
                                                                             1.2) * self.distance_factor * self.epsilon]
                else:
                    # Purchase: OTM → p <= MCP
                    self.pricing_model.addConstr(self.MCP[t] >= p0 - self.epsilon, name=f"buy_PLO_rejected_{order_id}")
                    self.cuts[f"buy_PLO_rejected_{order_id}"] = [
                        gurobi_acceptance_var <= acceptance - random.uniform(0.8,
                                                                             1.2) * self.distance_factor * self.epsilon,
                        gurobi_acceptance_var >= acceptance + random.uniform(0.8,
                                                                             1.2) * self.distance_factor * self.epsilon]

            # ATM → must be exactly at the money
            elif 0.0 < acceptance < 1.0:
                print(f"PLO acceptance = {acceptance}")
                self.pricing_model.addConstr((self.MCP[t] - p0) / (p1 - p0) - self.epsilon <= acceptance,
                                             name=f"PLO_partially_accepted_lower_{order_id}")
                self.pricing_model.addConstr((self.MCP[t] - p0) / (p1 - p0) + self.epsilon >= acceptance,
                                             name=f"PLO_partially_accepted_upper_{order_id}")
                self.cuts[f"PLO_partially_accepted_upper_{order_id}"] = [
                    gurobi_acceptance_var <= acceptance - random.uniform(0.8,
                                                                         1.2) * self.distance_factor * self.epsilon,
                    gurobi_acceptance_var >= acceptance + random.uniform(0.8,
                                                                         1.2) * self.distance_factor * self.epsilon,
                    gurobi_acceptance_var == 0.0]
                self.cuts[f"PLO_partially_accepted_lower_{order_id}"] = [
                    gurobi_acceptance_var <= acceptance - random.uniform(0.8,
                                                                         1.2) * self.distance_factor * self.epsilon,
                    gurobi_acceptance_var >= acceptance + random.uniform(0.8,
                                                                         1.2) * self.distance_factor * self.epsilon,
                    gurobi_acceptance_var == 0.0]

    """
    Add constraints in order to avoid the paradoxical acceptance of block orders (PABs)
    """

    def add_block_order_constraints(self):
        accept_block_columns = [col for col in self.solution_dict_df.columns if 'accept_block' in col]
        accept_block_values = self.solution_dict_df[accept_block_columns].values.flatten()

        block_order_df = self.master_problem.block_orders.copy()
        block_order_df['acceptance'] = accept_block_values

        for _, block_order in block_order_df.iterrows():
            if block_order['acceptance'] > self.epsilon:  # Only accepted blocks relevant
                block_id = block_order['id']
                p = block_order['p']
                q_columns = [col for col in block_order_df.columns if col.startswith('q')]
                q_values = block_order_df.loc[block_id - 1, q_columns].values

                total_quantity = sum(abs(q) for q in q_values)
                if total_quantity == 0:
                    continue  # No relevance with q = 0 for all

                weighted_mcp = gp.quicksum(
                    self.MCP[t] * q for t, q in zip(self.master_problem.periods, q_values)
                ) / total_quantity

                # set right weighted_mcp in case of flexible block order
                if block_order['block_type'] == 'flexible':
                    # overwrite weighted MCP with correct value considering flex_period variable
                    active_period = calculate_flexible_order_active_period(master_problem=self.master_problem,
                                                                           block_id=block_id)
                    weighted_mcp = self.MCP[active_period] * q_values[0]

                # Sales or purchase order
                is_sale = any(q > 0 for q in q_values)

                # save gurobi accept variable object in order to use it for cuts
                gurobi_acceptance_var = self.master_problem.accept_block[block_id]

                if block_order['block_type'] != 'linked':
                    if is_sale:
                        # Sales order: INM, if p < avg(MCP)
                        self.pricing_model.addConstr(weighted_mcp >= p, f"sell_block_INM_{block_id}")
                        self.cuts[f"sell_block_INM_{block_id}"] = [gurobi_acceptance_var == 0.0]
                    else:
                        # Purchase order: INM, if p > avg(MCP)
                        self.pricing_model.addConstr(weighted_mcp <= p, f"buy_block_INM_{block_id}")
                        self.cuts[f"buy_block_INM_{block_id}"] = [gurobi_acceptance_var == 0.0]
                else:
                    self.add_linked_block_order_constraints(block_order_df=block_order_df, parent_order=block_order)

    def add_linked_block_order_constraints(self, block_order_df, parent_order):
        child_id = parent_order['code_prm']
        child_dict = block_order_df.loc[block_order_df['id'] == child_id].iloc[0].to_dict()

        # Family surplus must not be negative
        self.pricing_model.addConstr(gp.quicksum(
            (child_dict['acceptance'] * child_dict[f'q{t}'] + parent_order['acceptance'] * parent_order[f'q{t}']) * (
                    child_dict['p'] - self.MCP[t]) for t in self.master_problem.periods) >= 0,
                                     f'linked_block_positive_family_{child_id}')
        self.cuts[f'linked_block_positive_family_{child_id}'] = self.master_problem.accept_block[
                                                                    parent_order['id']] == 0.0

        # Leaf blocks are not allowed to generate negative surplus
        if block_order_df['block_type'][child_id - 1] != 'linked':
            self.pricing_model.addConstr(
                gp.quicksum(child_dict['acceptance'] * (child_dict['p'] - self.MCP[t]) * child_dict[f'q{t}'] for t in
                         self.master_problem.periods) >= 0,
                f'linked_block_positive_leaf_{child_id}')
            self.cuts[f'linked_block_positive_leaf_{child_id}'] = self.master_problem.accept_block[
                                                                      parent_order['id']] == 0.0

    def add_MIC_MP_constraints(self):
        # MIC / MP for complex orders
        accept_complex_columns = [col for col in self.solution_dict_df.columns if 'accept_complex[' in col]
        accept_complex_step_columns = [col for col in self.solution_dict_df.columns if 'accept_complex_step[' in col]
        accept_complex_values = self.solution_dict_df[accept_complex_columns].values.flatten()
        accept_complex_step_values = self.solution_dict_df[accept_complex_step_columns].values.flatten()

        complex_order_df = self.master_problem.complex_orders.copy()
        complex_step_order_df = self.master_problem.complex_step_orders.copy()
        complex_order_df['acceptance'] = accept_complex_values
        complex_step_order_df['acceptance'] = accept_complex_step_values

        for _, order in complex_order_df.iterrows():
            # only accepted complex orders relevant
            if order['acceptance'] > self.epsilon and (order['condition'] == 'MP' or order['condition'] == 'MIC'):
                order_id = int(order['id'])

                variable_expected_value = 0
                actual_value = gp.LinExpr()
                # calculate minimal expected income / maximum payment
                for _, step_order in complex_step_order_df.iterrows():
                    if step_order['complex_order_id'] == order_id:
                        self.add_complex_step_constraint(step_order, infix="complex")

                        # calculate values for MIC / MP
                        variable_expected_value += step_order['acceptance'] * order['variable_term'] * abs(
                            step_order['q'])
                        actual_value += step_order['acceptance'] * abs(step_order['q']) * self.MCP[step_order['t']]
                expected_value = order['fixed_term'] + variable_expected_value

                gurobi_acceptance_var = self.master_problem.accept_complex[order_id]

                if order['condition'] == 'MP':
                    self.pricing_model.addConstr(actual_value <= expected_value, f"MP_condition_CO_{order_id}")
                    self.cuts[f"MP_condition_CO_{order_id}"] = [gurobi_acceptance_var == 0.0]
                else:
                    self.pricing_model.addConstr(actual_value >= expected_value, f"MIC_condition_CO_{order_id}")
                    self.cuts[f"MIC_condition_CO_{order_id}"] = [gurobi_acceptance_var == 0.0]

        # MIC / MP for scalable complex orders
        accept_scalable_columns = [col for col in self.solution_dict_df.columns if 'accept_scalable_complex[' in col]
        accept_scalable_step_columns = [col for col in self.solution_dict_df.columns if 'accept_scalable_step[' in col]
        accept_scalable_values = self.solution_dict_df[accept_scalable_columns].values.flatten()
        accept_scalable_step_values = self.solution_dict_df[accept_scalable_step_columns].values.flatten()

        scalable_complex_order_df = self.master_problem.scalable_complex_orders.copy()
        scalable_complex_step_order_df = self.master_problem.scalable_step_orders.copy()
        scalable_complex_order_df['acceptance'] = accept_scalable_values
        scalable_complex_step_order_df['acceptance'] = accept_scalable_step_values

        for _, order in scalable_complex_order_df.iterrows():
            if order['acceptance'] > self.epsilon and (order['condition'] == 'MP' or order['condition'] == 'MIC'):
                order_id = int(order['id'])

                variable_expected_value = 0
                actual_value = gp.LinExpr()
                # calculate minimal expected income / maximum payment
                for _, step_order in scalable_complex_step_order_df.iterrows():
                    if step_order['scalable_order_id'] == order_id:
                        self.add_complex_step_constraint(step_order, infix="scalable_complex")

                        variable_expected_value += step_order['acceptance'] * step_order['p'] * abs(step_order['q'])
                        actual_value += step_order['acceptance'] * abs(step_order['q']) * self.MCP[step_order['t']]
                expected_value = order['fixed_term'] + variable_expected_value

                gurobi_acceptance_var = self.master_problem.accept_scalable[order_id]

                if order['condition'] == 'MP':
                    self.pricing_model.addConstr(actual_value <= expected_value, f"MP_condition_SCO_{order_id}")
                    self.cuts[f"MP_condition_SCO_{order_id}"] = [gurobi_acceptance_var == 0.0]
                else:
                    self.pricing_model.addConstr(actual_value >= expected_value, f"MIC_condition_SCO_{order_id}")
                    self.cuts[f"MIC_condition_SCO_{order_id}"] = [gurobi_acceptance_var == 0.0]


    """
    Add constraints to (scalable) complex step orders in order to make sure there are no paradoxically accepted orders
    """
    def add_complex_step_constraint(self, step_order, infix):
        acceptance = step_order['acceptance']
        q = step_order['q']
        t = step_order['t']
        p = step_order['p']
        id = int(step_order['id'])
        if acceptance >= 1.0 - self.epsilon:
            if q > 0:
                self.pricing_model.addConstr(self.MCP[t] >= p - self.epsilon, f"sell_{infix}_step_accepted_{id}")
            else:
                self.pricing_model.addConstr(self.MCP[t] <= p + self.epsilon, f"buy_{infix}_step_accepted_{id}")
        elif 0.0 + self.epsilon < acceptance < 1.0 - self.epsilon:
            self.pricing_model.addConstr(self.MCP[t] >= p - self.epsilon,
                                         name=f"{infix}_step_partially_accepted_lower_{id}")
            self.pricing_model.addConstr(self.MCP[t] <= p + self.epsilon,
                                         name=f"{infix}_step_partially_accepted_upper_{id}")
