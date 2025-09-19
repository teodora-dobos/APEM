from typing import Optional, Union

import numpy as np
import pandas as pd

from apem.US_market_model.allocation.algorithms.nodal_clearing.dcopf import DCOPF
from apem.US_market_model.allocation.allocation import Allocation
from apem.US_market_model.allocation.configuration import Configuration
from apem.US_market_model.allocation.error import Error
from apem.US_market_model.data.parsing.scenario import Scenario
from apem.US_market_model.pricing.algorithms.pricing_algorithm import PricingAlgorithm
from apem.US_market_model.pricing.analysis.pricing import Pricing
from apem.enums import US_Datasets


class Markup(PricingAlgorithm):
    def compute_prices(self, scenario: Scenario, configuration: Configuration, file_prices: Optional[str] = None,
                       alpha: Optional[float] = 0) -> Union[Pricing, Error]:
        # first stage -> compute prices
        dcopf = DCOPF()

        modified_scenario = scenario

        # modify scenario -> scale down buyers' valuations by alpha
        val_cols = [col for col in modified_scenario.df_buyers.columns if col.startswith("val")]
        modified_scenario.df_buyers[val_cols] = modified_scenario.df_buyers[val_cols] / (1 + alpha)

        configuration.relaxation = True

        initial_allocation = dcopf.solve(modified_scenario, configuration, results_file=f'markup_phase1.csv',
                                         stats_file='markup_phase1_stats.txt', shadow_prices=True, alpha=alpha)

        seller_prices_file = 'markup_phase1.txt'.split(".", 1)[0] + f'_seller_prices_{alpha}.csv'
        seller_prices = pd.read_csv(seller_prices_file)
        p_vt = dict(zip(zip(seller_prices["node"], seller_prices["period"]), seller_prices["price"]))

        pricing = Pricing(node_prices=p_vt)

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
            final_allocation = dcopf.solve(scenario, configuration, results_file=f'markup_phase2_{threshold}.csv',
                                           stats_file=f'markup_phase2_stats_{threshold}.txt', u_fixed=u_fixed)
            if type(final_allocation) == Allocation:
                if final_allocation.welfare > best_welfare:
                    best_welfare = final_allocation.welfare
                    best_threshold = threshold

        if best_threshold != -1:
            u_fixed = {}
            for seller, period in initial_allocation.SellersAllocation.u_st:
                u_fixed[seller, period] = 1 if initial_allocation.SellersAllocation.u_st[
                                                   seller, period] > threshold else 0

            dcopf.solve(scenario, configuration, results_file=f'final_markup_phase2_{best_threshold}.csv',
                        stats_file=f'final_markup_phase2_stats_{best_threshold}.txt', u_fixed=u_fixed)

            print(f"Best allocation found with threshold = {best_threshold}, welfare: {best_welfare}")

        return pricing

    def __str__(self):
        return 'Markup'


markup = Markup()

scenario = US_Datasets.IEEE_RTS.value.parse_data()
configuration = Configuration(
    MIP_gap=1e-4,
    optimality_tol=1e-6,
    time_limit=3600,
    work_limit=3600,
    threads=0,
    presparsify=-1,
    strict_supply_demand_eq=True,
    relaxation=False,
    output_flag=0,
    verbosity=True
)
markup.compute_prices(scenario=scenario, configuration=configuration, alpha=0.01)
