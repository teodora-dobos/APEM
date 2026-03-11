from gurobipy import GRB
import gurobipy as gp

from apem.EU_market_model.euphemia.pricing.price_determination_subproblem import PriceSubproblem
import apem.EU_market_model.euphemia.cutting_strategies.no_good as no_good_cutting


def handle_price_based_cutting(self, callback_model) -> None:
    """
    Solve a price subproblem without any block order, complex order and scalable complex order constraints.
    Only step order and piecewise linear order constraints are included.
    """
    print("Creating unconstrained subproblem")
    price_subproblem = PriceSubproblem(master_problem=self)
    price_subproblem.isConstrained = False
    price_subproblem.solve_price_determination_subproblem()

    if price_subproblem.pricing_model.Status == GRB.OPTIMAL:
        # Update prices (No final prices!)
        self.set_prices(price_subproblem.extract_prices(), reinsertion=False)

        # Add price-based cut to block orders
        pab_blocks = self.get_block_bids(threshold=False)
        print(f"PABs: {pab_blocks}")
        for b in pab_blocks:
            block_order = self.block_orders[self.block_orders['id'] == b].iloc[0]
            add_price_based_cut_to_block(self=self, callback_model=callback_model, block_order=block_order)

        # Deactivate PAMICs/PAMPs
        terms = []
        violated_complex_mic = self.get_MIC_complex_orders(threshold=True)
        print(f"PAMIC complex: {violated_complex_mic}")
        if violated_complex_mic:
            terms.extend(self.accept_complex[i] for i in violated_complex_mic)

        violated_scalable_mic = self.get_MIC_scalable_orders(threshold=True)
        print(f"PAMIC scalable complex: {violated_scalable_mic}")
        if violated_scalable_mic:
            terms.extend(self.accept_scalable[i] for i in violated_scalable_mic)

        violated_complex_load_gradient = self.get_load_gradient_orders(threshold=True, complex=True)
        print(f"PA complex load gradient: {violated_complex_load_gradient}")
        if violated_complex_load_gradient:
            terms.extend(self.accept_complex[i] for i in violated_complex_load_gradient)

        violated_scalable_load_gradient = self.get_load_gradient_orders(threshold=True, complex=False)
        print(f"PA complex load gradient: {violated_scalable_load_gradient}")
        if violated_scalable_load_gradient:
            terms.extend(self.accept_scalable[i] for i in violated_scalable_load_gradient)

        if terms:
            print(f"Deactivate PA (scalable) complex orders: {gp.quicksum(terms)} == 0")
            callback_model.cbLazy(gp.quicksum(terms) == 0)
        # If no paradoxically accepted orders but subproblem infeasible add simple no good cut
        elif not pab_blocks:
            no_good_cutting.add_no_good_cut(self=self, callback_model=callback_model)
    else:
        print("Something went wrong and in the unconstrained problem no prices could be found")
        no_good_cutting.add_no_good_cut(self=self, callback_model=callback_model)


def add_price_based_cut_to_block(self, callback_model, block_order) -> None:
    """
    Add a lazy price-based combinatorial cut for one paradoxically accepted block.

    The cut is built from the target block plus accepted/rejected overlapping
    blocks according to buy/sell direction, then posted via ``cbLazy``.
    """
    terms = [1 - self.MAR_aux[block_order['id']]]  # (1 - ACCEPT_hat)

    def is_sale(bo_id: int) -> bool:
        return self.block_orders.loc[self.block_orders['id'] == bo_id,
        [f"q{t}" for t in self.periods]].values.sum() > 0

    for overlapping_order_id in block_order['overlap_set']:
        accepted = self.current_alloc_solution[f"y[{overlapping_order_id}]"][0] > self.epsilon
        sale = is_sale(overlapping_order_id)

        if is_sale(block_order['id']):
            if sale and accepted: terms.append(1 - self.MAR_aux[overlapping_order_id])
            if (not sale) and (not accepted): terms.append(self.MAR_aux[overlapping_order_id])
        else:
            if (not sale) and accepted: terms.append(1 - self.MAR_aux[overlapping_order_id])
            if sale and (not accepted): terms.append(self.MAR_aux[overlapping_order_id])

    callback_model.cbLazy(gp.quicksum(terms) >= 1)
    print(f"Added {gp.quicksum(terms)} >= 1")
