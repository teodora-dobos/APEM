from typing import TYPE_CHECKING

from apem.order_book_based_model.euphemia.utils.extraction import get

if TYPE_CHECKING:
    from apem.order_book_based_model.euphemia.master_problem.master_problem import MasterProblem


RejectedOrders = dict[str, list[int]]


def PRMIC_PRB_reinsertion(self: "MasterProblem", is_prmic_reinsertion: bool) -> None:
    """
    Attempt to reinsert paradoxically rejected orders after a feasible solve.

    :param is_prmic_reinsertion: When ``False``, try to reinsert paradoxically
        rejected block orders (PRBs). When ``True``, try to reinsert rejected
        complex and scalable-complex MIC or MP orders.
    """
    from apem.order_book_based_model.euphemia.master_problem.master_problem import MasterProblem

    counter = 0
    activated_order_counter = 0
    attempted_block_counter = 0
    max_block_attempts = None if is_prmic_reinsertion else self.max_prb_reinsertion_attempts
    stop_due_to_attempt_limit = False
    rejected_orders, paradoxically_rejected_orders = calculate_paradoxically_rejected_orders(self, is_prmic_reinsertion)
    print(f'Rejected orders: {rejected_orders}')


    # Search as long as there are paradoxically rejected orders
    while len(paradoxically_rejected_orders['block']) + len(paradoxically_rejected_orders['complex']) + len(paradoxically_rejected_orders['scalable_complex']) > 0:
        recalculate_list = False
        print(f"Checking {paradoxically_rejected_orders} paradoxically rejected orders...")
        # Try to activate all paradoxically rejected orders
        for order_type, ids in paradoxically_rejected_orders.items():
            break_outer_loop = False
            for id in ids:
                if (
                    not is_prmic_reinsertion
                    and order_type == 'block'
                    and max_block_attempts is not None
                    and attempted_block_counter >= max_block_attempts
                ):
                    print(f"Reached PRB reinsertion attempt limit ({max_block_attempts}).")
                    stop_due_to_attempt_limit = True
                    break

                print(f'{order_type} order {id} is paradoxically rejected. Attempting to activate it...')
                if not is_prmic_reinsertion and order_type == 'block':
                    attempted_block_counter += 1
                # New model for current reinsertion run
                reinsertion_run = MasterProblem(self.config)
                reinsertion_run.reinsertion_run = True
                reinsertion_run.current_best_objective = self.current_best_objective

                # Give Gurobi incumbent as starting point
                if is_prmic_reinsertion:
                    for _, order in self.complex_orders.iterrows():
                        reinsertion_run.accept_complex[order['id']].Start = order['acceptance']
                    for _, order in self.scalable_complex_orders.iterrows():
                        reinsertion_run.accept_scalable[order['id']].Start = order['acceptance']


                # PRB reinsertion: Fix selection of (Scalable) Complex Orders
                if not is_prmic_reinsertion:
                    for _, order in self.complex_orders.iterrows():
                        reinsertion_run.model.addConstr(reinsertion_run.accept_complex[order['id']] == order['acceptance'])
                    for _, order in self.scalable_complex_orders.iterrows():
                        reinsertion_run.model.addConstr(reinsertion_run.accept_scalable[order['id']] == order['acceptance'])
                    # Give Gurobi incumbent as starting point
                    for _, order in self.block_orders.iterrows():
                        reinsertion_run.MAR_aux[order['id']].Start = self.current_alloc_solution[f'y[{order["id"]}]'][0]

                # Activate paradoxically rejected order
                if (order_type == 'block'):
                    reinsertion_run.model.addConstr(reinsertion_run.accept_block[id] >= self.epsilon, name=f'accept-{id}')
                elif (order_type == 'complex'):
                    reinsertion_run.model.addConstr(reinsertion_run.accept_complex[id] == 1, name=f'accept-{id}')
                elif (order_type == 'scalable_complex'):
                    reinsertion_run.model.addConstr(reinsertion_run.accept_scalable[id] == 1, name=f'accept-{id}')

                reinsertion_run.run()

                if reinsertion_run.found_solution:
                    # Solution found but surplus smaller
                    if self.current_best_objective >= reinsertion_run.current_best_objective:
                        print(f'Could not activate {order_type} {id}: {self.current_best_objective}(Best objective) >= {reinsertion_run.current_best_objective}(Reinsertion run objective)')
                    # Solution found, order can be reinserted
                    else:
                        print(f'Activated {order_type} {id}.')
                        print(f'Activation of {order_type} {id} improved surplus from {self.current_best_objective} to {reinsertion_run.current_best_objective}')
                        # Save better results in master problem and recalculate order list
                        self.current_alloc_solution = reinsertion_run.current_alloc_solution
                        self.update_order_dataframes()
                        self.current_best_objective = reinsertion_run.current_best_objective
                        self.set_prices(reinsertion_run.prices, reinsertion=False)

                        activated_order_counter += 1
                        recalculate_list = True
                        break_outer_loop = True
                        break
                else:
                    print(f'Could not activate {order_type} {id}.')
                print(f'Up to this step {activated_order_counter} {"block" if not is_prmic_reinsertion else "(scalable) complex"} orders could be activated')
            if break_outer_loop:
                break
            if stop_due_to_attempt_limit:
                break

        if stop_due_to_attempt_limit:
            break

        # Recalculate the paradoxically rejected set after a successful activation.
        if recalculate_list:
            _, paradoxically_rejected_orders = calculate_paradoxically_rejected_orders(self, is_prmic_reinsertion)
        # No recalculation -> All PR orders checked
        else:
            break

    print(f'Reinsertion finished with paradoxically rejected order: {paradoxically_rejected_orders} left.')
    print(f'--- Activated {activated_order_counter} {"block" if not is_prmic_reinsertion else "(scalable) complex"} orders ---')
    if not is_prmic_reinsertion:
        print(f'--- Attempted {attempted_block_counter} block reinsertions ---')

