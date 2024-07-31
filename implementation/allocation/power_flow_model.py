from abc import ABC, abstractmethod
from typing import Optional


class PowerFlowModel(ABC):
    """Abstract class to be extended by each power flow model.
    """
    @abstractmethod
    def solve(self, scenario, configuration, file_welfare: Optional[str] = None, u_fixed: Optional[dict] = None):
        pass

    @abstractmethod
    def __str__(self):
        pass
