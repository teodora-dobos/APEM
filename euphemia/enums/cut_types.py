from enum import Enum


class CutType(Enum):
    PB = "price based"
    CB = "combinatorial benders"
    NG = "no good"
