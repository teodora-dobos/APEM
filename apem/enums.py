from enum import Enum

from apem.US_market_model.data.parsing.parse_arpa import ParseARPA
from apem.US_market_model.data.parsing.parse_ieee_rts import ParseIEEERTS
from apem.US_market_model.data.parsing.parse_pjm import ParsePJM
from apem.US_market_model.data.parsing.parse_pypsa_eur_large import ParsePyPSAEurLarge
from apem.US_market_model.data.parsing.parse_pypsa_eur_small import ParsePyPSAEurSmall
from apem.market_models import US_model
from apem.market_models import EU_model
from apem.US_market_model.pricing.algorithms.elmp import ELMP
from apem.US_market_model.pricing.algorithms.ip import IP
from apem.US_market_model.pricing.algorithms.join import Join
from apem.US_market_model.pricing.algorithms.min_mwp import MinMWP
from apem.US_market_model.pricing.algorithms.markup import Markup
from apem.US_market_model.allocation.algorithms.zonal_clearing.redispatch.min_abs_cost import MinAbsCostRD
from apem.US_market_model.allocation.algorithms.zonal_clearing.redispatch.min_abs_vol import MinAbsVolRD
from apem.US_market_model.allocation.algorithms.zonal_clearing.redispatch.min_cost import MinCostRD
from apem.US_market_model.allocation.algorithms.zonal_clearing.zonal_NTC import Zonal_NTC
from apem.US_market_model.allocation.algorithms.nodal_clearing.dcopf import DCOPF


class MarketModels(Enum):
    US_model = US_model
    EU_model = EU_model


class PowerFlowModels(Enum):
    DCOPF = DCOPF()
    Zonal_NTC = Zonal_NTC()


class PricingAlgorithms(Enum):
    ELMP = ELMP()
    IP = IP()
    MinMWP = MinMWP()
    Join = Join()
    Markup = Markup()


class RedispatchAlgorithms(Enum):
    MinAbsCostRD = MinAbsCostRD()
    MinAbsVolRD = MinAbsVolRD()
    MinCostRD = MinCostRD()


class US_Datasets(Enum):
    IEEE_RTS = ParseIEEERTS()
    PJM = ParsePJM()
    PyPSAEurSmall = ParsePyPSAEurSmall()
    PyPSAEurLarge = ParsePyPSAEurLarge()
    ARPA = ParseARPA()
