def calculate_flexible_order_active_period(master_problem, block_id) -> int:
    """
    Calculates in which period a flexible order is active.
    """

    # list with flex_period variables for current order
    flex_vars = [
        (t, var) for (oid, t), var in master_problem.flex_period.items()
        if oid == block_id
    ]
    # Dictionary with values for each time period
    flex_vals = {
        t: master_problem.current_alloc_solution[var.VarName][0]
        for (t, var) in flex_vars
    }
    # Find time period with value 1
    return next((t for t, val in flex_vals.items() if val > 0.5), None)

def calculate_block_demand_surplus(master_problem):
    total_surplus = 0.0
    for _, row in master_problem.block_orders.iterrows():
        p = row['p']
        if any(row[f'q{t}'] < 0 for t in range(1, 25)):
            for t in range(1, 25):
                acceptance = row['acceptance']
                q = row[f'q{t}']
                price = master_problem.prices[t]
                surplus = acceptance * (price - p) * q
                total_surplus += surplus
    return total_surplus