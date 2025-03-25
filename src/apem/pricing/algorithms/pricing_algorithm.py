from abc import ABC, abstractmethod
from typing import Optional

from src.apem.allocation.allocation import Allocation
from src.apem.data.parsing.scenario import Scenario


class PricingAlgorithm(ABC):
    """
    Abstract class to be extended by all pricing algorithms.
    """

    @abstractmethod
    def compute_prices(self, allocation: Allocation, scenario: Scenario, file_prices: Optional[str] = None):
        pass

    @abstractmethod
    def __str__(self):
        pass
