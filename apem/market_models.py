from abc import ABC, abstractmethod


class MarketModel(ABC):
    """
    Abstract class to be extended by each market model.
    """

    @abstractmethod
    def __str__(self):
        pass


class unit_based_model(MarketModel):
    def __str__(self):
        return 'unit_based_model'


class order_book_based_model(MarketModel):
    def __str__(self):
        return 'order_book_based_model'

