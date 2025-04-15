import ast
import os
import random
import shutil
from typing import Optional
import gurobipy as gp
from gurobipy import GRB

from implementation.data.parsing.zonal_scenario import ZonalScenario
from implementation.model.setup_model import add_objective, add_market_constraints, add_network_constraints
from implementation.pricing.price_determination_subproblem import Price_Subproblem
from implementation.reinsertions.prb_reinsertion import PRB_reinsertion
from implementation.utils.extraction import get


class Euphemia:
    def __init__(self, scenario: ZonalScenario):
        self.model = gp.Model('Euphemia')
        self.periods = scenario.periods
        self.step_orders = scenario.step_orders
        self.block_orders = scenario.block_orders
        self.complex_orders = scenario.complex_orders
        self.complex_step_orders = scenario.complex_step_orders
        self.scalable_complex_orders = scenario.scalable_complex_orders
        self.scalable_step_orders = scenario.scalable_step_orders

        self.accept_step = self.model.addVars(list(self.step_orders['id']), vtype=GRB.CONTINUOUS, lb=0, ub=1,
                                              name='accept_step')
        self.accept_block = self.model.addVars(list(self.block_orders['id']), vtype=GRB.BINARY, lb=0, ub=1,
                                               name='accept_block')
        # required for the big-M constraint to satisfy the MAR condition of block orders
        self.MAR_aux = self.model.addVars(list(self.block_orders['id']), vtype=GRB.BINARY, name='y')

        # required for flexible orders - decide in which period the order is accepted
        self.flex_period = self.model.addVars(
            list(self.block_orders[self.block_orders['block_type'] == 'flexible']['id']), self.periods,
            vtype=GRB.BINARY, name='flex_period')
        self.accept_complex = self.model.addVars(list(self.complex_orders['id']), vtype=GRB.BINARY, lb=0, ub=1,
                                                 name='accept_mic_complex')
        self.accept_complex_step = self.model.addVars(list(self.complex_step_orders['id']), vtype=GRB.CONTINUOUS,
                                                      lb=0, ub=1, name='accept_complex_step')
        self.accept_scalable = self.model.addVars(list(self.scalable_complex_orders['id']), vtype=GRB.BINARY,
                                                  lb=0, ub=1, name='accept_mic_scalable')
        self.accept_scalable_step = self.model.addVars(list(self.scalable_step_orders['id']), vtype=GRB.CONTINUOUS,
                                                       lb=0, ub=1, name='accept_scalable_step')

        # Make additional cuts in MIPSOL callback possible
        self.model.Params.LazyConstraints = 1

        # Needed to avoid race conditions
        #self.model.setParam("Threads", 1)
        # Variable to save branching decisions
        self.fixed_accepts = []
        # Make model branch
        # self.model.setParam("Presolve", 0)  # kein klassisches Presolve
        # self.model.setParam("Cuts", 0)  # keine automatischen Schnitte (Cuts)
        # self.model.setParam("Heuristics", 0)  # keine Heuristiklösungen
        # self.model.setParam("AggFill", 0)  # keine Aggregation
        # self.model.setParam("Aggregate", 0)  # keine Spaltenaggregation
        # self.model.setParam("Symmetry", 0)  # keine Symmetrieerkennung
        # self.model.setParam("PrePasses", 0)  # keine extra Presolve-Passes
        # self.model.setParam("Method", 1)  # Simplex (nicht Barrier) für LP
        # self.model.setParam("VarBranch", 0)  # Standard-Branching
        # self.model.setParam("NodefileStart", 0.5)  # Speichert Knoten ggf. auf Festplatte
        # self.model.setParam("Threads", 1)
        # self.model.setParam("RINS", 0)
        # self.model.setParam("Disconnected", 0)
        # self.model.Params.OutputFlag = 1
        # self.model.setParam("MIPFocus", 3)


        self.M = 10 ** 6
        self.prices = {}
        self.prices_reinsertion = {}
        self.price_lower_bound = -500
        self.price_upper_bound = 4000
        self.delta_PAB = 50
        self.delta_MIC = 50
        self.max_iterations = 30
        self.iteration = 0
        self.epsilon = 1e-5
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

        print("Solving master problem...")
        self.solve_master_problem()



        #
        # print("Computing PAB...")
        # pab = self.get_block_bids(threshold=False)
        # if len(pab) > 0:
        #     success = False
        #     print(f"There are {len(pab)} PAB. Adding block cut...")
        #     cut_added = self.add_block_cut()
        #     increase_count = 0
        #     while not cut_added and increase_count < 5:
        #         increase_count += 1
        #         self.delta_PAB += 10
        #         print(f"Increasing delta_PAB to {self.delta_PAB}.\n")
        #         cut_added = self.add_block_cut()
        #
        #     if not cut_added:
        #         print("Reject PAB.")
        #         self.model.addConstrs(self.accept_block[i] == 0 for i in pab)
        #
        #     self.delta_PAB -= 10 * increase_count
        #     self.iteration += 1
        #     continue
        #
        # print("No PAB.")
        #
        # print("Computing complex orders with MIC/MP condition violated...")
        # violated_MIC_MP_complex = self.get_MIC_complex_orders(threshold=False)
        # if len(violated_MIC_MP_complex) > 0:
        #     success = False
        #     print(f"MIC/MP conditions violated in {len(violated_MIC_MP_complex)} complex orders.")
        #     cut_added = self.add_MIC_complex_cut()
        #     increase_count = 0
        #     while not cut_added and increase_count < 5:
        #         increase_count += 1
        #         self.delta_MIC += 10
        #         print(f"Increasing delta_MIC to {self.delta_MIC}.\n")
        #         cut_added = self.add_MIC_complex_cut()
        #
        #     if not cut_added:
        #         print("Reject complex orders with MIC condition violated.")
        #         self.model.addConstrs(self.accept_complex[i] == 0 for i in violated_MIC_MP_complex)
        #
        #     self.delta_MIC -= 10 * increase_count
        #     self.iteration += 1
        #     continue
        #
        # print(f"MIC condition satisfied in complex orders.")
        #
        # print("Computing scalable complex orders with MIC/MP condition violated...")
        # violated_MIC_MP_scalable = self.get_MIC_scalable_orders(threshold=False)
        # if len(violated_MIC_MP_scalable) > 0:
        #     success = False
        #     print(f"MIC/MP conditions violated in {len(violated_MIC_MP_scalable)} scalable complex orders.")
        #     cut_added = self.add_MIC_scalable_cut()
        #     increase_count = 0
        #     while not cut_added and increase_count < 5:
        #         increase_count += 1
        #         self.delta_MIC += 10
        #         print(f"Increasing delta_MIC to {self.delta_MIC}.\n")
        #         cut_added = self.add_MIC_scalable_cut()
        #
        #     if not cut_added:
        #         print("Reject scalable complex orders with MIC condition violated.")
        #         self.model.addConstrs(self.accept_scalable[i] == 0 for i in violated_MIC_MP_scalable)
        #
        #     self.delta_MIC -= 10 * increase_count
        #     self.iteration += 1
        #     continue
        #
        # print(f"MIC condition satisfied in scalable complex orders.")
        #
        # print("\nPRB reinsertion...\n")
        # PRB_reinsertion(self)

        print(f'Final economic surplus: {self.get_objective()}')


    def check_infeasibility(self, model: gp.Model, reinsertion: Optional[bool] = False) -> bool:
        """
        Check if model is infeasible. If applicable, compute an Irreducible Inconsistent Subsystem (IIS).
        """
        try:
            if model.status == GRB.INFEASIBLE:
                print("Model is infeasible. Computing IIS...")
                model.computeIIS()
                iis_file = os.path.join(self.paths['debug'],
                                        f"master_iip_{self.iteration}_reinsertion_{reinsertion}.ilp")
                model.write(iis_file)
                print(f"IIS file saved at: {iis_file}")
                return True
            else:
                return False
        except gp.GurobiError as e:
            print(f'An error occurred while checking infeasibility: {e}')


    def solve_master_problem(self) -> None:
        """
        Search for a selection of block and MIC orders that maximizes the economic surplus.
        """
        self.model.optimize(callback=self.master_problem_callback)


    def master_problem_callback(self, callbackModel, where) -> None:
        # if where == GRB.Callback.MIPNODE:
        #     print("MIPNODE callback")
        #     fixed = []
        #     for v in callbackModel.getVars():
        #         lb = callbackModel.cbGet(GRB.Callback.MIPNODE_VARLB, v)
        #         ub = callbackModel.cbGet(GRB.Callback.MIPNODE_VARUB, v)
        #         if abs(lb - ub) < 1e-6:
        #             fixed.append((v, lb))
        #         print(lb)
        #     self.fixed_accepts = fixed

        # when a MIP solution was found
        if where == GRB.Callback.MIPSOL:
            # get current solution
            objective_value = callbackModel.cbGet(GRB.Callback.MIPSOL_OBJ)
            vars = callbackModel.getVars()
            solution = callbackModel.cbGetSolution(vars)
            if solution is not None:
                print("Found integer solution")
                print("Objective value:", objective_value)

                # match variables with value in current solution
                solution_dict = {v.VarName: [val] for v, val in zip(vars, solution)}

                print("Solving price determination subproblem...")
                price_subproblem = Price_Subproblem(master_problem=self, solution_dict=solution_dict)
                price_subproblem.solve_price_determination_subproblem()

                # if price subproblem feasible check if new incumbent
                if price_subproblem.pricing_model.status == GRB.OPTIMAL:
                    print("Found market clearing prices")

                    file_path = f"{self.paths['alloc']}/results.txt"
                    with open(file_path, 'w') as file:
                        for v in price_subproblem.pricing_model.getVars():
                            print(f"{v.varName}: {v.x}")
                        file.writelines("Continuos variables:\n")
                        for var in callbackModel.getVars():
                            if var.VType == GRB.CONTINUOUS:
                                file.write(f"{var.VarName}: {callbackModel.cbGetSolution(var)}\n")

                # if price subproblem infeasible add cut to master problem
                if price_subproblem.pricing_model.status == GRB.INFEASIBLE:
                    print("Price subproblem is infeasible")
                    price_subproblem.pricing_model.computeIIS()

                    problematic_constraints = []
                    problematic_bounds = []

                    for constr in price_subproblem.pricing_model.getConstrs():
                        if constr.IISConstr:
                            print(f"Infeasible constraint: {constr}")
                            problematic_constraints.append(constr)
                            callbackModel.cbLazy(price_subproblem.cuts[constr.ConstrName])
                    for var in price_subproblem.pricing_model.getVars():
                        if var.IISLB:
                            print(f"Variable {var.VarName}: untere Schranke verletzt (LB = {var.LB})")
                        if var.IISUB:
                            print(f"Variable {var.VarName}: obere Schranke verletzt (UB = {var.UB})")

                    #self.addNoGoodCut(callbackModel, solution_dict)





    def addNoGoodCut(self, callbackModel, solution_dict) -> None:
        # create cut that makes current solution invalid
        terms = []
        # match variable from current solution with gurobi variable from model
        for gurobi_acceptance_var in callbackModel.getVars():
            if gurobi_acceptance_var.VType == GRB.BINARY:
                solution_value = solution_dict.get(gurobi_acceptance_var.VarName)
                if solution_value is None:
                    print(f"{gurobi_acceptance_var.VarName} not found in solution dict")
                    continue
                #print(f"{gurobi_acceptance_var.VarName} -> {solution_value}")
                if solution_value[0] > 0.5:
                    terms.append(1 - gurobi_acceptance_var)
                else:
                    terms.append(gurobi_acceptance_var)
        expr = gp.quicksum(terms)
        callbackModel.cbLazy(expr >= 1)
        print(f"Added cut: {expr} >= 1")



    def get_block_bids(self, threshold: bool, reinsertion: Optional[bool] = False) -> list:
        """
        Compute accepted block orders that satisfy a condition.
        If threshold is True, compute block orders that are in-the-money by less than delta_PAB.
        If threshold is False, compute block orders that are paradoxically accepted.
        """
        res = []
        for i in list(self.block_orders['id']):
            if self.accept_block[i].X == 0:
                continue
            p = get(self.block_orders, 'p', i)
            q = {t: get(self.block_orders, f'q{t}', i) for t in self.periods if get(self.block_orders, f'q{t}', i) != 0}
            sale = True if sum(q.values()) > 0 else False

            if not reinsertion:
                avg_mcp = sum(self.prices[q_t] for q_t in q.keys()) / len(q)
            else:
                avg_mcp = sum(self.prices_reinsertion[q_t] for q_t in q.keys()) / len(q)

            if threshold:
                if sale and avg_mcp - self.delta_PAB < p < avg_mcp or not sale and avg_mcp < p < avg_mcp - self.delta_PAB:
                    res.append(i)
            else:
                if sale and p > avg_mcp or not sale and avg_mcp > p:
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
            if self.accept_complex[i].X == 0:
                continue
            fixed_term = get(self.complex_orders, 'fixed_term', i)
            variable_term = get(self.complex_orders, 'variable_term', i)
            step_orders = ast.literal_eval(get(self.complex_orders, 'step_orders', i))

            expected = sum(variable_term * abs(get(self.complex_step_orders, 'q', j)) * self.accept_complex_step[j].X
                           for j in step_orders) + fixed_term
            actual = 0
            for t in self.periods:
                step_orders_t = self.complex_step_orders[
                    (self.complex_step_orders['id'].isin(step_orders)) & (self.complex_step_orders['t'] == t)][
                    'id'].tolist()

                if i in mic_complex_order_ids:
                    actual += sum(
                        (prices[t] - get(self.complex_step_orders, 'p', j)) *
                        abs(get(self.complex_step_orders, 'q', j)) * self.accept_complex_step[j].X
                        for j in step_orders_t)
                else:
                    actual += sum(
                        prices[t] *
                        abs(get(self.complex_step_orders, 'q', j)) * self.accept_complex_step[j].X
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
            if self.accept_scalable[i].X == 0:
                continue
            fixed_term = get(self.scalable_complex_orders, 'fixed_term', i)
            step_orders = ast.literal_eval(get(self.scalable_complex_orders, 'step_orders', i))

            expected, actual = 0, 0
            for t in self.periods:
                step_orders_t = self.scalable_step_orders[
                    (self.scalable_step_orders['id'].isin(step_orders)) & (self.scalable_step_orders['t'] == t)][
                    'id'].tolist()

                if i in mic_scalable_order_ids:
                    actual += sum(
                        (prices[t] - get(self.scalable_step_orders, 'p', j)) *
                        abs(get(self.scalable_step_orders, 'q', j)) * self.accept_scalable_step[j].X
                        for j in step_orders_t)
                else:
                    actual += sum(
                        prices[t] *
                        abs(get(self.scalable_step_orders, 'q', j)) * self.accept_scalable_step[j].X
                        for j in step_orders_t)

                expected += sum(get(self.scalable_step_orders, 'p', j) * abs(get(self.scalable_step_orders, 'q', j)) *
                                self.accept_scalable_step[j].X for j in step_orders_t)

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
