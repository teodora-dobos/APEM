import json
import logging
import os
import random
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from uuid import uuid4

import gurobipy as gp
import pandas as pd
from gurobipy import GRB

import apem.EU_market_model.euphemia.cutting_strategies.price_based as price_based_cutting
import apem.EU_market_model.euphemia.cutting_strategies.combinatorial_benders as combinatorial_benders_cutting
import apem.EU_market_model.euphemia.cutting_strategies.no_good as no_good_cutting
from apem.EU_market_model.euphemia.enums.cut_types import CutTypes
from apem.EU_market_model.euphemia.euphemia_config import EuphemiaConfig
from apem.EU_market_model.euphemia.model.setup_model import add_objective, add_market_constraints, \
    add_network_constraints
from apem.EU_market_model.euphemia.pricing.price_determination_subproblem import PriceSubproblem
from apem.EU_market_model.euphemia.reinsertions.prmic_prb_reinsertion import PRMIC_PRB_reinsertion
from apem.EU_market_model.euphemia.utils.calculations import calculate_flexible_order_active_period, \
    calculate_block_demand_surplus
from apem.EU_market_model.euphemia.utils.extraction import get, parse_step_order_ids


def _slugify(value: str) -> str:
    """Convert free-text labels to folder-safe identifiers."""
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def _new_run_id() -> str:
    """Create a unique run id with UTC timestamp and random suffix."""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{timestamp}_{uuid4().hex[:8]}"


