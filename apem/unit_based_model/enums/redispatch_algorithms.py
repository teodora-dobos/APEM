from enum import Enum

from apem.unit_based_model.allocation.algorithms.zonal_clearing.redispatch.min_abs_cost import MinAbsCostRD
from apem.unit_based_model.allocation.algorithms.zonal_clearing.redispatch.min_abs_vol import MinAbsVolRD
from apem.unit_based_model.allocation.algorithms.zonal_clearing.redispatch.min_cost import MinCostRD


class RedispatchAlgorithms(Enum):
    MinAbsCostRD = MinAbsCostRD()
    MinAbsVolRD = MinAbsVolRD()
    MinCostRD = MinCostRD()

