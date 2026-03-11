from enum import Enum


class CutTypes(Enum):
    """Supported cutting strategies for the Euphemia master problem."""

    PB = "price based"
    CB = "combinatorial benders"
    NG = "no good"
