import pandas as pd

class ZonalScenario:
    """
    Data expected in the Euphemia implementation.
    """

    def __init__(self, name: str, periods: list, step_orders: pd.DataFrame, block_orders: pd.DataFrame,
                 complex_orders: pd.DataFrame, complex_step_orders: pd.DataFrame, scalable_complex_orders: pd.DataFrame,
                 scalable_step_orders: pd.DataFrame, piecewise_linear_orders: pd.DataFrame):
        self.name = name
        self.periods = periods
        self.step_orders = step_orders
        self.block_orders = block_orders
        self.complex_orders = complex_orders
        self.complex_step_orders = complex_step_orders
        self.scalable_complex_orders = scalable_complex_orders
        self.scalable_step_orders = scalable_step_orders
        self.piecewise_linear_orders = piecewise_linear_orders

    def __str__(self):
        return self.name

    def overview(self) -> str:
        return (f"{self.name}\n{self.periods}\n{self.step_orders}\n{self.block_orders}\n{self.complex_orders}\n"
                f"{self.complex_step_orders}\n{self.scalable_complex_orders}\n{self.scalable_step_orders}\n{self.piecewise_linear_orders}\n")

