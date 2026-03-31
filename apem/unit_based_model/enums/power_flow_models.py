from enum import Enum

from apem.unit_based_model.allocation.algorithms.nodal_clearing.dcopf import DCOPF
from apem.unit_based_model.allocation.algorithms.zonal_clearing.zonal_fbmc_included import Zonal_FBMC
from apem.unit_based_model.allocation.algorithms.zonal_clearing.zonal_ntc_aggregated import Zonal_NTC_aggregated
from apem.unit_based_model.allocation.algorithms.zonal_clearing.zonal_ntc_multiedge import Zonal_NTC_multiedge


class PowerFlowModels(Enum):
    DCOPF = DCOPF()
    Zonal_NTC_aggregated = Zonal_NTC_aggregated(zonal_configuration="zonal_DE4", factor=0.8)
    Zonal_NTC_multiedge = Zonal_NTC_multiedge(zonal_configuration="zonal_DE4", factor=0.8)
    Zonal_FBMC = Zonal_FBMC(zonal_configuration="zonal_DE4", base_case_type="BC2")

