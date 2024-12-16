from abc import ABC, abstractmethod
from typing import Optional

from src.allocation.configuration import Configuration
from src.data.parsing.scenario import Scenario


class PowerFlowModel(ABC):
    """
    Abstract class to be extended by each power flow model.
    """

    @abstractmethod
    def solve(self, scenario: Scenario, configuration: Configuration, file_welfare: Optional[str] = None,
              u_fixed: Optional[dict] = None):
        pass

    @abstractmethod
    def __str__(self):
        pass
