import re
from typing import Optional


def solve_price_determination_subproblem(self, reinsertion: Optional[bool] = False) -> None:
    """
    Compute shadow prices.
    """
    fixed_model = self.model.fixed()
    fixed_model.optimize()
    prices = {}
    for i in [i for i in fixed_model.getConstrs() if "power_balance" in i.ConstrName]:
        match = re.search(r'\[(\d+)\]', i.ConstrName)
        period = int(match.group(1))
        prices[period] = -i.getAttr("Pi")

    self.set_prices(prices, reinsertion=reinsertion)

    with open(self.paths['prices'] + f'/iteration_{self.iteration}_reinsertion_{reinsertion}.txt', 'w') as file:
        for key, value in prices.items():
            file.write(f"{key}: {value}\n")