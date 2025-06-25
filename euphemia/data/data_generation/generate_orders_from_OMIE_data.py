import pandas as pd

from euphemia.utils.paths import RAW_DATA_DIR

'''
--- OMIE ---
Step 2
This script can be used to convert parsed OMIE csv data to EUPHEMIA readable format
'''

def generate_block_orders_from_omie(omie_df):
    block_orders = omie_df[omie_df["num_block"] != 0].copy()
    grouped = block_orders.groupby("cod_oferta")

    block_output = []
    for offer_id, group in grouped:
        q_by_hour = [0.0] * 24
        sign = 1 if group["cv"].iloc[0] == "V" else -1
        for _, row in group.iterrows():
            t = int(row["periodo"])
            if 1 <= t <= 24:
                q_by_hour[t - 1] = sign * row["cantidad"]

        block_type = "exclusive" if group["grupo_excl"].iloc[0] != 0 else "normal"

        block = {
            "id": offer_id,
            "block_type": block_type,
            "code_prm": group["grupo_excl"].iloc[0],
            "p": group["precio"].iloc[0],
            **{f"q{i+1}": q for i, q in enumerate(q_by_hour)},
            "MAR": group["mar"].iloc[0],
        }
        block_output.append(block)

    return pd.DataFrame(block_output)


def generate_sco_orders_from_omie(omie_df):
    sco_candidates = omie_df[(omie_df["fijo_eur"] > 0) & (omie_df["mav"] > 0)]
    grouped = sco_candidates.groupby("cod_oferta")

    parent_rows = []
    step_rows = []

    for sco_id, group in grouped:
        fixed_term = group["fijo_eur"].iloc[0]
        sign = 1 if group["cv"].iloc[0] == "V" else -1
        map_dict = {f"MAP{t}": 0.0 for t in range(1, 25)}
        step_ids = []

        for _, row in group.iterrows():
            t = int(row["periodo"])
            if t < 1 or t > 24:
                continue
            step_id = f"{sco_id}_{t}_{row['num_tramo']}"
            map_dict[f"MAP{t}"] = max(map_dict[f"MAP{t}"], row["mav"])
            step_ids.append(step_id)
            step_rows.append({
                "id": step_id,
                "scalable_order_id": sco_id,
                "t": t,
                "p": row["precio"],
                "q": sign * row["cantidad"]
            })

        parent = {
            "id": sco_id,
            "step_orders": ", ".join(step_ids),
            "fixed_term": fixed_term,
            "condition": "MIC" if sign == 1 else "MP",
            "load_gradient": "",
            **map_dict
        }
        parent_rows.append(parent)

    return pd.DataFrame(parent_rows), pd.DataFrame(step_rows)


def generate_complex_orders_from_omie(omie_df):
    complex_candidates = omie_df[
        (omie_df["fijo_eur"] > 0) &
        (omie_df["mav"] == 0) &
        (omie_df["mar"] == 0)
    ]
    grouped = complex_candidates.groupby("cod_oferta")

    parent_rows = []
    step_rows = []
    for cid, group in grouped:
        if group["periodo"].nunique() < 1:
            continue
        fixed_term = group["fijo_eur"].iloc[0]
        sign = 1 if group["cv"].iloc[0] == "V" else -1
        step_ids = []

        for _, row in group.iterrows():
            t = int(row["periodo"])
            if t < 1 or t > 24:
                continue
            step_id = f"{cid}_{row['periodo']}_{row['num_tramo']}"
            step_ids.append(step_id)
            step_rows.append({
                "id": step_id,
                "complex_order_id": cid,
                "t": t,
                "p": row["precio"],
                "q": sign * row["cantidad"]
            })

        parent_rows.append({
            "id": cid,
            "step_orders": ", ".join(step_ids),
            "fixed_term": fixed_term,
            "variable_term": 0.0,
            "condition": "MIC" if sign == 1 else "MP",
            "load_gradient": ""
        })

    return pd.DataFrame(parent_rows), pd.DataFrame(step_rows)



omie_df = pd.read_csv(RAW_DATA_DIR / "omie/OMIE_orderdata_parsed.csv")

# Block Orders
block_df = generate_block_orders_from_omie(omie_df)

# SCO
sco_parent_df, sco_step_df = generate_sco_orders_from_omie(omie_df)

# Complex Orders
complex_parent_df, complex_step_df = generate_complex_orders_from_omie(omie_df)


block_df.to_csv(RAW_DATA_DIR / "omie/block_orders.csv", index=False)
sco_parent_df.to_csv(RAW_DATA_DIR / "omie/scalable_complex_orders.csv", index=False)
sco_step_df.to_csv(RAW_DATA_DIR / "omie/scalable_step_orders.csv", index=False)
complex_parent_df.to_csv(RAW_DATA_DIR / "omie/complex_orders.csv", index=False)
complex_step_df.to_csv(RAW_DATA_DIR / "omie/complex_step_orders.csv", index=False)
