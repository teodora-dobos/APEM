from typing import Union

from apem.US_market_model.allocation.algorithms.nodal_clearing.dcopf import DCOPF
from apem.US_market_model.allocation.allocation import Allocation, SellersAllocation
from apem.US_market_model.data.parsing.scenario import Scenario
from apem.US_market_model.allocation.configuration import Configuration
from apem.US_market_model.allocation.error import Error

from apem.US_market_model.allocation.algorithms.zonal_clearing.redispatch.redispatch_algorithm import RedispatchAlgorithm


class MinCostRD(RedispatchAlgorithm):
    """
    Computes a redispatch solution that minimizes the total redispatch costs, i.e., the reimbursements to the
    redispatched units. Assumes that:
    - all generators can be redispatched
    - that the reimbursements are based on the production costs
    - upward and downward redispatched units are reimbursed similarly
    """

    def compute_redispatch(self, nodal_scenario: Scenario, zonal_allocation: SellersAllocation,
                           configuration: Configuration, path: str) -> Union[Allocation, Error]:
        dcopf = DCOPF()
        return dcopf.solve(scenario=nodal_scenario, configuration=configuration,
                           results_file=path + '/min_cost.csv', stats_file=path + '/min_cost_obj.txt',
                           redispatch=True, min_cost=True, zonal_allocation=zonal_allocation)

    def __str__(self):
        return 'MinCostRD'
