from fontTools.merge.util import recalculate

from euphemia.utils.extraction import get
from euphemia.utils.calculations import calculate_flexible_order_active_period


def PRMIC_PRB_reinsertion(self, is_prmic_reinsertion: bool):
    from euphemia.euphemia import Euphemia

    counter = 0
    activated_order_counter = 0
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
                print(f'{order_type} order {id} is paradoxically rejected. Attempting to activate it...')
                # New model for current reinsertion run
                reinsertion_run = Euphemia(self.scenario)
                reinsertion_run.reinsertion_run = True
                reinsertion_run.current_best_objective = self.current_best_objective

                # Give Gurobi incumbent as starting point
                if is_prmic_reinsertion:
                    for _, order in self.complex_orders.iterrows():
                        reinsertion_run.accept_complex[order['id']].Start = order['acceptance']
                    for _, order in self.complex_orders.iterrows():
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

                reinsertion_run.solve()

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

        # Recalculate list with paradoxically rejected orders after reinsertion was successful
        if recalculate_list:
            _, paradoxically_rejected_orders = calculate_paradoxically_rejected_orders(self, is_prmic_reinsertion)
        # No recalculation -> All PR orders checked
        else:
            break

    print(f'Reinsertion finished with paradoxically rejected order: {paradoxically_rejected_orders} left.')
    print(f'--- Activated {activated_order_counter} {"block" if not is_prmic_reinsertion else "(scalable) complex"} orders ---')

def calculate_paradoxically_rejected_orders(self, is_prmic_reinsertion: bool):
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
            if check_PRCO_PRSCO(self, id, isComplex=True):
                paradoxically_rejected_orders['complex'].append(id)
        for id in rejected_orders['scalable_complex']:
            if check_PRCO_PRSCO(self, id, isComplex=False):
                paradoxically_rejected_orders['scalable_complex'].append(id)

    return rejected_orders, paradoxically_rejected_orders


def check_PRCO_PRSCO(self, id: int, isComplex: bool) -> bool:
    orders = self.complex_orders if isComplex else self.scalable_complex_orders
    step_orders = self.complex_step_orders if isComplex else self.scalable_step_orders
    variable_term = get(orders, 'variable_term', id) if isComplex else None
    variable_expected_value = 0
    actual_value= 0
    condition = get(orders, 'condition', id)

    if condition == 'load gradient':
        return False

    for _, step_order in step_orders.iterrows():
        step_acceptance = step_order['acceptance']
        if step_order['complex_order_id' if isComplex else 'scalable_order_id'] == id:
            variable_term = step_order['p'] if not isComplex else variable_term

            variable_expected_value += step_acceptance * variable_term * abs(step_order['q'])
            actual_value += step_acceptance * abs(step_order['q']) * self.prices[step_order['t']]

    expected_value = get(orders, 'fixed_term', id) + variable_expected_value

    if condition == 'MIC':
        return actual_value >= expected_value
    else:
        return actual_value <= expected_value

def check_PRB(self, order: int) -> bool:
    # Always try flexible orders
    if get(self.block_orders, f'block_type', order) == 'flexible':
        return True

    p = get(self.block_orders, 'p', order)
    q = {t: get(self.block_orders, f'q{t}', order) for t in self.periods}
    sale = True if sum(q.values()) > 0 else False
    # Calculate volume weighted average MCP
    avg_mcp = sum(self.prices[t] * abs(q_t) / abs(sum(q.values())) for t, q_t in q.items())

    if sale and p < avg_mcp or not sale and avg_mcp < p:
        return True

    return False
