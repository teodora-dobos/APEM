from enum import Enum

from apem.unit_based_model.data.parsing.parse_arpa import ParseARPA
from apem.unit_based_model.data.parsing.parse_ieee_rts import ParseIEEERTS
from apem.unit_based_model.data.parsing.parse_pjm import ParsePJM
from apem.unit_based_model.data.parsing.parse_pypsa_eur_large import ParsePyPSAEurLarge
from apem.unit_based_model.data.parsing.parse_pypsa_eur_small import ParsePyPSAEurSmall


class UnitBased_Datasets(Enum):
    IEEE_RTS = ParseIEEERTS()
    PJM = ParsePJM()
    PyPSAEurSmall = ParsePyPSAEurSmall()
    PyPSAEurLarge = ParsePyPSAEurLarge()
    ARPA = ParseARPA()
