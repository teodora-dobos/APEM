from enum import Enum


class CutTypes(Enum):
    PB = "price based"
    CB = "combinatorial benders"
    NG = "no good"
