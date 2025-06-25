import ast
import os
import random
import shutil
from typing import Optional
import gurobipy as gp
from gurobipy import GRB
import re
import pandas as pd

from euphemia.data.parsing.zonal_scenario import ZonalScenario
from euphemia.enums.cut_types import CutType
from euphemia.enums.order_types import OrderType
from euphemia.model.setup_model import add_objective, add_market_constraints, add_network_constraints
from euphemia.pricing.price_determination_subproblem import Price_Subproblem
from euphemia.reinsertions.prmic_prb_reinsertion import PRMIC_PRB_reinsertion
from euphemia.utils.calculations import calculate_flexible_order_active_period
from euphemia.utils.extraction import get
from euphemia.utils.paths import EUPHEMIA_ROOT


class Euphemia:
    def __init__(self, scenario: ZonalScenario):
        self.model = gp.Model('Euphemia')
        self.scenario = scenario
        self.periods = scenario.periods
        self.step_orders = scenario.step_orders
        self.block_orders = scenario.block_orders
        self.complex_orders = scenario.complex_orders
        self.complex_step_orders = scenario.complex_step_orders
        self.scalable_complex_orders = scenario.scalable_complex_orders
        self.scalable_step_orders = scenario.scalable_step_orders
        self.piecewise_linear_orders = scenario.piecewise_linear_orders

        self.accept_step = self.model.addVars(list(self.step_orders['id']), vtype=GRB.CONTINUOUS, lb=0, ub=1,
                                              name='accept_step')
        self.accept_block = self.model.addVars(list(self.block_orders['id']), vtype=GRB.CONTINUOUS, lb=0, ub=1,
                                               name='accept_block')
        # required for the big-M constraint to satisfy the MAR condition of block orders
        self.MAR_aux = self.model.addVars(list(self.block_orders['id']), vtype=GRB.BINARY, name='y')

        # required for flexible orders - decide in which period the order is accepted
        self.flex_period = self.model.addVars(
            list(self.block_orders[self.block_orders['block_type'] == 'flexible']['id']), self.periods,
            vtype=GRB.BINARY, name='flex_period')
        self.accept_complex = self.model.addVars(list(self.complex_orders['id']), vtype=GRB.BINARY, lb=0, ub=1,
                                                 name='accept_complex')
        self.accept_complex_step = self.model.addVars(list(self.complex_step_orders['id']), vtype=GRB.CONTINUOUS,
                                                      lb=0, ub=1, name='accept_complex_step')
        self.accept_scalable = self.model.addVars(list(self.scalable_complex_orders['id']), vtype=GRB.BINARY,
                                                  lb=0, ub=1, name='accept_scalable_complex')
        self.accept_scalable_step = self.model.addVars(list(self.scalable_step_orders['id']), vtype=GRB.CONTINUOUS,
                                                       lb=0, ub=1, name='accept_scalable_step')
        self.accept_piecewise_linear = self.model.addVars(list(self.piecewise_linear_orders['id']),
                                                          vtype=GRB.CONTINUOUS, lb=0, ub=1,
                                                          name='accept_piecewise_linear')

        self.add_acceptance_variables_to_dataframe()

        # Compute overlapping block orders
        self.block_overlap = self.compute_block_overlaps()
        self.block_orders['overlap_set'] = self.block_orders['id'].map(self.block_overlap)

        self.current_alloc_solution = {}
        self.found_solution = False
        self.current_best_objective = -1
        self.reinsertion_run = False

        self.model.Params.LazyConstraints = 1

        self.M = 10 ** 6
        self.prices = {}
        self.prices_reinsertion = {}
        self.price_lower_bound = -500
        self.price_upper_bound = 4000
        self.delta_PAB = 50
        self.delta_MIC = 50
        self.epsilon = 1e-4
        self.distance_factor = 1e-1
        self.max_iterations = 2000
        self.iteration = 0
        self.objective_lower_bound = 0
        self.cutting_strategy = CutType.PB
        self.paths = {
            "alloc": "euphemia_results/allocation",
            "prices": "euphemia_results/prices",
            "pab": "euphemia_results/pab",
            "block_inm_threshold": "euphemia_results/block_inm_threshold",
            "complex_mic": "euphemia_results/complex_mic",
            "complex_mic_inm_threshold": "euphemia_results/complex_mic_inm_threshold",
            "scalable_mic": "euphemia_results/scalable_mic",
            "scalable_mic_inm_threshold": "euphemia_results/scalable_mic_inm_threshold",
            "debug": "euphemia_results/debug",

        }

        for attr, path in self.paths.items():
            setattr(self, attr, path)
            if os.path.exists(path):
                shutil.rmtree(path)
            os.makedirs(path, exist_ok=True)

    def solve(self) -> None:
        """
        Compute market clearing prices, matched volumes, selection of block and complex orders that will be executed,
        accepted percentage for each curtailable block.
        Determine the market clearing price for each zone while ensuring that no block and complex MIC orders are
        paradoxically accepted and the primal-dual relations are satisfied.
        Add cut to the master problem that renders the current solution infeasible if no prices were found.
        The prices computed satisfy:
            - complementary slackness conditions
            - price bounds
            - no PAB constraints
            - MIC
        """
        add_objective(self)
        add_market_constraints(self)
        add_network_constraints(self)
        self.max_iterations = self.max_iterations if not self.reinsertion_run else 100
        self.iteration = 1

        print("Solving master problem...")
        self.solve_master_problem()
        self.model.write(os.path.join(self.paths['debug'], f"master_problem.lp"))
        print(f"Master problem status: {self.model.Status}")
        if self.model.Status == GRB.Status.INFEASIBLE:
            print("Master problem is infeasible")

        if self.found_solution:
            print(
                f'------- Surplus maximization and price problem successfully finished after {self.iteration} iterations -------')
            print(
                f'Final economic surplus{" of reinsertion run" if self.reinsertion_run else ""}: {self.current_best_objective}')
            print(f'Found prices: {self.prices}')

            if not self.reinsertion_run:
                PRMIC_PRB_reinsertion(self, is_prmic_reinsertion=True)
                PRMIC_PRB_reinsertion(self, is_prmic_reinsertion=False)

    def solve_master_problem(self) -> None:
        """
        Search for a selection of block and MIC orders that maximizes the economic surplus.
        """
        self.model.optimize(callback=self.master_problem_callback)

    def master_problem_callback(self, callbackModel, where) -> None:
        if where == GRB.Callback.MIPNODE:
            print("MIPNODE callback")

        # when a MIP solution was found
        if where == GRB.Callback.MIPSOL:
            # get current solution
            objective_value = callbackModel.cbGet(GRB.Callback.MIPSOL_OBJ)
            vars = callbackModel.getVars()
            solution = callbackModel.cbGetSolution(vars)
            if solution is not None:
                print("Found integer solution")
                print("Objective value:", objective_value)
                self.iteration += 1

                # match variables with value in current solution
                self.current_alloc_solution = {v.VarName: [val] for v, val in zip(vars, solution)}
                self.update_order_dataframes()

                # Write current allocation solution to file
                file_path = f"{EUPHEMIA_ROOT / self.paths['alloc']}/results.txt"
                with open(file_path, 'w', buffering=1) as f:
                    f.write(f"New solution with objective value {objective_value}\n")
                    for var in callbackModel.getVars():
                        f.write(f"{var.VarName}: {callbackModel.cbGetSolution(var)}\n")
                    f.flush()
                    os.fsync(f.fileno())

                print("Solving price determination subproblem...")
                price_subproblem = Price_Subproblem(master_problem=self)
                price_subproblem.solve_price_determination_subproblem()

                # If price subproblem optimal check if new incumbent was found
                if price_subproblem.pricing_model.Status == GRB.OPTIMAL:
                    print("Found market clearing prices")

                    # Write MCPs to file
                    file_path = f"{EUPHEMIA_ROOT / self.paths['prices']}/results.txt"
                    with open(file_path, 'a', buffering=1) as file:  # 'a' = append
                        for v in price_subproblem.pricing_model.getVars():
                            line = f"{v.varName}: {v.X}\n"
                            file.write(line)  # to file
                            print(line, end='')  # for console output
                        file.flush()
                        os.fsync(file.fileno())

                    if objective_value > self.current_best_objective:
                        self.set_prices({int(re.search(r'\d+', var.varName).group()): var.X for var in
                                         price_subproblem.pricing_model.getVars()}, reinsertion=False)
                        self.current_best_objective = objective_value
                        self.found_solution = True

                # if price subproblem infeasible add cut to master problem
                if price_subproblem.pricing_model.Status == GRB.INFEASIBLE:
                    print("Price subproblem is infeasible")

                    if self.cutting_strategy == CutType.CB:
                        price_subproblem.pricing_model.computeIIS()
                        terms = []
                        for constr in price_subproblem.pricing_model.getConstrs():
                            if constr.IISConstr:
                                print(f"Infeasible constraint: {constr}")
                                constr_name = constr.ConstrName

                                if constr_name in price_subproblem.constraint_meta_data.keys():
                                    metadata = price_subproblem.constraint_meta_data[constr_name]

                                    # Combinatorial Benders Cut
                                    if metadata[0] == OrderType.BLOCK:
                                        terms.append(1 - self.MAR_aux[metadata[1]])
                                    elif metadata[0] == OrderType.COMPLEX:
                                        terms.append(1 - self.accept_complex[metadata[1]])
                                    elif metadata[0] == OrderType.SCALABLE_COMPLEX:
                                        terms.append(1 - self.accept_scalable[metadata[1]])

                        callbackModel.cbLazy(gp.quicksum(terms) >= 1)
                        # For security to always invalidate solution
                        # TODO check if necessary
                        self.add_no_good_cut(callbackModel=callbackModel)

                    elif self.cutting_strategy == CutType.NG:
                        self.add_no_good_cut(callbackModel=callbackModel)

                    elif self.cutting_strategy == CutType.PB:
                        price_subproblem.pricing_model.computeIIS()
                        terms = []
                        for constr in price_subproblem.pricing_model.getConstrs():
                            if constr.IISConstr:
                                print(f"Infeasible constraint: {constr}")
                        self.handle_price_based_cutting(callbackModel=callbackModel)



    def add_acceptance_variables_to_dataframe(self) -> None:
        self.step_orders['acceptance_var'] = self.step_orders['id'].map(self.accept_step)
        self.piecewise_linear_orders['acceptance_var'] = self.piecewise_linear_orders['id'].map(
            self.accept_piecewise_linear)
        self.block_orders['acceptance_var'] = self.block_orders['id'].map(self.accept_block)
        self.complex_orders['acceptance_var'] = self.complex_orders['id'].map(self.accept_complex)
        self.scalable_complex_orders['acceptance_var'] = self.scalable_complex_orders['id'].map(self.accept_scalable)


    def update_order_dataframes(self) -> None:
        """
        Add current acceptance value to order in dataframe for simplification of further processing
        """

        solution_df = pd.DataFrame(self.current_alloc_solution)

        # step orders
        accept_step_order_columns = [col for col in solution_df.columns if 'accept_step' in col]
        accept_step_values = solution_df[accept_step_order_columns].values.flatten()
        self.step_orders['acceptance'] = accept_step_values

        # piecewise linear orders
        accept_piecewise_linear_order_columns = [col for col in solution_df.columns if
                                                 'accept_piecewise_linear' in col]
        accept_piecewise_linear_order_values = solution_df[
            accept_piecewise_linear_order_columns].values.flatten()
        self.piecewise_linear_orders['acceptance'] = accept_piecewise_linear_order_values

        # block orders
        accept_block_columns = [col for col in solution_df.columns if 'accept_block' in col]
        accept_block_values = solution_df[accept_block_columns].values.flatten()
        self.block_orders['acceptance'] = accept_block_values

        # complex orders
        accept_complex_columns = [col for col in solution_df.columns if 'accept_complex[' in col]
        accept_complex_step_columns = [col for col in solution_df.columns if 'accept_complex_step[' in col]
        accept_complex_values = solution_df[accept_complex_columns].values.flatten()
        accept_complex_step_values = solution_df[accept_complex_step_columns].values.flatten()

        self.complex_orders['acceptance'] = accept_complex_values
        self.complex_step_orders['acceptance'] = accept_complex_step_values

        # scalable complex orders
        accept_scalable_columns = [col for col in solution_df.columns if 'accept_scalable_complex[' in col]
        accept_scalable_step_columns = [col for col in solution_df.columns if 'accept_scalable_step[' in col]
        accept_scalable_values = solution_df[accept_scalable_columns].values.flatten()
        accept_scalable_step_values = solution_df[accept_scalable_step_columns].values.flatten()

        self.scalable_complex_orders['acceptance'] = accept_scalable_values
        self.scalable_step_orders['acceptance'] = accept_scalable_step_values


    def compute_block_overlaps(self) -> dict[int, set[int]]:
        """
        Computes block orders that have at least one overlapping period with quantity unequal to 0.
        Can be used for Price-based-cuts
        """
        period_cols = [f"q{t}" for t in self.periods]

        # Extract only the 'id' column and the period quantity columns
        df = self.block_orders[['id'] + period_cols].copy()

        # Boolean mask: True if quantity is non-zero in that period
        mask = df[period_cols].ne(0)

        # Extract the list of IDs (ensured to be unique)
        ids = df['id'].tolist()

        # Initialize overlap dictionary with order IDs as keys
        overlap = {i: set() for i in ids}

        # Compare each pair of orders only once (i < j)
        for idx1 in range(len(ids)):
            i = ids[idx1]
            for idx2 in range(idx1 + 1, len(ids)):
                j = ids[idx2]

                # Check for overlapping periods with non-zero quantities
                if (mask.iloc[idx1] & mask.iloc[idx2]).any():
                    overlap[i].add(j)
                    overlap[j].add(i)

        return overlap


    def add_no_good_cut(self, callbackModel) -> None:
        # create cut that makes current solution invalid
        terms = []
        # match variable from current solution with gurobi variable from model
        for gurobi_acceptance_var in callbackModel.getVars():
            if gurobi_acceptance_var.VType == GRB.BINARY:
                solution_value = self.current_alloc_solution.get(gurobi_acceptance_var.VarName)
                if solution_value is None:
                    print(f"{gurobi_acceptance_var.VarName} not found in solution dict")
                    continue
                if solution_value[0] > 0.5:
                    terms.append(1 - gurobi_acceptance_var)
                else:
                    terms.append(gurobi_acceptance_var)
        if terms:
            expr = gp.quicksum(terms)
            callbackModel.cbLazy(expr >= 1)
            print(f"Added no good cut: {expr} >= 1")


    def handle_price_based_cutting(self, callbackModel) -> None:
        print("Creating unconstrained subproblem")
        price_subproblem = Price_Subproblem(master_problem=self)
        price_subproblem.isConstrained = False
        price_subproblem.solve_price_determination_subproblem()

        if price_subproblem.pricing_model.Status == GRB.OPTIMAL:
            # Update prices (No final prices!)
            self.set_prices({int(re.search(r'\d+', var.varName).group()): var.X for var in
                             price_subproblem.pricing_model.getVars()}, reinsertion=False)

            # Add price-based cut to block orders
            pab_blocks = self.get_block_bids(threshold=False)
            print(f"PABs: {pab_blocks}")
            for b in pab_blocks:
                block_order = self.block_orders[self.block_orders['id'] == b].iloc[0]
                self.add_price_based_cut_to_block(callbackModel, block_order)

            # Apply combinatorial benders cut over PAMICs/PAMPs
            terms = []
            violated_complex_mic = self.get_MIC_complex_orders(threshold=False)
            print(f"PAMIC complex: {violated_complex_mic}")
            if violated_complex_mic:
                terms.extend(1 - self.accept_complex[i] for i in violated_complex_mic)

            violated_scalable_mic = self.get_MIC_scalable_orders(threshold=False)
            print(f"PAMIC scalable complex: {violated_scalable_mic}")
            if violated_scalable_mic:
                terms.extend(1 - self.accept_scalable[i] for i in violated_scalable_mic)

            if terms:
                print(f"Added cb cut: {gp.quicksum(terms)} >= 1")
                callbackModel.cbLazy(gp.quicksum(terms) >= 1)
        else:
            print("Something went wrong and in the unconstrained problem no prices could be found")
            callbackModel.terminate()

    def add_price_based_cut_to_block(self, callbackModel, block_order) -> None:
        terms = [1 - self.MAR_aux[block_order['id']]]  # (1 - ACCEPT_hat)

        def is_sale(bo_id: int) -> bool:
            return self.block_orders.loc[self.block_orders['id'] == bo_id,
            [f"q{t}" for t in self.periods]].values.sum() > 0

        for overlapping_order_id in block_order['overlap_set']:
            accepted = get(self.block_orders, 'acceptance', overlapping_order_id) > self.epsilon
            sale = is_sale(overlapping_order_id)

            if is_sale(block_order['id']):
                if sale and accepted: terms.append(1 - self.MAR_aux[overlapping_order_id])
                if (not sale) and (not accepted): terms.append(self.MAR_aux[overlapping_order_id])
            else:
                if (not sale) and accepted: terms.append(1 - self.MAR_aux[overlapping_order_id])
                if sale and (not accepted): terms.append(self.MAR_aux[overlapping_order_id])

        callbackModel.cbLazy(gp.quicksum(terms) >= 1)
        print(f"Added {gp.quicksum(terms)} >= 1")


    def get_block_bids(self, threshold: bool, reinsertion: Optional[bool] = False) -> list:
        """
        Compute accepted block orders that satisfy a condition.
        If threshold is True, compute block orders that are in-the-money by less than delta_PAB.
        If threshold is False, compute block orders that are paradoxically accepted.
        """
        res = []
        for i in list(self.block_orders['id']):
            accepted = get(self.block_orders, 'acceptance', i) > self.epsilon
            if not accepted:
                continue
            p = get(self.block_orders, 'p', i)
            q = {t: get(self.block_orders, f'q{t}', i) for t in self.periods if get(self.block_orders, f'q{t}', i) != 0}
            sale = True if sum(q.values()) > 0 else False
            type = get(self.block_orders, 'block_type', i)


            total_quantity = sum(abs(q_t) for q_t in q)
            if not reinsertion:
                weighted_mcp = sum(
                    self.prices[t] * abs(q) / total_quantity for t, q in zip(self.periods, q))
            else:
                weighted_mcp = sum(
                    self.prices_reinsertion[t] * abs(q) / total_quantity for t, q in zip(self.periods, q))


            # set right weighted_mcp in case of flexible block order
            if type == 'flexible':
                # overwrite weighted MCP with correct value considering flex_period variable
                active_period = calculate_flexible_order_active_period(master_problem=self,
                                                                       block_id=i)
                weighted_mcp = self.prices[active_period] * q[1] if not reinsertion else self.prices_reinsertion[active_period] * q[1]

            if threshold:
                if sale and weighted_mcp - self.delta_PAB < p < weighted_mcp or not sale and weighted_mcp < p < weighted_mcp - self.delta_PAB:
                    res.append(i)
            else:
                if sale and p > weighted_mcp or not sale and weighted_mcp > p:
                    res.append(i)

        path_key = 'pab' if not threshold else 'block_inm_threshold'
        file_path = f"{self.paths[path_key]}/iteration_{self.iteration}.txt"

        with open(file_path, 'w') as file:
            file.writelines(f"{bid}\n" for bid in res)

        return res


    def add_block_cut(self, single: Optional[bool] = False) -> bool:
        """
        If single is False, reject all block orders that are in-the-money by less than delta_PAB.
        If single is True, reject a single block order.
        """
        in_the_money_blocks = self.get_block_bids(threshold=True)
        if len(in_the_money_blocks) == 0:
            print("No INM block orders left to reject.")
            return False
        if not single:
            self.model.addConstrs(self.accept_block[i] == 0 for i in in_the_money_blocks)
        else:
            random_block = random.choice(in_the_money_blocks)
            self.model.addConstr(self.accept_block[random_block] == 0)

        print("Block cut successfully added.")
        return True


    def get_MIC_complex_orders(self, threshold: Optional[bool] = False, reinsertion: Optional[bool] = False) -> list:
        """
        If threshold is False, return a list with complex orders that do not have the MIC/MP condition satisfied.
        If threshold is True, return a list of complex orders that are in-the-money by at most delta_MIC.
        """
        prices = self.prices if not reinsertion else self.prices_reinsertion

        mic_complex_order_ids = self.complex_orders.loc[self.complex_orders['condition'] == 'MIC', 'id'].tolist()
        mp_complex_order_ids = self.complex_orders.loc[self.complex_orders['condition'] == 'MP', 'id'].tolist()

        res = []
        for i in mic_complex_order_ids + mp_complex_order_ids:
            accepted = get(self.complex_orders, 'acceptance', i) > self.epsilon
            if not accepted == 0:
                continue
            fixed_term = get(self.complex_orders, 'fixed_term', i)
            variable_term = get(self.complex_orders, 'variable_term', i)
            step_orders = ast.literal_eval(get(self.complex_orders, 'step_orders', i))

            expected = sum(variable_term * abs(get(self.complex_step_orders, 'q', j)) * get(self.complex_step_orders, 'acceptance', j)
                           for j in step_orders) + fixed_term
            actual = 0
            for t in self.periods:
                step_orders_t = self.complex_step_orders[
                    (self.complex_step_orders['id'].isin(step_orders)) & (self.complex_step_orders['t'] == t)][
                    'id'].tolist()

                actual += sum(
                    prices[t] *
                    abs(get(self.complex_step_orders, 'q', j)) * get(self.complex_step_orders, 'acceptance', j)
                    for j in step_orders_t)

            if not threshold:
                if i in mic_complex_order_ids and expected > actual:
                    res.append(i)
                elif i in mp_complex_order_ids and expected < actual:
                    res.append(i)
            else:
                if i in mic_complex_order_ids and expected < actual < expected + self.delta_MIC:
                    res.append(i)
                elif i in mp_complex_order_ids and expected - self.delta_MIC < actual < expected:
                    res.append(i)

            path_key = 'complex_mic_inm_threshold' if threshold else 'complex_mic'
            file_path = f"{self.paths[path_key]}/iteration_{self.iteration}.txt"

            with open(file_path, 'w') as file:
                file.writelines(f"{bid}\n" for bid in res)

        return res


    def get_MIC_scalable_orders(self, threshold: Optional[bool] = False, reinsertion: Optional[bool] = False) -> list:
        """
        If threshold is False, return a list with scalable complex orders that do not have the MIC/MP condition
        satisfied. If threshold is True, return a list of scalable complex orders that are in-the-money by at most
        delta_MIC.
        """
        prices = self.prices if not reinsertion else self.prices_reinsertion

        mic_scalable_order_ids = self.scalable_complex_orders.loc[
            self.scalable_complex_orders['condition'] == 'MIC', 'id'].tolist()
        mp_scalable_order_ids = self.scalable_complex_orders.loc[
            self.scalable_complex_orders['condition'] == 'MP', 'id'].tolist()

        res = []
        for i in mic_scalable_order_ids + mp_scalable_order_ids:
            accepted = get(self.scalable_complex_orders, 'acceptance', i) > self.epsilon
            if not accepted:
                continue
            fixed_term = get(self.scalable_complex_orders, 'fixed_term', i)
            step_orders = ast.literal_eval(get(self.scalable_complex_orders, 'step_orders', i))

            expected, actual = 0, 0
            for t in self.periods:
                step_orders_t = self.scalable_step_orders[
                    (self.scalable_step_orders['id'].isin(step_orders)) & (self.scalable_step_orders['t'] == t)][
                    'id'].tolist()

                actual += sum(
                    prices[t] *
                    abs(get(self.scalable_step_orders, 'q', j)) * get(self.scalable_step_orders, 'acceptance', j)
                    for j in step_orders_t)

                expected += sum(get(self.scalable_step_orders, 'p', j) * abs(get(self.scalable_step_orders, 'q', j)) *
                                get(self.scalable_step_orders, 'acceptance', j) for j in step_orders_t)

            expected += fixed_term

            if not threshold:
                if i in mic_scalable_order_ids and expected > actual:
                    res.append(i)
                elif i in mp_scalable_order_ids and expected < actual:
                    res.append(i)
            else:
                if i in mic_scalable_order_ids and expected < actual < expected + self.delta_MIC:
                    res.append(i)
                elif i in mp_scalable_order_ids and expected - self.delta_MIC < actual < expected:
                    res.append(i)

            path_key = 'scalable_mic_inm_threshold' if threshold else 'scalable_mic'
            file_path = f"{self.paths[path_key]}/iteration_{self.iteration}.txt"

            with open(file_path, 'w') as file:
                file.writelines(f"{bid}\n" for bid in res)

        return res


    def add_MIC_complex_cut(self, single: Optional[bool] = False) -> bool:
        """
        If single is False, add cuts to reject complex orders that are in-the-money by less than delta_MIC.
        If single is True, add a single cut.
        """
        in_the_money_MIC_complex_orders = self.get_MIC_complex_orders(threshold=True)
        if len(in_the_money_MIC_complex_orders) == 0:
            print("No INM complex MIC orders left to reject.")
            return False
        else:
            if not single:
                self.model.addConstrs(self.accept_complex[i] == 0 for i in in_the_money_MIC_complex_orders)
            else:
                random_order = random.choice(in_the_money_MIC_complex_orders)
                self.model.addConstr(self.accept_complex[random_order] == 0)

        print("MIC complex cut successfully added.")
        return True


    def add_MIC_scalable_cut(self, single: Optional[bool] = False) -> bool:
        """
        If single is False, add cuts to reject scalable complex orders that are in-the-money by less than delta_MIC.
        If single is True, add a single cut.
        """
        in_the_money_MIC_scalable_orders = self.get_MIC_scalable_orders(threshold=True)
        if len(in_the_money_MIC_scalable_orders) == 0:
            print("No INM scalable complex MIC orders left to reject.")
            return False
        else:
            if not single:
                self.model.addConstrs(self.accept_scalable[i] == 0 for i in in_the_money_MIC_scalable_orders)
            else:
                random_order = random.choice(in_the_money_MIC_scalable_orders)
                self.model.addConstr(self.accept_scalable[random_order] == 0)

        print("MIC scalable complex cut successfully added.")
        return True


    def check_in_the_money_complex(self, order_id: int) -> bool:
        """
        Check if a complex MIC/MP order is in-the-money.
        """
        pass


    def check_in_the_money_scalable(self, order_id: id) -> bool:
        """
        Check if a scalable complex order is in-the-money.
        """
        pass


    def volume_indeterminacy_subproblem(self):
        # later
        pass


    def set_prices(self, prices: dict, reinsertion: Optional[bool] = False) -> None:
        if not reinsertion:
            self.prices = prices
        else:
            self.prices_reinsertion = prices


    def get_objective(self) -> float:
        return self.model.getObjective().getValue()


    def __str__(self):
        return 'Euphemia'
