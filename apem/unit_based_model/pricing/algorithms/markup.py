import os
from typing import Optional, Union, Tuple

import numpy as np
import pandas as pd

from apem.unit_based_model.allocation.algorithms.nodal_clearing.dcopf import DCOPF
from apem.unit_based_model.allocation.allocation import Allocation
from apem.unit_based_model.allocation.configuration import Configuration
from apem.unit_based_model.allocation.error import Error
from apem.unit_based_model.data.parsing.scenario import Scenario
from apem.unit_based_model.pricing.algorithms.pricing_algorithm import PricingAlgorithm
from apem.unit_based_model.pricing.analysis.pricing import Pricing


class Markup(PricingAlgorithm):
    def compute_prices(self, scenario: Scenario, configuration: Configuration, file_prices: Optional[str] = None,
                       alpha: Optional[float] = 0) -> Union[Tuple[Allocation, Pricing], Error]:
        # first stage -> compute prices
        dcopf = DCOPF()

        modified_scenario = scenario

        # modify scenario -> scale down buyers' valuations by alpha
        val_cols = [col for col in modified_scenario.df_buyers.columns if col.startswith("val")]
        modified_scenario.df_buyers[val_cols] = modified_scenario.df_buyers[val_cols] / (1 + alpha)

        configuration.relaxation = True

        base_dir = os.path.dirname(file_prices) if file_prices else "."
        phase_dir = os.path.splitext(file_prices)[0] if file_prices else base_dir

        os.makedirs(base_dir, exist_ok=True)
        os.makedirs(phase_dir, exist_ok=True)

        results_file = os.path.join(phase_dir, f"alpha{alpha}_phase1_allocation.csv")
        stats_file = os.path.join(phase_dir, f"alpha{alpha}_phase1_stats.txt")

        initial_allocation = dcopf.solve(modified_scenario, configuration, results_file=results_file,
                                         stats_file=stats_file, shadow_prices=True, alpha=alpha)

        seller_prices_file = os.path.splitext(results_file)[0] + f"_seller_prices_alpha{alpha}.csv"
        seller_prices = pd.read_csv(seller_prices_file)
        p_vt = dict(zip(zip(seller_prices["node"], seller_prices["period"]), seller_prices["price"]))

        pricing = Pricing(node_prices=p_vt, used_algorithm='Markup')

        # second stage -> find feasible allocation
        # try out multiple thresholds
        threshold_values = np.arange(0.8, -0.01, -0.1).round(1).tolist()
        best_welfare = float('-inf')
        best_threshold = -1
        for threshold in threshold_values:
            u_fixed = {}
            for seller, period in initial_allocation.SellersAllocation.u_st:
                u_fixed[seller, period] = 1 if initial_allocation.SellersAllocation.u_st[
                                                   seller, period] > threshold else 0

            configuration.relaxation = False

            phase2_results = os.path.join(phase_dir, f"alpha{alpha}_phase2_threshold{threshold}_allocation.csv")
            phase2_stats = os.path.join(phase_dir, f"alpha{alpha}_phase2_threshold{threshold}_stats.txt")

            phase2_allocation = dcopf.solve(
                scenario, configuration,
                results_file=phase2_results,
                stats_file=phase2_stats,
                u_fixed=u_fixed
            )

            if type(phase2_allocation) == Allocation:
                if phase2_allocation.welfare > best_welfare:
                    best_welfare = phase2_allocation.welfare
                    best_threshold = threshold

        if best_threshold != -1:
            u_fixed = {}
            for seller, period in initial_allocation.SellersAllocation.u_st:
                u_fixed[seller, period] = 1 if initial_allocation.SellersAllocation.u_st[
                                                   (seller, period)] > best_threshold else 0

            final_results = os.path.join(phase_dir, f"alpha{alpha}_final_phase2_threshold{best_threshold}.csv")
            final_stats = os.path.join(phase_dir, f"alpha{alpha}_final_phase2_stats_threshold{best_threshold}.txt")

            final_allocation = dcopf.solve(
                scenario, configuration,
                results_file=final_results,
                stats_file=final_stats,
                u_fixed=u_fixed
            )

            print('-' * 50)
            print(f"Best allocation found with threshold = {best_threshold}, welfare: {best_welfare}")
            print('-' * 50)

            return final_allocation, pricing

        print(f'Could not run markup pricing - second stage infeasible')
        error = Error(-1)
        return error

    def __str__(self):
        return 'Markup'

