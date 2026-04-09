from typing import Union

from apem.unit_based_model.allocation.algorithms.nodal_clearing.dcopf import DCOPF
from apem.unit_based_model.allocation.allocation import Allocation, SellersAllocation
from apem.unit_based_model.data.parsing.scenario import Scenario
from apem.unit_based_model.solver_configuration import SolverConfiguration
from apem.unit_based_model.error import Error

from apem.unit_based_model.allocation.algorithms.zonal_clearing.redispatch.redispatch_algorithm import \
    RedispatchAlgorithm


class MinAbsCostRD(RedispatchAlgorithm):
    """
    Computes a redispatch solution that minimizes the total absolute redispatch costs. Assumes that:
    - all generators can be redispatched
    - redispatch costs are based on the production costs from the zonal clearing stage.
    """

    def compute_redispatch(self, nodal_scenario: Scenario, zonal_allocation: SellersAllocation,
                           configuration: SolverConfiguration, path: str, redispatch_constraint_units: bool,
                           redispatch_threshold: float) -> Union[Allocation, Error]:
        from apem.unit_based_model.enums.redispatch_algorithms import RedispatchAlgorithms

        dcopf = DCOPF()
        return dcopf.solve(scenario=nodal_scenario, configuration=configuration,
                           results_file=path + f'/{self.__str__()}_{redispatch_constraint_units}_{redispatch_threshold}_results.csv',
                           stats_file=path + f'/{self.__str__()}_{redispatch_constraint_units}_{redispatch_threshold}_obj.txt',
                           redispatch_type=RedispatchAlgorithms.MinAbsCostRD, zonal_allocation=zonal_allocation,
                           redispatch_constraint_units=redispatch_constraint_units,
                           redispatch_threshold=redispatch_threshold)

    def __str__(self):
        return 'MinAbsCostRD'

