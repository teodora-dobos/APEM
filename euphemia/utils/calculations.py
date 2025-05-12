
def calculate_flexible_order_active_period(master_problem, block_id) -> int:
    from euphemia.euphemia import Euphemia
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

