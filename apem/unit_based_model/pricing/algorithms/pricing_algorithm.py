from abc import ABC, abstractmethod
from typing import Optional

from apem.unit_based_model.allocation.allocation import Allocation
from apem.unit_based_model.allocation.configuration import Configuration
from apem.unit_based_model.data.parsing.scenario import Scenario


class PricingAlgorithm(ABC):
    """
    Abstract class to be extended by all pricing algorithms.
    """

    @abstractmethod
    def compute_prices(self, allocation: Allocation, scenario: Scenario, configuration: Configuration, file_prices: Optional[str] = None):
        pass

    @abstractmethod
    def __str__(self):
        pass

