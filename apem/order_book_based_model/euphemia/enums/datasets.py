from enum import Enum

from apem.unit_based_model.data.parsing.parse_arpa import ParseARPA
from apem.unit_based_model.data.parsing.parse_ieee_rts import ParseIEEERTS
from apem.order_book_based_model.euphemia.data.parsing.parse_order_book import ParseOrderBook
from apem.order_book_based_model.euphemia.utils.paths import DATA_DIR, CONVERTED_DATASET_PATH_MAP


class OrderBookBased_Datasets(Enum):
    """Named order-book datasets mapped to concrete ``ParseOrderBook`` parser instances."""

    GENERATED_SMALL = ParseOrderBook(DATA_DIR / "generated_small", "Generated Small")
    GENERATED_LARGE = ParseOrderBook(DATA_DIR / "generated_large", "Generated Large")
    OMIE = ParseOrderBook(DATA_DIR / "omie", "OMIE")
    GME = ParseOrderBook(DATA_DIR / "gme", "GME")
    TEST_3NODE = ParseOrderBook(DATA_DIR / "test_3node", "Test 3-Node")
    TEST_3NODE_LOWCAP = ParseOrderBook(DATA_DIR / "test_3node_lowcap", "Test 3-Node Low Capacity")
    IEEE_RTS = ParseOrderBook(CONVERTED_DATASET_PATH_MAP[ParseIEEERTS], "IEEE_RTS")
    ARPA = ParseOrderBook(CONVERTED_DATASET_PATH_MAP[ParseARPA], "ARPA")
