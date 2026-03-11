from enum import Enum

from apem.US_market_model.data.parsing.parse_arpa import ParseARPA
from apem.US_market_model.data.parsing.parse_ieee_rts import ParseIEEERTS
from apem.EU_market_model.euphemia.data.parsing.parse_eu import ParseEU
from apem.EU_market_model.euphemia.utils.paths import DATA_DIR, CONVERTED_DATASET_PATH_MAP


class EU_Datasets(Enum):
    """Named EU datasets mapped to concrete ``ParseEU`` parser instances."""

    GENERATED_SMALL = ParseEU(DATA_DIR / "generated_small", "Generated Small")
    GENERATED_LARGE = ParseEU(DATA_DIR / "generated_large", "Generated Large")
    OMIE = ParseEU(DATA_DIR / "omie", "OMIE")
    GME = ParseEU(DATA_DIR / "gme", "GME")
    TEST_3NODE = ParseEU(DATA_DIR / "test_3node", "Test 3-Node")
    TEST_3NODE_LOWCAP = ParseEU(DATA_DIR / "test_3node_lowcap", "Test 3-Node Low Capacity")
    IEEE_RTS = ParseEU(CONVERTED_DATASET_PATH_MAP[ParseIEEERTS], "IEEE_RTS")
    ARPA = ParseEU(CONVERTED_DATASET_PATH_MAP[ParseARPA], "ARPA")
