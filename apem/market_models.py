from abc import ABC, abstractmethod


class MarketModel(ABC):
    """Abstract marker base class for high-level market model families."""

    @abstractmethod
    def __str__(self):
        pass


class unit_based_model(MarketModel):
    """Unit-based market workflow family."""

    def __str__(self):
        return "unit_based_model"


class order_book_based_model(MarketModel):
    """Order-book-based (Euphemia-style) workflow family."""

    def __str__(self):
        return "order_book_based_model"