class MasterProblem:
    """
    Formulate and solve the Euphemia master problem.
    """

    def __init__(self, config: EuphemiaConfig):
        if not config:
            config = EuphemiaConfig()

        self.config = config
        self.model = gp.Model('Euphemia Master Problem')
        self.scenario = config.scenario
        self.periods = self.scenario.periods
        self.step_orders = self.scenario.step_orders
        self.block_orders = self.scenario.block_orders
        self.complex_orders = self.scenario.complex_orders
        self.complex_step_orders = self.scenario.complex_step_orders
        self.scalable_complex_orders = self.scenario.scalable_complex_orders
        self.scalable_step_orders = self.scenario.scalable_step_orders
        self.piecewise_linear_orders = self.scenario.piecewise_linear_orders

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

        # Compute overlapping block orders for price-based cuts
        self.block_overlap = self.compute_block_overlaps()
        self.block_orders['overlap_set'] = self.block_orders['id'].map(self.block_overlap)

        self.current_alloc_solution = {}
        self.found_solution = False
        self.current_best_objective = -1
        self.reinsertion_run = False

        self.iteration = 0
        self.start_time = 0
        self.M = config.big_m
        self.prices = {}
        self.prices_reinsertion = {}

        self.price_lower_bound = config.price_lower_bound
        self.price_upper_bound = config.price_upper_bound
        self.delta_PAB = config.delta_PAB
        self.beta_MIC = config.beta_MIC
        self.delta_load_gradient = config.delta_load_gradient
        self.epsilon = config.epsilon
        self.max_iterations = config.max_iterations
        self.reinsertion_max_iterations = config.reinsertion_max_iterations
        self.cutting_strategy = config.cutting_strategy
        self.disable_reinsertion = config.disable_reinsertion
        self.calculate_corrected_welfare = config.calculate_corrected_welfare
        self.output_flag = config.output_flag
        self.time_limit = config.time_limit
        self.mip_gap = config.mip_gap
        self.threads = config.threads
        self.seed = config.seed
        self.lazy_constraints = config.lazy_constraints

        self.model.Params.LazyConstraints = int(self.lazy_constraints)
        self.model.setParam("OutputFlag", int(self.output_flag))
        if self.time_limit is not None:
            self.model.setParam("TimeLimit", float(self.time_limit))
        if self.mip_gap is not None:
            self.model.setParam("MIPGap", float(self.mip_gap))
        if self.threads is not None:
            self.model.setParam("Threads", int(self.threads))
        if self.seed is not None:
            self.model.setParam("Seed", int(self.seed))

        self.run_id = _new_run_id()
        self.cut_type_key = _slugify(self.cutting_strategy.value)
        self.created_at_utc = datetime.now(timezone.utc)
        self.started_at_utc = None

        project_root = Path(__file__).resolve().parents[4]
        results_root = project_root / "EU_results" / "euphemia"
        self.run_root = results_root / self.config.dataset / self.cut_type_key / self.run_id

        self.paths = {
            "alloc": self.run_root / "allocation",
            "prices": self.run_root / "prices",
            "pab": self.run_root / "pab",
            "block_inm_threshold": self.run_root / "block_inm_threshold",
            "complex_mic": self.run_root / "complex_mic",
            "complex_mic_inm_threshold": self.run_root / "complex_mic_inm_threshold",
            "scalable_mic": self.run_root / "scalable_mic",
            "scalable_mic_inm_threshold": self.run_root / "scalable_mic_inm_threshold",
            "debug": self.run_root / "debug",
            "evaluation": self.run_root / "evaluation",
        }

        for attr, path in self.paths.items():
            setattr(self, attr, path)
            os.makedirs(path, exist_ok=True)

        self.run_metadata_path = self.run_root / "run.json"
        self.run_logger = logging.getLogger(f"apem.euphemia.{self.config.dataset}.{self.cut_type_key}.{self.run_id}")
        self._setup_run_logger()
        self.run_metadata = {
            "run_id": self.run_id,
            "dataset": self.config.dataset,
            "scenario_name": self.scenario.name,
            "cut_type": self.cutting_strategy.value,
            "cut_type_key": self.cut_type_key,
            "created_at_utc": self.created_at_utc.isoformat().replace("+00:00", "Z"),
            "started_at_utc": None,
            "ended_at_utc": None,
            "status": "initialized",
            "reinsertion_run": self.reinsertion_run,
            "iteration": 0,
            "found_solution": False,
            "best_objective": None,
            "model_status": None,
            "paths": {key: str(path) for key, path in self.paths.items()},
            "run_log": str(self.run_root / "run.log"),
        }
        self._write_run_metadata()

    def _setup_run_logger(self) -> None:
        """Configure a per-run file logger."""
        self.run_logger.setLevel(logging.INFO)
        self.run_logger.propagate = False
        for handler in list(self.run_logger.handlers):
            self.run_logger.removeHandler(handler)
            handler.close()

        log_file = self.run_root / "run.log"
        handler = logging.FileHandler(log_file, mode="a", encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        self.run_logger.addHandler(handler)

    def _emit(self, message: str, level: int = logging.INFO) -> None:
        """Write a message to stdout and the per-run log file."""
        print(message)
        self.run_logger.log(level, message)

    def _safe_model_status(self):
        try:
            return int(self.model.Status)
        except Exception:  # noqa: BLE001
            return None

    def _write_run_metadata(self) -> None:
        """Persist run metadata as JSON for downstream tracking."""
        with open(self.run_metadata_path, "w", encoding="utf-8") as metadata_file:
            json.dump(self.run_metadata, metadata_file, indent=2, sort_keys=True)

    def _finalize_run_metadata(self, status: str, error: Optional[str] = None) -> None:
        elapsed_seconds = None
        if self.start_time:
            elapsed_seconds = time.time() - self.start_time

        self.run_metadata.update(
            {
                "status": status,
                "reinsertion_run": self.reinsertion_run,
                "iteration": self.iteration,
                "found_solution": self.found_solution,
                "best_objective": self.current_best_objective if self.current_best_objective >= 0 else None,
                "model_status": self._safe_model_status(),
                "ended_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "elapsed_seconds": elapsed_seconds,
            }
        )
        if error:
            self.run_metadata["error"] = error
        self._write_run_metadata()

    def run(self) -> None:
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
        self.start_time = time.time()
        self.started_at_utc = datetime.now(timezone.utc)
        self.run_metadata.update(
            {
                "started_at_utc": self.started_at_utc.isoformat().replace("+00:00", "Z"),
                "status": "running",
                "reinsertion_run": self.reinsertion_run,
                "error": None,
            }
        )
        self._write_run_metadata()

        run_status = "failed"
        run_error = None
        try:
            add_objective(self)
            add_market_constraints(self)
            add_network_constraints(self)
            self.max_iterations = self.max_iterations if not self.reinsertion_run else self.reinsertion_max_iterations

            self._emit("Solving master problem...")
            self.solve_master_problem()
            self.model.write(str(self.paths["debug"] / "master_problem.lp"))
            self._emit(f"Master problem status: {self.model.Status}")
            if self.model.Status == GRB.Status.INFEASIBLE:
                self._emit("Master problem is infeasible")
                run_status = "infeasible"
            else:
                run_status = "completed_no_solution"

            if self.found_solution:
                self._emit(
                    f"------- Surplus maximization and price problem successfully finished after {self.iteration} iterations -------"
                )
                self._emit(
                    f'Final economic surplus{" of reinsertion run" if self.reinsertion_run else ""}: {self.current_best_objective}'
                )
                self._emit(f"Found prices: {self.prices}")
                run_status = "success"

                # Log metrics for evaluation
                if not self.reinsertion_run:
                    elapsed = time.time() - self.start_time
                    file_path = self.paths["evaluation"] / "evaluation.txt"
                    with open(file_path, "a", buffering=1) as file:
                        file.write(f"--- Evaluation: {self.cutting_strategy} on {self.scenario.name} ---\n")
                        if self.cutting_strategy == CutTypes.PB:
                            file.write(
                                f"- beta_MIC: {self.beta_MIC} ; delta_load_gradient: {self.delta_load_gradient} - \n"
                            )
                        file.write(f"Iterations: {self.iteration}\n")
                        file.write(f"Final welfare: {self.current_best_objective}\n")
                        file.write(f"Time passed: {elapsed:.3f} seconds\n")
                        file.write(f"Clearing prices {self.prices}\n")
                        if self.calculate_corrected_welfare:
                            inelastic_surplus = calculate_block_demand_surplus(self)
                            file.write(f"Corrected welfare: {self.current_best_objective - inelastic_surplus}\n")
                        file.write("\n")
                        file.flush()
                        os.fsync(file.fileno())

                if not self.reinsertion_run and not self.disable_reinsertion:
                    PRMIC_PRB_reinsertion(self, is_prmic_reinsertion=True)
                    PRMIC_PRB_reinsertion(self, is_prmic_reinsertion=False)
        except Exception as exc:  # noqa: BLE001
            run_error = str(exc)
            self._emit(f"Run failed: {exc}", level=logging.ERROR)
            self.run_logger.exception("Unhandled exception during run")
            raise
        finally:
            self._finalize_run_metadata(status=run_status, error=run_error)

    def solve_master_problem(self) -> None:
        """
        Search for a selection of block and MIC orders that maximizes the economic surplus.
        The callback function is called for each valid integer solution.
        """
        self.model.optimize(callback=self.master_problem_callback)

    def master_problem_callback(self, callback_model, where) -> None:
        """
        Callback function that is executed for each valid integer solution from the master problem.

        Checks if pricing subproblem is feasible or not.
        If infeasible a lazy cut is added to the master problem.
        """

        # when a MIP solution was found
        if where == GRB.Callback.MIPSOL:
            # Check iteration limit
            if self.iteration >= self.max_iterations:
                self._emit(f"Maximum iterations ({self.max_iterations}) reached. Terminating.")
                callback_model.terminate()  # terminate optimization early
                if not self.reinsertion_run:
                    elapsed = time.time() - self.start_time
                    # Log if no solution could be found
                    file_path = self.paths["evaluation"] / "evaluation.txt"
                    with open(file_path, "a", buffering=1) as file:
                        file.write(f"--- Evaluation: {self.cutting_strategy} on {self.scenario.name} ---\n")
                        if self.cutting_strategy == CutTypes.PB:
                            file.write(
                                f"- beta_MIC: {self.beta_MIC} ; delta_load_gradient: {self.delta_load_gradient} - \n")
                        file.write(f"No solution in iteration limit of {self.max_iterations}\n")
                        file.write(f"Time passed: {elapsed:.3f} seconds\n\n")
                        file.flush()
                        os.fsync(file.fileno())
                return

            # get current solution
            objective_value = callback_model.cbGet(GRB.Callback.MIPSOL_OBJ)
            vars = callback_model.getVars()
            solution = callback_model.cbGetSolution(vars)
            if solution is not None:
                self._emit("Found integer solution")
                self._emit(f"Objective value: {objective_value}")
                self.iteration += 1

                # match variables with value in current solution
                self.current_alloc_solution = {v.VarName: [val] for v, val in zip(vars, solution)}
                self.update_order_dataframes()

                # Write current allocation solution to file
                file_path = self.paths["alloc"] / "results.txt"
                with open(file_path, "w", buffering=1) as f:
                    f.write(f"New solution with objective value {objective_value}\n")
                    for var in callback_model.getVars():
                        f.write(f"{var.VarName}: {callback_model.cbGetSolution(var)}\n")
                    f.flush()
                    os.fsync(f.fileno())

                self._emit("Solving price determination subproblem...")
                price_subproblem = PriceSubproblem(master_problem=self)
                price_subproblem.solve_price_determination_subproblem()

                # If price subproblem optimal check if new incumbent was found
                if price_subproblem.pricing_model.Status == GRB.OPTIMAL:
                    self._emit("Found market clearing prices")

                    # Write MCPs to file
                    file_path = self.paths["prices"] / "results.txt"
                    with open(file_path, "a", buffering=1) as file:  # 'a' = append
                        for v in price_subproblem.pricing_model.getVars():
                            line = f"{v.varName}: {v.X}\n"
                            file.write(line)  # to file
                            self._emit(line.rstrip())  # for console output and run log
                        file.flush()
                        os.fsync(file.fileno())

                    if objective_value > self.current_best_objective:
                        self.set_prices({int(re.search(r'\d+', var.varName).group()): var.X for var in
                                         price_subproblem.pricing_model.getVars()}, reinsertion=False)
                        self.current_best_objective = objective_value
                        self.found_solution = True

                # if price subproblem is infeasible, add cut to master problem
                if price_subproblem.pricing_model.Status == GRB.INFEASIBLE:
                    self._emit("Price subproblem is infeasible")

                    if self.cutting_strategy == CutTypes.CB:
                        combinatorial_benders_cutting.add_combinatorial_benders_cut(self=self,
                                                                                    callback_model=callback_model,
                                                                                    price_subproblem=price_subproblem)

                    elif self.cutting_strategy == CutTypes.NG:
                        no_good_cutting.add_no_good_cut(self=self, callback_model=callback_model)

                    elif self.cutting_strategy == CutTypes.PB:
                        price_based_cutting.handle_price_based_cutting(self=self, callback_model=callback_model)

    def add_acceptance_variables_to_dataframe(self) -> None:
        """
        Add reference to acceptance variable to each order in dataframe for further processing
        """

        self.step_orders['acceptance_var'] = self.step_orders['id'].map(self.accept_step)
        self.piecewise_linear_orders['acceptance_var'] = self.piecewise_linear_orders['id'].map(
            self.accept_piecewise_linear)
        self.block_orders['acceptance_var'] = self.block_orders['id'].map(self.accept_block)
        self.complex_orders['acceptance_var'] = self.complex_orders['id'].map(self.accept_complex)
        self.scalable_complex_orders['acceptance_var'] = self.scalable_complex_orders['id'].map(self.accept_scalable)

    def update_order_dataframes(self) -> None:
        """
        Add current acceptance value to order in dataframe for simplification of further processing.
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
        Can be used for Price-based cuts
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

            # Check if this is a linked parent order
            is_linked_parent = any(
                other_order['block_type'] == 'linked' and i == other_order['code_prm']
                for _, other_order in self.block_orders.iterrows()
            )

            if is_linked_parent:
                # For linked parent orders, calculate family surplus (parent + all children)
                family_surplus = 0

                # Parent surplus: acceptance * q_t * (MCP_t - p)
                parent_surplus = 0
                for t in self.periods:
                    q_t = get(self.block_orders, f'q{t}', i)
                    if q_t != 0:
                        if not reinsertion:
                            parent_surplus += get(self.block_orders, 'acceptance', i) * q_t * (self.prices[t] - p)
                        else:
                            parent_surplus += get(self.block_orders, 'acceptance', i) * q_t * (
                                    self.prices_reinsertion[t] - p)

                family_surplus += parent_surplus

                # Children surplus: Find children where code_prm == parent_id
                children_df = self.block_orders[
                    (self.block_orders['code_prm'] == i) & (self.block_orders['block_type'] == 'linked')
                    ]

                for _, child in children_df.iterrows():
                    child_id = child['id']
                    child_p = child['p']
                    child_accepted = get(self.block_orders, 'acceptance', child_id) > self.epsilon

                    if child_accepted:
                        child_surplus = 0
                        for t in self.periods:
                            child_q_t = get(self.block_orders, f'q{t}', child_id)
                            if child_q_t != 0:
                                if not reinsertion:
                                    child_surplus += get(self.block_orders, 'acceptance', child_id) * child_q_t * (
                                            self.prices[t] - child_p)
                                else:
                                    child_surplus += get(self.block_orders, 'acceptance', child_id) * child_q_t * (
                                            self.prices_reinsertion[t] - child_p)

                        family_surplus += child_surplus

                # Check if family has negative surplus (PAB condition for linked parent)
                if not threshold:
                    if family_surplus < 0:  # Family has negative surplus -> PAB
                        res.append(i)
                else:
                    pass

            else:
                # Normal block order logic (non-linked parent)
                total_quantity = sum(abs(q_t) for q_t in q.values())
                if not reinsertion:
                    weighted_mcp = sum(
                        self.prices[t] * abs(q_t) / total_quantity for t, q_t in zip(self.periods, q.values()))
                else:
                    weighted_mcp = sum(
                        self.prices_reinsertion[t] * abs(q_t) / total_quantity for t, q_t in
                        zip(self.periods, q.values()))

                # set right weighted_mcp in case of flexible block order
                if type == 'flexible':
                    # overwrite weighted MCP with correct value considering flex_period variable
                    active_period = calculate_flexible_order_active_period(master_problem=self,
                                                                           block_id=i)
                    weighted_mcp = self.prices[active_period] * q[1] if not reinsertion else self.prices_reinsertion[
                                                                                                 active_period] * q[1]

                if threshold:
                    if sale and weighted_mcp - self.delta_PAB < p < weighted_mcp or not sale and weighted_mcp < p < weighted_mcp - self.delta_PAB:
                        res.append(i)
                else:
                    if sale and p > weighted_mcp or not sale and weighted_mcp > p:
                        res.append(i)

        path_key = 'pab' if not threshold else 'block_inm_threshold'
        file_path = self.paths[path_key] / f"iteration_{self.iteration}.txt"

        with open(file_path, "w") as file:
            file.writelines(f"{bid}\n" for bid in res)

        return res

    def add_block_cut(self, single: Optional[bool] = False) -> bool:
        """
        If single is False, reject all block orders that are in-the-money by less than delta_PAB.
        If single is True, reject a single block order.
        """
        in_the_money_blocks = self.get_block_bids(threshold=True)
        if len(in_the_money_blocks) == 0:
            self._emit("No INM block orders left to reject.")
            return False
        if not single:
            self.model.addConstrs(self.accept_block[i] == 0 for i in in_the_money_blocks)
        else:
            random_block = random.choice(in_the_money_blocks)
            self.model.addConstr(self.accept_block[random_block] == 0)

        self._emit("Block cut successfully added.")
        return True

    def get_MIC_complex_orders(self, threshold: Optional[bool] = False, reinsertion: Optional[bool] = False) -> list:
        """
        If threshold is False, return a list with complex orders that do not have the MIC/MP condition satisfied.
        If threshold is True, return a list of complex orders that are out-of-the-money by at least beta_MIC * expected.
        """
        prices = self.prices if not reinsertion else self.prices_reinsertion

        mic_complex_order_ids = self.complex_orders.loc[self.complex_orders['condition'] == 'MIC', 'id'].tolist()
        mp_complex_order_ids = self.complex_orders.loc[self.complex_orders['condition'] == 'MP', 'id'].tolist()

        res = []
        for i in mic_complex_order_ids + mp_complex_order_ids:
            accepted = get(self.complex_orders, 'acceptance', i) > self.epsilon
            if not accepted:
                continue
            fixed_term = get(self.complex_orders, 'fixed_term', i)
            variable_term = get(self.complex_orders, 'variable_term', i)
            step_orders_str = get(self.complex_orders, 'step_orders', i)
            step_orders = parse_step_order_ids(step_orders_str, self.complex_step_orders)

            expected = sum(
                variable_term * abs(get(self.complex_step_orders, 'q', j)) * get(self.complex_step_orders, 'acceptance',
                                                                                 j)
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
                if i in mic_complex_order_ids and expected * (1 - self.beta_MIC) > actual:
                    res.append(i)
                elif i in mp_complex_order_ids and actual > expected * (1 + self.beta_MIC):
                    res.append(i)

            path_key = 'complex_mic_inm_threshold' if threshold else 'complex_mic'
            file_path = self.paths[path_key] / f"iteration_{self.iteration}.txt"

            with open(file_path, "w") as file:
                file.writelines(f"{bid}\n" for bid in res)

        return res

    def get_MIC_scalable_orders(self, threshold: Optional[bool] = False, reinsertion: Optional[bool] = False) -> list:
        """
        If threshold is False, return a list with scalable complex orders that do not have the MIC/MP condition
        satisfied.
        If threshold is True, return a list of scalable complex orders that are out-of-the-money by at least
        beta_MIC * expected.
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
            step_orders_str = get(self.scalable_complex_orders, 'step_orders', i)
            step_orders = parse_step_order_ids(step_orders_str, self.scalable_step_orders)

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
                if i in mic_scalable_order_ids and expected * (1 - self.beta_MIC) > actual:
                    res.append(i)
                elif i in mp_scalable_order_ids and actual > (1 + self.beta_MIC):
                    res.append(i)

            path_key = 'scalable_mic_inm_threshold' if threshold else 'scalable_mic'
            file_path = self.paths[path_key] / f"iteration_{self.iteration}.txt"

            with open(file_path, "w") as file:
                file.writelines(f"{bid}\n" for bid in res)

        return res

    def get_load_gradient_orders(self, threshold: Optional[bool] = False, reinsertion: Optional[bool] = False,
                                 complex: bool = True) -> list:
        """
        Returns a list of accepted load gradient orders (either complex or scalable complex, depending on `complex` flag)
        that have a negative total surplus.

        If `threshold=True`, only orders with total surplus < -delta_load_gradient are returned.
        If `threshold=False`, all orders with surplus < 0 are returned (i.e., paradoxically accepted).

        Parameters:
            threshold: If True, apply margin (delta_load_gradient) to determine out-of-the-money.
            reinsertion: If True, use prices from reinsertion subproblem.
            complex: If True, evaluate complex orders; otherwise evaluate scalable complex orders.
        """
        prices = self.prices if not reinsertion else self.prices_reinsertion

        # Select order and step dataframes depending on `complex` flag
        if complex:
            orders_df = self.complex_orders[
                (self.complex_orders['condition'] == 'load gradient') &
                (self.complex_orders['acceptance'] > self.epsilon)
                ]
            step_orders_df = self.complex_step_orders
            step_parent_col = 'complex_order_id'
        else:
            orders_df = self.scalable_complex_orders[
                (self.scalable_complex_orders['condition'] == 'load gradient') &
                (self.scalable_complex_orders['acceptance'] > self.epsilon)
                ]
            step_orders_df = self.scalable_step_orders
            step_parent_col = 'scalable_order_id'

        res = []

        for _, order in orders_df.iterrows():
            surplus = 0.0
            order_id = order['id']
            for _, step in step_orders_df[step_orders_df[step_parent_col] == order_id].iterrows():
                t = step['t']
                q = step['q']
                p = step['p']
                accept = step['acceptance']
                surplus += accept * q * (prices[t] - p)

            if (not threshold and surplus < 0) or (threshold and surplus < -self.delta_load_gradient):
                res.append(order_id)

        return res

    def add_MIC_complex_cut(self, single: Optional[bool] = False) -> bool:
        """
        --- Not used in current implementation ---

        If single is False, add cuts to reject complex orders that are in-the-money by less than delta_MIC.
        If single is True, add a single cut.
        """
        in_the_money_MIC_complex_orders = self.get_MIC_complex_orders(threshold=True)
        if len(in_the_money_MIC_complex_orders) == 0:
            self._emit("No INM complex MIC orders left to reject.")
            return False
        else:
            if not single:
                self.model.addConstrs(self.accept_complex[i] == 0 for i in in_the_money_MIC_complex_orders)
            else:
                random_order = random.choice(in_the_money_MIC_complex_orders)
                self.model.addConstr(self.accept_complex[random_order] == 0)

        self._emit("MIC complex cut successfully added.")
        return True

    def add_MIC_scalable_cut(self, single: Optional[bool] = False) -> bool:
        """
        --- Not used in current implementation ---

        If single is False, add cuts to reject scalable complex orders that are in-the-money by less than delta_MIC.
        If single is True, add a single cut.
        """
        in_the_money_MIC_scalable_orders = self.get_MIC_scalable_orders(threshold=True)
        if len(in_the_money_MIC_scalable_orders) == 0:
            self._emit("No INM scalable complex MIC orders left to reject.")
            return False
        else:
            if not single:
                self.model.addConstrs(self.accept_scalable[i] == 0 for i in in_the_money_MIC_scalable_orders)
            else:
                random_order = random.choice(in_the_money_MIC_scalable_orders)
                self.model.addConstr(self.accept_scalable[random_order] == 0)

        self._emit("MIC scalable complex cut successfully added.")
        return True

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
