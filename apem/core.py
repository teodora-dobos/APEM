from enum import Enum

from apem.market_models import order_book_based_model, unit_based_model


class MarketModels(Enum):
    """Supported high-level market model families."""

    unit_based_model = unit_based_model
    order_book_based_model = order_book_based_model
