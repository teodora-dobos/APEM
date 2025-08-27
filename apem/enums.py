from enum import Enum

from apem.data.parsing.parse_arpa import ParseARPA
from apem.data.parsing.parse_ieee_rts import ParseIEEERTS
from apem.data.parsing.parse_pjm import ParsePJM
from apem.data.parsing.parse_pypsa_eur_large import ParsePyPSAEurLarge
from apem.data.parsing.parse_pypsa_eur_small import ParsePyPSAEurSmall
from apem.pricing.algorithms.elmp import ELMP
from apem.pricing.algorithms.ip import IP
from apem.pricing.algorithms.join import Join
from apem.pricing.algorithms.min_mwp import MinMWP
from apem.allocation.algorithms.zonal_clearing.redispatch.min_cost import MinCostRD
from apem.allocation.algorithms.zonal_clearing.redispatch.min_vol import MinVolRD
from apem.allocation.algorithms.zonal_clearing.zonal_NTC import Zonal_NTC
from apem.allocation.algorithms.nodal_clearing.dcopf import DCOPF
from apem.allocation.algorithms.nodal_clearing.nodal_fbmc_included import NodalFBMC


# Only for apply_all_algorithms in execution_chain.py
class PowerFlowModels(Enum):
    DCOPF = DCOPF()
    NodalFBMC = NodalFBMC()
    Zonal_NTC = Zonal_NTC(zonal_configuration='zonal_DE4-refined',
                          factor=0.8)
    # set zonal_configuration to one of national, zonal_DE2-k, zonal_DE2-s, zonal_DE3, zonal_DE4, zonal_DE4-refined,
    # as described in zonal_configuration.py
    # the factor (between 0 and 1) describes the conservativeness of the NTC model

class PricingAlgorithms(Enum):
    ELMP = ELMP()
    IP = IP()
    MinMWP = MinMWP()
    Join = Join()


class RedispatchAlgorithms(Enum):
    MinCostRD = MinCostRD()
    MinVolRD = MinVolRD()


class Datasets(Enum):
    IEEE_RTS = ParseIEEERTS()
    PJM = ParsePJM()
    PyPSAEurSmall = ParsePyPSAEurSmall()
    PyPSAEurLarge = ParsePyPSAEurLarge()
    ARPA = ParseARPA() 