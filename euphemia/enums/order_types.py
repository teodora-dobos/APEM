from enum import Enum

class OrderType(Enum):
    STEP = "step"
    PLO = "piecewise linear"
    BLOCK = "block"
    COMPLEX = "complex"
    SCALABLE_COMPLEX = "scalable complex"