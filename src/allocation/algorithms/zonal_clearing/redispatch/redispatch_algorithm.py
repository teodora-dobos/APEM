from typing import Union

from src.allocation.allocation import Allocation, SellersAllocation
from src.allocation.configuration import Configuration
from src.allocation.error import Error
from src.data.parsing.scenario import Scenario
from abc import ABC, abstractmethod


class RedispatchAlgorithm(ABC):
    """
    Abstract class to be extended by each redispatch algorithm.
    """

    @abstractmethod
    def compute_redispatch(self, zonal_scenario: Scenario, nodal_scenario: Scenario,
                           zonal_allocation: SellersAllocation, configuration: Configuration,
                           path: str) -> Union[Allocation, Error]:
        pass

    @abstractmethod
    def __str__(self):
        pass
