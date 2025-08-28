from itertools import combinations
import os.path
from typing import Optional, Tuple, Union

import networkx as nx
import pandas as pd

from apem.allocation.algorithms.nodal_clearing.dcopf import DCOPF
from apem.allocation.allocation import Allocation
from apem.allocation.configuration import Configuration
from apem.allocation.error import Error
from apem.allocation.power_flow_model import PowerFlowModel
from apem.allocation.algorithms.zonal_clearing.zonal_configuration import node_zone_mapper
from apem.data.parsing.scenario import Scenario

class Zonal_NTC(PowerFlowModel):
    pass