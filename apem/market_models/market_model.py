from abc import ABC, abstractmethod


class MarketModel(ABC):
    """
    Abstract class to be extended by each market model.
    """

    @abstractmethod
    def __str__(self):
        pass
