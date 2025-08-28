from abc import ABC, abstractmethod


class MarketModel(ABC):
    """
    Abstract class to be extended by each market model.
    """

    @abstractmethod
    def __str__(self):
        pass


class US_model(MarketModel):
    def __str__(self):
        return 'US_model'


class EU_model(MarketModel):
    def __str__(self):
        return 'EU_model'
