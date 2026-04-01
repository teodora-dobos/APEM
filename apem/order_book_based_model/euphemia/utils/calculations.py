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
    """
    Compute total demand-side surplus contributed by accepted block orders.

    Only block orders with at least one negative quantity (demand blocks) are
    considered. Surplus is aggregated over all periods using current prices.
    """
    total_surplus = 0.0
    for _, row in master_problem.block_orders.iterrows():
        p = row['p']
        zone = master_problem.resolve_zone(row.get("zone", master_problem.default_zone))
        if any(row.get(f'q{t}', 0) < 0 for t in master_problem.periods):
            for t in master_problem.periods:
                acceptance = row['acceptance']
                q = row.get(f'q{t}', 0)
                price = master_problem.get_price_value(t, zone)
                surplus = acceptance * (price - p) * q
                total_surplus += surplus
    return total_surplus
