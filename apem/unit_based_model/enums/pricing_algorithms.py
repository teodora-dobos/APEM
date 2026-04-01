from enum import Enum

from apem.unit_based_model.pricing.algorithms.elmp import ELMP
from apem.unit_based_model.pricing.algorithms.ip import IP
from apem.unit_based_model.pricing.algorithms.join import Join
from apem.unit_based_model.pricing.algorithms.markup import Markup
from apem.unit_based_model.pricing.algorithms.min_mwp import MinMWP


class PricingAlgorithms(Enum):
    ELMP = ELMP()
    IP = IP()
    MinMWP = MinMWP()
    Join = Join()
    Markup = Markup()

