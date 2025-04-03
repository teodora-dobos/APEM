from abc import ABC, abstractmethod
from typing import Optional

from apem.allocation.configuration import Configuration
from apem.data.parsing.scenario import Scenario


class PowerFlowModel(ABC):
    """
    Abstract class to be extended by each power flow model.
    """

    @abstractmethod
    def solve(self, scenario: Scenario, configuration: Configuration, results_file: Optional[str] = None,
              stats_file: Optional[str] = None, u_fixed: Optional[dict] = None):
        pass

    @abstractmethod
    def __str__(self):
        pass
