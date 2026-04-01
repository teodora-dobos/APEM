from enum import Enum

from apem.market_models import order_book_based_model, unit_based_model


class MarketModels(Enum):
    unit_based_model = unit_based_model
    order_book_based_model = order_book_based_model

