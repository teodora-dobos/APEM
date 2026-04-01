import pandas as pd

from apem.order_book_based_model.euphemia.utils.paths import DATA_DIR

"""
--- OMIE ---
Step 2
This script converts parsed OMIE CSV data to Euphemia-readable order tables.
"""


def has_block(group: pd.DataFrame) -> bool:
    """Return True if an OMIE offer group contains non-zero block slices."""
    return (group["num_bloq"] != 0).any()


def has_var(group: pd.DataFrame) -> bool:
    """Return True if the offer group has a positive variable term."""
    return (group["vareuro"] > 0).any()


def has_fixed(group: pd.DataFrame) -> bool:
    """Return True if the offer group has a positive fixed term."""
    return (group["fijoeuro"] > 0).any()


def has_ramp(group: pd.DataFrame) -> bool:
    """Return True when up/down ramp constraints are provided in the group."""
    ramp_cols = ["max_ram_sub", "max_ram_baj"]
    return (group[ramp_cols].fillna(0).abs().sum(axis=1) > 0).any()


def indivisible(group: pd.DataFrame) -> bool:
    """Return True if the offer behaves as indivisible in Euphemia mapping."""
    # An order is indivisible if bloq_ind == 'S' OR it contains block slices.
    return (group["bloq_ind"] == "S").any() or has_block(group)


def main() -> None:
    src = DATA_DIR / "omie" / "raw_data" / "OMIE_orderdata_parsed.csv"
    df = pd.read_csv(src)

    def sign(cv):
        return 1 if cv == "V" else -1

    complex_parents, complex_steps = [], []
    sco_parents, sco_steps = [], []

    for offer_id, group in df.groupby("cod_oferta", sort=False):
        cv = group["cv"].iloc[0]  # 'V' or 'C'

        # Priority 1: Complex order with variable term.
        if has_var(group):
            parent_type = "COMPLEX"
            fixed_term = float(group["fijoeuro"].iloc[0])
            variable_term = float(group["vareuro"].iloc[0])
            load_gradient = 0.0
            target_parent_list = complex_parents
            target_step_list = complex_steps
            map_needed = False

        # Priority 2: Block-like SCO (indivisible).
        elif indivisible(group) and has_fixed(group):
            parent_type = "SCO_BLOCK"
            fixed_term = float(group["fijoeuro"].iloc[0])
            load_gradient = 0.0
            target_parent_list = sco_parents
            target_step_list = sco_steps
            map_needed = True  # MAPh = |q_h|

        # Priority 3: Load-gradient SCO.
        elif has_ramp(group):
            parent_type = "SCO_GRAD"
            fixed_term = 0.0
            up = abs(group["max_ram_sub"].iloc[0] or 0)
            down = abs(group["max_ram_baj"].iloc[0] or 0)
            load_gradient = round((up + down) / 2, 4)
            target_parent_list = sco_parents
            target_step_list = sco_steps
            map_needed = indivisible(group)

        # Ignore the rest.
        else:
            continue

        # Sub orders.
        step_ids = []
        for _, row in group.iterrows():
            step_id = f"{offer_id}_{int(row.periodo):02d}_{int(row.num_bloq):02d}"
            step_ids.append(step_id)

            target_step_list.append(
                {
                    "id": step_id,
                    (
                        "complex_order_id"
                        if target_step_list is complex_steps
                        else "scalable_order_id"
                    ): offer_id,
                    "t": int(row["periodo"]),
                    "p": row["prec_euro"],
                    "q": sign(cv) * row["energia"],
                }
            )

        # Parent order.
        parent_row = {
            "id": offer_id,
            "step_orders": ",".join(step_ids),
            "fixed_term": fixed_term,
            **({"variable_term": variable_term} if target_parent_list is complex_parents else {}),
            "condition": (
                "MIC"
                if (parent_type in {"COMPLEX", "SCO_BLOCK"}) and cv == "V"
                else "MP"
                if (parent_type in {"COMPLEX", "SCO_BLOCK"}) and cv == "C"
                else ""
            ),
            "load_gradient": load_gradient,
        }

        # Add MAP1..MAP24 for SCOs.
        if target_parent_list is sco_parents:
            for hour in range(1, 25):
                qty = group.loc[group["periodo"] == hour, "energia"].abs().sum()
                parent_row[f"MAP{hour}"] = qty if (map_needed and qty > 0) else 0.0

        target_parent_list.append(parent_row)

    complex_parent_cols = ["id", "step_orders", "fixed_term", "variable_term", "condition", "load_gradient"]
    complex_step_cols = ["id", "complex_order_id", "t", "p", "q"]
    sco_parent_cols = ["id", "step_orders", "fixed_term", "condition", "load_gradient"] + [
        f"MAP{i}" for i in range(1, 25)
    ]
    sco_step_cols = ["id", "scalable_order_id", "t", "p", "q"]

    # If empty, still save headers.
    complex_orders_df = (
        pd.DataFrame(complex_parents) if complex_parents else pd.DataFrame(columns=complex_parent_cols)
    )
    complex_step_orders_df = (
        pd.DataFrame(complex_steps) if complex_steps else pd.DataFrame(columns=complex_step_cols)
    )
    scalable_complex_orders_df = (
        pd.DataFrame(sco_parents) if sco_parents else pd.DataFrame(columns=sco_parent_cols)
    )
    scalable_step_orders_df = (
        pd.DataFrame(sco_steps) if sco_steps else pd.DataFrame(columns=sco_step_cols)
    )

    out_dir = DATA_DIR / "omie"
    complex_orders_df.to_csv(out_dir / "complex_orders.csv", index=False)
    complex_step_orders_df.to_csv(out_dir / "complex_step_orders.csv", index=False)
    scalable_complex_orders_df.to_csv(out_dir / "scalable_complex_orders.csv", index=False)
    scalable_step_orders_df.to_csv(out_dir / "scalable_step_orders.csv", index=False)


if __name__ == "__main__":
    main()

