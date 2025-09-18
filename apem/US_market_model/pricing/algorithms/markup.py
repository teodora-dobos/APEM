from typing import Optional, Union

from apem.US_market_model.allocation.algorithms.nodal_clearing.dcopf import DCOPF
from apem.US_market_model.allocation.allocation import Allocation
from apem.US_market_model.allocation.configuration import Configuration
from apem.US_market_model.allocation.error import Error
from apem.US_market_model.data.parsing.scenario import Scenario
from apem.US_market_model.pricing.algorithms.pricing_algorithm import PricingAlgorithm
from apem.US_market_model.pricing.analysis.pricing import Pricing
from apem.enums import US_Datasets


class Markup(PricingAlgorithm):
    def compute_prices(self, allocation: Allocation, scenario: Scenario, configuration: Configuration,
                       file_prices: Optional[str] = None, alpha: Optional[float] = 0,
                       threshold: Optional[float] = 0) -> Union[Pricing, Error]:
        # modify scenario -> scale down buyers' valuations by alpha
        dcopf = DCOPF()

        modified_scenario = scenario
        modified_scenario.df_buyers['val1'] /= 1 + alpha
        modified_scenario.df_buyers['val2'] /= 1 + alpha
        modified_scenario.df_buyers['val3'] /= 1 + alpha

        configuration.relaxation = True

        # first stage -> compute prices
        initial_allocation = dcopf.solve(scenario, configuration, results_file=f'markup_phase1.csv',
                                         stats_file='markup_phase1_stats.txt', shadow_prices=True)

        # pricing = Pricing(p_vt, gamma_vwt, str(self), runtime, num_vars, num_constrs)

        # second stage -> find feasible allocation
        u_fixed = {}
        for seller, period in initial_allocation.SellersAllocation.u_st:
            u_fixed[seller, period] = 1 if initial_allocation.SellersAllocation.u_st[seller, period] > threshold else 0

        configuration.relaxation = False
        final_allocation = dcopf.solve(scenario, configuration, results_file=f'markup_phase2.csv',
                                       stats_file='markup_phase2_stats.txt', u_fixed=u_fixed)

    def __str__(self):
        return 'Markup'


markup = Markup()

scenario = US_Datasets.ARPA.value.parse_data()
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
markup.compute_prices(allocation=None, scenario=scenario, configuration=configuration, alpha=0.01)
