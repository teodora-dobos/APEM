from pathlib import Path
from typing import List, Optional

import pandas as pd

from apem.order_book_based_model.euphemia.data.parsing.parse_data import ParseData
from apem.order_book_based_model.euphemia.data.parsing.zonal_scenario import ZonalScenario


def ensure_zone_column(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize zone naming in an order table.

    :param df: Input table that may use a zone alias such as ``z`` or
        ``bidding_zone``.
    :return: Copy of ``df`` with a canonical string ``zone`` column. Missing
        zone information defaults to ``"Z1"``.
    """
    zone_aliases = ("zone", "z", "bidding_zone", "country", "node")
    copy = df.copy()

    source_col = None
    for candidate in zone_aliases:
        if candidate in copy.columns:
            source_col = candidate
            break

    if source_col is None:
        copy["zone"] = "Z1"
    elif source_col != "zone":
        copy = copy.rename(columns={source_col: "zone"})

    copy["zone"] = copy["zone"].fillna("Z1").astype(str)
    return copy


def parse_atc(path: Path) -> pd.DataFrame:
    """Load optional ATC network data from ``atc.csv``.

    :param path: Dataset directory that may contain ``atc.csv``.
    :return: DataFrame with canonical ATC columns ``from_zone``, ``to_zone``,
        ``t``, ``cap`` and optional ``ramp_up`` / ``ramp_down`` columns. An
        empty DataFrame is returned when no ATC file exists.
    :raises ValueError: If ``atc.csv`` is present but missing required columns.
    """
    atc_path = path / "atc.csv"
    if not atc_path.exists():
        return pd.DataFrame(columns=["from_zone", "to_zone", "t", "cap"])

    atc = pd.read_csv(atc_path)
    aliases = {
        "from": "from_zone",
        "to": "to_zone",
        "source_zone": "from_zone",
        "sink_zone": "to_zone",
        "period": "t",
        "time": "t",
        "capacity": "cap",
        "atc": "cap",
    }
    atc = atc.rename(columns={k: v for k, v in aliases.items() if k in atc.columns})

    required = {"from_zone", "to_zone", "t", "cap"}
    missing = required.difference(atc.columns)
    if missing:
        missing_cols = ", ".join(sorted(missing))
        raise ValueError(f"Invalid atc.csv: missing required column(s): {missing_cols}")

    keep_cols = ["from_zone", "to_zone", "t", "cap"]
    for optional_col in ("ramp_up", "ramp_down"):
        if optional_col in atc.columns:
            keep_cols.append(optional_col)
    atc = atc[keep_cols].copy()

    atc["from_zone"] = atc["from_zone"].astype(str)
    atc["to_zone"] = atc["to_zone"].astype(str)
    atc["t"] = atc["t"].astype(int)
    atc["cap"] = atc["cap"].astype(float)
    if "ramp_up" in atc.columns:
        atc["ramp_up"] = atc["ramp_up"].astype(float)
    if "ramp_down" in atc.columns:
        atc["ramp_down"] = atc["ramp_down"].astype(float)
    return atc


def parse_fb_constraints(path: Path) -> pd.DataFrame:
    """Load optional FBMC RAM constraints from ``fb_constraints.csv``.

    :param path: Dataset directory that may contain ``fb_constraints.csv``.
    :return: DataFrame with canonical columns ``cnec_id``, ``t``, ``ram`` and
        optional ``lb``. An empty DataFrame is returned when no FBMC constraint
        file exists.
    :raises ValueError: If the file exists but required columns are missing.
    """
    fb_path = path / "fb_constraints.csv"
    if not fb_path.exists():
        return pd.DataFrame(columns=["cnec_id", "t", "ram"])

    fb = pd.read_csv(fb_path)
    aliases = {
        "cnec": "cnec_id",
        "constraint_id": "cnec_id",
        "period": "t",
        "time": "t",
        "capacity": "ram",
    }
    fb = fb.rename(columns={k: v for k, v in aliases.items() if k in fb.columns})

    required = {"cnec_id", "t", "ram"}
    missing = required.difference(fb.columns)
    if missing:
        missing_cols = ", ".join(sorted(missing))
        raise ValueError(f"Invalid fb_constraints.csv: missing required column(s): {missing_cols}")

    lb_column = None
    for candidate in ("lb", "ram_lb", "min_ram"):
        if candidate in fb.columns:
            lb_column = candidate
            break

    keep_cols = ["cnec_id", "t", "ram"]
    if lb_column is not None:
        fb = fb.rename(columns={lb_column: "lb"})
        keep_cols.append("lb")
    fb = fb[keep_cols].copy()

    fb["cnec_id"] = fb["cnec_id"].astype(str)
    fb["t"] = fb["t"].astype(int)
    fb["ram"] = fb["ram"].astype(float)
    if "lb" in fb.columns:
        fb["lb"] = fb["lb"].astype(float)
    return fb


def parse_fb_ptdf(path: Path) -> pd.DataFrame:
    """Load optional FBMC PTDF rows from ``fb_ptdf.csv``.

    :param path: Dataset directory that may contain ``fb_ptdf.csv``.
    :return: DataFrame with canonical columns ``cnec_id``, ``t``, ``zone``,
        and ``ptdf``. An empty DataFrame is returned when no PTDF file exists.
    :raises ValueError: If the file exists but required columns are missing.
    """
    ptdf_path = path / "fb_ptdf.csv"
    if not ptdf_path.exists():
        return pd.DataFrame(columns=["cnec_id", "t", "zone", "ptdf"])

    ptdf = pd.read_csv(ptdf_path)
    aliases = {
        "cnec": "cnec_id",
        "constraint_id": "cnec_id",
        "period": "t",
        "time": "t",
        "bidding_zone": "zone",
        "z": "zone",
        "value": "ptdf",
        "factor": "ptdf",
    }
    ptdf = ptdf.rename(columns={k: v for k, v in aliases.items() if k in ptdf.columns})

    required = {"cnec_id", "t", "zone", "ptdf"}
    missing = required.difference(ptdf.columns)
    if missing:
        missing_cols = ", ".join(sorted(missing))
        raise ValueError(f"Invalid fb_ptdf.csv: missing required column(s): {missing_cols}")

    ptdf = ptdf[["cnec_id", "t", "zone", "ptdf"]].copy()
    ptdf["cnec_id"] = ptdf["cnec_id"].astype(str)
    ptdf["t"] = ptdf["t"].astype(int)
    ptdf["zone"] = ptdf["zone"].fillna("Z1").astype(str)
    ptdf["ptdf"] = ptdf["ptdf"].astype(float)
    return ptdf


def transform_step_orders(
    orders: pd.DataFrame,
    periods: List[int],
    sell: bool,
    order_id: Optional[int] = None,
    scalable: Optional[bool] = None,
) -> pd.DataFrame:
    """Convert cumulative step-order quantities into marginal bid segments.

    :param orders: Step-order table for either complex or scalable-complex
        orders.
    :param periods: Ordered list of modeled periods.
    :param sell: When ``True``, transform sell-side cumulative quantities;
        otherwise transform buy-side cumulative quantities.
    :param order_id: Optional parent order identifier used to filter rows to a
        single complex or scalable-complex order.
    :param scalable: Whether ``order_id`` refers to a scalable-complex order.
    :return: DataFrame of transformed marginal step-order rows.
    """
    id_array, t_array, p_array, q_array, complex_id_array = [], [], [], [], []
    cond_q = orders["q"] > 0 if sell else orders["q"] < 0

    cond_order_id = True
    if order_id:
        cond_order_id = orders["scalable_order_id"] == order_id if scalable else orders["complex_order_id"] == order_id

    for t in periods:
        orders_t_df = orders[(orders["t"] == t) & cond_q & cond_order_id]
        orders_t_dict = orders_t_df.to_dict(orient="records")
        first = True
        previous = None
        for order in orders_t_dict:
            id_array.append(order["id"])
            t_array.append(order["t"])
            p_array.append(order["p"])

            if order_id:
                complex_id_array.append(order["scalable_order_id"] if scalable else order["complex_order_id"])

            if first:
                q_array.append(order["q"])
            else:
                q_array.append(order["q"] - previous if sell else previous - order["q"])

            previous = order["q"]
            first = False

        if len(orders_t_df) > 0 and not sell:
            q_array[-1] = previous

    data = {"id": id_array, "t": t_array, "p": p_array, "q": q_array}
    if order_id:
        data["scalable_order_id" if scalable else "complex_order_id"] = complex_id_array

    step_orders_transformed = pd.DataFrame(data)
    return step_orders_transformed


class ParseOrderBook(ParseData):
    """Parse a Euphemia-style CSV dataset folder into a normalized scenario."""

    def __init__(self, path: Path, title: str) -> None:
        """Store dataset location and display title.

        :param path: Root directory of the order-book dataset.
        :param title: Human-readable dataset name used in outputs.
        """
        self.path = path
        self.title = title

    def parse_data(self, day: Optional[object] = None) -> ZonalScenario:
        """Read dataset CSVs and assemble a :class:`ZonalScenario`.

        The parser loads the standard order tables, period definitions, and
        optional network files from ``self.path``. Zone labels are normalized,
        missing optional network inputs are replaced with empty canonical
        tables, and the final result is returned as a model-ready scenario.

        :param day: Optional compatibility argument accepted to match the base
            parser interface. It is currently ignored.
        :return: Parsed order-book scenario ready for Euphemia.
        """
        step_orders = ensure_zone_column(pd.read_csv(self.path / "step_orders.csv"))
        block_orders = ensure_zone_column(pd.read_csv(self.path / "block_orders.csv"))
        complex_orders = pd.read_csv(self.path / "complex_orders.csv")
        complex_step_orders = ensure_zone_column(pd.read_csv(self.path / "complex_step_orders.csv"))
        scalable_complex_orders = pd.read_csv(self.path / "scalable_complex_orders.csv")
        scalable_step_orders = ensure_zone_column(pd.read_csv(self.path / "scalable_step_orders.csv"))
        piecewise_linear_orders = ensure_zone_column(pd.read_csv(self.path / "piecewise_linear_orders.csv"))
        periods_df = pd.read_csv(self.path / "periods.csv")
        periods = periods_df["period"].tolist()
        atc = parse_atc(self.path)
        fb_constraints = parse_fb_constraints(self.path)
        fb_ptdf = parse_fb_ptdf(self.path)

        zones_path = self.path / "zones.csv"
        if zones_path.exists():
            zones_df = pd.read_csv(zones_path)
            zone_col = "zone" if "zone" in zones_df.columns else (
                "z" if "z" in zones_df.columns else zones_df.columns[0]
            )
            zones = zones_df[zone_col].dropna().astype(str).unique().tolist()
        else:
            zones = sorted(
                set(step_orders["zone"])
                .union(block_orders["zone"])
                .union(complex_step_orders["zone"])
                .union(scalable_step_orders["zone"])
                .union(piecewise_linear_orders["zone"])
            )

        if not atc.empty:
            zones = sorted(set(zones).union(atc["from_zone"]).union(atc["to_zone"]))
        if not fb_ptdf.empty:
            zones = sorted(set(zones).union(fb_ptdf["zone"]))
        if not zones:
            zones = ["Z1"]

        complex_ids = complex_orders["id"].tolist()
        complex_dfs = []
        for complex_id in complex_ids:
            complex_dfs.append(
                transform_step_orders(complex_step_orders, periods, sell=True, order_id=complex_id)
            )
            complex_dfs.append(
                transform_step_orders(complex_step_orders, periods, sell=False, order_id=complex_id)
            )

        scalable_ids = scalable_complex_orders["id"].tolist()
        scalable_dfs = []
        for scalable_id in scalable_ids:
            scalable_dfs.append(
                transform_step_orders(scalable_step_orders, periods, sell=True, order_id=scalable_id, scalable=True)
            )
            scalable_dfs.append(
                transform_step_orders(scalable_step_orders, periods, sell=False, order_id=scalable_id, scalable=True)
            )

        return ZonalScenario(
            self.title,
            periods,
            step_orders,
            block_orders,
            complex_orders,
            complex_step_orders,
            scalable_complex_orders,
            scalable_step_orders,
            piecewise_linear_orders,
            zones=zones,
            atc=atc,
            fb_constraints=fb_constraints,
            fb_ptdf=fb_ptdf,
        )