def calculate_paradoxically_rejected_orders(
    self: "MasterProblem", is_prmic_reinsertion: bool
) -> tuple[RejectedOrders, RejectedOrders]:
    """
    Collect rejected orders and identify which of them are paradoxically rejected.

    :param is_prmic_reinsertion: Whether to inspect complex-style orders instead of
        block orders.
    :return: A pair ``(rejected_orders, paradoxically_rejected_orders)``, both
        keyed by ``block``, ``complex``, and ``scalable_complex``.
    """
    rejected_orders = {'block': [], 'complex': [], 'scalable_complex': []}
    paradoxically_rejected_orders = {'block': [], 'complex': [], 'scalable_complex': []}
    # Calculate rejected orders
    if not is_prmic_reinsertion:
        # Rejected blocks
        for _, order in self.block_orders.iterrows():
            if order['acceptance'] == 0:
                rejected_orders['block'].append(order['id'])

        # PRBs
        for id in rejected_orders['block']:
            if check_PRB(self, id):
                paradoxically_rejected_orders['block'].append(id)
    else:
        # Rejected (scalable) complex orders
        for _, order in self.complex_orders.iterrows():
            if order['acceptance'] == 0:
                rejected_orders['complex'].append(order['id'])
        for _, order in self.scalable_complex_orders.iterrows():
            if order['acceptance'] == 0:
                rejected_orders['scalable_complex'].append(order['id'])

        # PRMICs
        for id in rejected_orders['complex']:
            if check_PRCO_PRSCO(self, id, is_complex=True):
                paradoxically_rejected_orders['complex'].append(id)
        for id in rejected_orders['scalable_complex']:
            if check_PRCO_PRSCO(self, id, is_complex=False):
                paradoxically_rejected_orders['scalable_complex'].append(id)

    return rejected_orders, paradoxically_rejected_orders


def check_PRCO_PRSCO(self: "MasterProblem", id: int, is_complex: bool) -> bool:
    """
    Check whether a rejected complex-style order is paradoxically rejected.

    The test compares the order's expected MIC or MP revenue against the revenue
    implied by the current prices, while skipping load-gradient orders.

    :param id: Parent order id.
    :param is_complex: Whether the order lives in ``complex_orders`` instead of
        ``scalable_complex_orders``.
    :return: ``True`` when the rejected order could satisfy its condition at the
        current prices.
    """
    orders = self.complex_orders if is_complex else self.scalable_complex_orders
    step_orders = self.complex_step_orders if is_complex else self.scalable_step_orders
    variable_term = get(orders, 'variable_term', id) if is_complex else None
    variable_expected_value = 0
    actual_value = 0
    condition = get(orders, 'condition', id)

    if condition == 'load gradient':
        return False

    for _, step_order in step_orders.iterrows():
        # if step order is INM it could be accepted
        sign = 1 if step_order['q'] >= 0 else -1
        step_zone = self.resolve_zone(step_order.get("zone", self.default_zone))
        step_price = self.get_price_value(step_order['t'], step_zone)
        step_acceptance = sign * (step_price - step_order['p']) >= 0
        if step_order['complex_order_id' if is_complex else 'scalable_order_id'] == id:
            variable_term = step_order['p'] if not is_complex else variable_term

            variable_expected_value += step_acceptance * variable_term * abs(step_order['q'])
            actual_value += step_acceptance * abs(step_order['q']) * step_price

    expected_value = get(orders, 'fixed_term', id) + variable_expected_value

    if condition == 'MIC':
        return actual_value >= expected_value
    else:
        return actual_value <= expected_value

def check_PRB(self: "MasterProblem", order: int) -> bool:
    """
    Check whether a rejected block order is paradoxical at current prices.

    Flexible blocks are always treated as candidates. Other block orders are
    evaluated by comparing their bid price against a volume-weighted average MCP.

    :param order: Block order id.
    :return: ``True`` when the rejected block would be in the money at the
        current prices.
    """
    # Always try flexible orders
    if get(self.block_orders, f'block_type', order) == 'flexible':
        return True

    p = get(self.block_orders, 'p', order)
    zone = self.get_order_zone(self.block_orders, order)
    q = {t: get(self.block_orders, f'q{t}', order) for t in self.periods}
    sale = True if sum(q.values()) > 0 else False
    # Calculate volume weighted average MCP
    avg_mcp = sum(self.get_price_value(t, zone) * abs(q_t) / abs(sum(q.values())) for t, q_t in q.items())

    if sale and p < avg_mcp or not sale and avg_mcp < p:
        return True

    return False
