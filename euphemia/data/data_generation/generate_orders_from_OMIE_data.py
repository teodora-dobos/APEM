import pandas as pd
from euphemia.utils.paths import EUPHEMIA_ROOT

'''
--- OMIE ---
Step 2
This script can be used to convert parsed OMIE csv data to EUPHEMIA readable format
'''


src = EUPHEMIA_ROOT / "data" / "raw_data" / "omie" / "OMIE_orderdata_parsed.csv"
df  = pd.read_csv(src)

sign = lambda cv: 1 if cv == "V" else -1

def has_block(g):
    return (g["num_bloq"] != 0).any()

def has_var(g):
    return (g["vareuro"] > 0).any()

def has_fixed(g):
    return (g["fijoeuro"] > 0).any()

def has_ramp(g):
    ramp_cols = ["max_ram_sub", "max_ram_baj"]
    return (g[ramp_cols].fillna(0).abs().sum(axis=1) > 0).any()

def indivisible(g):
    # An order is indivisible if bloq_ind == 'S' OR it contains block slices
    return (g["bloq_ind"] == "S").any() or has_block(g)

complex_parents, complex_steps = [], []
sco_parents,      sco_steps    = [], []

for offer_id, g in df.groupby("cod_oferta", sort=False):
    cv = g["cv"].iloc[0]                     # 'V' or 'C'

    # ---------- Priority 1 : Complex order with variable term -------
    if has_var(g):
        parent_type = "COMPLEX"
        fixed_term  = float(g["fijoeuro"].iloc[0])
        variable_term = float(g["vareuro"].iloc[0])
        load_gradient = 0.0
        target_parent_list = complex_parents
        target_step_list   = complex_steps
        map_needed   = False

    # ---------- Priority 2 : Block-like SCO (indivisible) ------------
    elif indivisible(g) and has_fixed(g):
        parent_type = "SCO_BLOCK"
        fixed_term  = float(g["fijoeuro"].iloc[0])
        load_gradient = 0.0
        target_parent_list = sco_parents
        target_step_list   = sco_steps
        map_needed   = True          # MAPh = |q_h|

    # ---------- Priority 3 : Load-gradient SCO -----------------------
    elif has_ramp(g):
        parent_type = "SCO_GRAD"
        fixed_term  = 0.0
        # Use up/down ramps if present, else fall back to arr/par
        up = abs(g["max_ram_sub"].iloc[0] or 0)
        dn = abs(g["max_ram_baj"].iloc[0] or 0)
        load_gradient = round((up + dn) / 2, 4)
        target_parent_list = sco_parents
        target_step_list   = sco_steps
        map_needed   = indivisible(g)  # only if bloq_ind=='S'

    # Ignore the rest
    else:
        continue

    # Sub orders
    step_ids = []
    for _, r in g.iterrows():
        step_id = f"{offer_id}_{int(r.periodo):02d}_{int(r.num_bloq):02d}"
        step_ids.append(step_id)

        target_step_list.append(
            {
                "id": step_id,
                # column name differs for the two step files:
                ("complex_order_id" if target_step_list is complex_steps
                 else "scalable_order_id"): offer_id,
                "t": int(r["periodo"]),
                "p": r["prec_euro"],
                "q": sign(cv) * r["energia"]
            }
        )

    # Parent order
    parent_row = {
        "id": offer_id,
        "step_orders": ",".join(step_ids),
        "fixed_term": fixed_term,
        # complex orders have variable_term, SCOs do not
        **({"variable_term": variable_term} if target_parent_list is complex_parents else {}),
        "condition": ("MIC" if (parent_type == "COMPLEX" or parent_type == "SCO_BLOCK") and cv == "V"
                      else "MP" if (parent_type == "COMPLEX" or parent_type == "SCO_BLOCK") and cv == "C"
                      else ""),
        "load_gradient": load_gradient
    }

    # add MAP1 … MAP24 for SCOs
    if target_parent_list is sco_parents:
        for h in range(1, 25):
            qty = g.loc[g["periodo"] == h, "energia"].abs().sum()
            parent_row[f"MAP{h}"] = qty if (map_needed and qty > 0) else 0.0

    target_parent_list.append(parent_row)


complex_parent_cols = ["id", "step_orders", "fixed_term",
                       "variable_term", "condition", "load_gradient"]

complex_step_cols   = ["id", "complex_order_id", "t", "p", "q"]

sco_parent_cols     = ["id", "step_orders", "fixed_term",
                       "condition", "load_gradient"] + \
                      [f"MAP{i}" for i in range(1, 25)]

sco_step_cols       = ["id", "scalable_order_id", "t", "p", "q"]

# if empty df save headers
complex_orders_df = pd.DataFrame(complex_parents) if complex_parents else pd.DataFrame(columns=complex_parent_cols)
complex_step_orders_df = pd.DataFrame(complex_steps) if complex_steps else pd.DataFrame(columns=complex_step_cols)
scalable_complex_orders_df = pd.DataFrame(sco_parents) if sco_parents else pd.DataFrame(columns=sco_parent_cols)
scalable_step_orders_df = pd.DataFrame(sco_steps) if sco_steps else pd.DataFrame(columns=sco_step_cols)


out_dir = EUPHEMIA_ROOT / "data" / "raw_data" / "omie"
complex_orders_df.to_csv(out_dir / "complex_orders.csv",          index=False)
complex_step_orders_df.to_csv(out_dir / "complex_step_orders.csv",index=False)
scalable_complex_orders_df.to_csv(out_dir / "scalable_complex_orders.csv", index=False)
scalable_step_orders_df.to_csv(out_dir / "scalable_step_orders.csv",       index=False)
