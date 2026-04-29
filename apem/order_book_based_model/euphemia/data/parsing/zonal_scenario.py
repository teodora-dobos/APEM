import pandas as pd


class ZonalScenario:
    """Container for normalized order-book and network inputs used by Euphemia.

    The scenario stores all parsed bid tables, period definitions, zone labels,
    and optional network representations in the canonical structure expected by
    the master problem and pricing subproblem.
    """

    def __init__(
        self,
        name: str,
        periods: list,
        step_orders: pd.DataFrame,
        block_orders: pd.DataFrame,
        complex_orders: pd.DataFrame,
        complex_step_orders: pd.DataFrame,
        scalable_complex_orders: pd.DataFrame,
        scalable_step_orders: pd.DataFrame,
        piecewise_linear_orders: pd.DataFrame,
        zones: list[str] | None = None,
        atc: pd.DataFrame | None = None,
        fb_constraints: pd.DataFrame | None = None,
        fb_ptdf: pd.DataFrame | None = None,
    ) -> None:
        """Create a normalized scenario object for a parsed order-book dataset.

        :param name: Human-readable scenario name.
        :param periods: Ordered market periods modeled by the scenario.
        :param step_orders: Standard step-order bids.
        :param block_orders: Block-order bids.
        :param complex_orders: Parent complex-order definitions.
        :param complex_step_orders: Step rows associated with complex orders.
        :param scalable_complex_orders: Parent scalable-complex-order definitions.
        :param scalable_step_orders: Step rows associated with scalable-complex orders.
        :param piecewise_linear_orders: Piecewise-linear bid segments.
        :param zones: Optional explicit zone list. Defaults to ``["Z1"]``.
        :param atc: Optional ATC network table.
        :param fb_constraints: Optional FBMC constraint table.
        :param fb_ptdf: Optional FBMC PTDF table.
        """
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

    def __str__(self) -> str:
        """Return the scenario name."""
        return self.name

    def overview(self) -> str:
        """Return a multiline text dump of the scenario contents.

        :return: Human-readable summary containing all stored tables and
            metadata.
        """
        return (f"{self.name}\n{self.periods}\n{self.step_orders}\n{self.block_orders}\n{self.complex_orders}\n"
                f"{self.complex_step_orders}\n{self.scalable_complex_orders}\n{self.scalable_step_orders}\n"
                f"{self.piecewise_linear_orders}\n{self.zones}\n{self.atc}\n{self.fb_constraints}\n{self.fb_ptdf}\n")
