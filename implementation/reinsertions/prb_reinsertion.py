from implementation.pricing.price_determination_subproblem import solve_price_determination_subproblem
from implementation.utils.extraction import get

def PRB_reinsertion(self):
    rejected_blocks = [i for i in self.block_orders['id'] if self.accept_block[i].X == 0]
    print(f"Checking {len(rejected_blocks)} rejected blocks...")
    obj = self.get_objective()
    for i in rejected_blocks:
        if check_PRB(self, i):
            print(f'Block {i} is paradoxically rejected. Attempting to activate it...')
            self.model.addConstr(self.accept_block[i] == 1, name=f'accept-{i}')
            self.solve_master_problem()
            infeasible = self.check_infeasibility(self.model, reinsertion=True)
            ok = False
            if not infeasible:
                new_obj = self.get_objective()
                if obj <= new_obj:
                    solve_price_determination_subproblem(self, reinsertion=True)
                    pab = self.get_block_bids(threshold=False, reinsertion=True)
                    if len(pab) == 0:
                        violated_complex_mic = self.get_MIC_complex_orders(reinsertion=True)
                        if len(violated_complex_mic) == 0:
                            violated_scalable_mic = self.get_MIC_scalable_orders(reinsertion=True)
                            if len(violated_scalable_mic) == 0:
                                ok = True
            if not ok:
                self.model.remove(self.model.getConstrByName(f'accept-{i}'))
                self.solve_master_problem()
                print(f'Could not activate PRB {i}.')
            else:
                self.set_prices(self.prices_reinsertion)
                print(f'Activated block {i}.')
    print('PRB reinsertion finished.')


def check_PRB(self, order: int) -> bool:
    p = get(self.block_orders, 'p', order)
    q = {t: get(self.block_orders, f'q{t}', order) for t in self.periods if
         get(self.block_orders, f'q{t}', order) != 0}
    sale = True if sum(q.values()) > 0 else False
    avg_mcp = sum(self.prices[q_t] for q_t in q.keys()) / len(q)

    if sale and p < avg_mcp or not sale and avg_mcp < p:
        return True

    return False