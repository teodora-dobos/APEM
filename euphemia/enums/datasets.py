from enum import Enum

from apem.data.parsing.parse_arpa import ParseARPA
from apem.data.parsing.parse_ieee_rts import ParseIEEERTS
from apem.data.parsing.parse_pypsa_eur_small import ParsePyPSAEurSmall
from apem.data.parsing.parse_pypsa_eur_large import ParsePyPSAEurLarge
from apem.data.parsing.parse_pjm import ParsePJM
from euphemia.data.parsing.parse_eu import ParseEU
from euphemia.utils.paths import DATA_DIR, CONVERTED_DATASET_PATH_MAP


class Datasets(Enum):
    GENERATED_SMALL = ParseEU(DATA_DIR / "generated_small", "Generated Small")
    GENERATED_LARGE = ParseEU(DATA_DIR / "generated_large", "Generated Large")
    OMIE = ParseEU(DATA_DIR / "omie", "OMIE")
    GME = ParseEU(DATA_DIR / "gme", "GME")
    IEEE_RTS = ParseEU(CONVERTED_DATASET_PATH_MAP[ParseIEEERTS], "IEEE_RTS")
    ARPA = ParseEU(CONVERTED_DATASET_PATH_MAP[ParseARPA], "ARPA")
    PyPSAEurSmall = ParseEU(CONVERTED_DATASET_PATH_MAP[ParsePyPSAEurSmall], "PyPSAEurSmall")
    PyPSAEurLarge = ParseEU(CONVERTED_DATASET_PATH_MAP[ParsePyPSAEurLarge], "PyPSAEurLarge")
    PJM = ParseEU(CONVERTED_DATASET_PATH_MAP[ParsePJM], "PJM")
