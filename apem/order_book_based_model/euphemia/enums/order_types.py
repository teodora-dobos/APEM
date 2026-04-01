from enum import Enum


class OrderType(Enum):
    """Canonical order families used in cut metadata and diagnostics."""

    STEP = "step"
    PLO = "piecewise linear"
    BLOCK = "block"
    COMPLEX = "complex"
    SCALABLE_COMPLEX = "scalable complex"
