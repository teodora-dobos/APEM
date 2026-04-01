import pandas as pd


class ZonalScenario:
    """
    Data expected in the Euphemia implementation.
    """

    def __init__(self, name: str, periods: list, step_orders: pd.DataFrame, block_orders: pd.DataFrame,
                 complex_orders: pd.DataFrame, complex_step_orders: pd.DataFrame, scalable_complex_orders: pd.DataFrame,
                 scalable_step_orders: pd.DataFrame, piecewise_linear_orders: pd.DataFrame,
                 zones: list[str] | None = None, atc: pd.DataFrame | None = None,
                 fb_constraints: pd.DataFrame | None = None, fb_ptdf: pd.DataFrame | None = None):
        self.name = name
        self.periods = periods
        self.step_orders = step_orders
        self.block_orders = block_orders
        self.complex_orders = complex_orders
        self.complex_step_orders = complex_step_orders
        self.scalable_complex_orders = scalable_complex_orders
        self.scalable_step_orders = scalable_step_orders
        self.piecewise_linear_orders = piecewise_linear_orders
        self.zones = [str(z) for z in zones] if zones else ["Z1"]
        self.atc = atc if atc is not None else pd.DataFrame(columns=["from_zone", "to_zone", "t", "cap"])
        self.fb_constraints = (
            fb_constraints if fb_constraints is not None else pd.DataFrame(columns=["cnec_id", "t", "ram"])
        )
        self.fb_ptdf = (
            fb_ptdf if fb_ptdf is not None else pd.DataFrame(columns=["cnec_id", "t", "zone", "ptdf"])
        )

    def __str__(self):
        return self.name

    def overview(self) -> str:
        return (f"{self.name}\n{self.periods}\n{self.step_orders}\n{self.block_orders}\n{self.complex_orders}\n"
                f"{self.complex_step_orders}\n{self.scalable_complex_orders}\n{self.scalable_step_orders}\n"
                f"{self.piecewise_linear_orders}\n{self.zones}\n{self.atc}\n{self.fb_constraints}\n{self.fb_ptdf}\n")


