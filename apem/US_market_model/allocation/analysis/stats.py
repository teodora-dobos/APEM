import gurobipy as gp

from apem.US_market_model.allocation.allocation import Allocation
from apem.US_market_model.allocation.configuration import Configuration
from apem.US_market_model.data.parsing.scenario import Scenario
from apem.US_market_model.utils.extraction import preprocess_as_dict


def compute_stats(stats_file: str, scenario: Scenario, configuration: Configuration, allocation: Allocation,
                  model: gp.Model) -> None:
    """
    Creates a file with allocation statistics.
    """
    f = open(stats_file, 'w+')

    nodes = scenario.network.nodes
    buyers = scenario.df_buyers['buyer'].unique().tolist()
    sellers = scenario.df_sellers['seller'].unique().tolist()
    
    # precompute dictionaries for fast access
    buyer_val_dict, seller_cost_dict = {}, {}
    
    seller_no_load_cost_dict = preprocess_as_dict(scenario.df_sellers, ['seller', 'period'], 'no_load_cost')

    for block in scenario.blocks_buyers:
        buyer_val_dict[block] = preprocess_as_dict(scenario.df_buyers, ['buyer', 'period'], 'val', block)
            
    for block in scenario.blocks_sellers:
        seller_cost_dict[block] = preprocess_as_dict(scenario.df_sellers, ['seller', 'period'], 'cost', block)

    welfare_total = 0
    for t in scenario.periods:
        welfare_per = gp.quicksum(
            buyer_val_dict[lb][b, t] * allocation.BuyersAllocation.x_btl[b, t, lb]
            for b in buyers
            for lb in scenario.blocks_buyers
        ) - gp.quicksum(
            seller_cost_dict[ls][s, t] * allocation.SellersAllocation.y_stl[s, t, ls]
            for s in sellers
            for ls in scenario.blocks_sellers
        ) - gp.quicksum(
            seller_no_load_cost_dict[s, t] * allocation.SellersAllocation.u_st[s, t]
            for s in sellers
        )
        welfare_total += welfare_per
        f.write(f"Welfare period {t}: {welfare_per}\n")

    # Report total as the sum of per-period welfare
    f.write(f"\nTotal welfare: {welfare_total}\n")

    total_inelastic_demand = scenario.df_buyers['inelastic_dem'].sum()

    elastic_bids = ['size' + str(lb) for lb in scenario.blocks_buyers]
    elastic_demand = scenario.df_buyers[elastic_bids].sum(axis=1)
    total_elastic_demand = elastic_demand.sum()

    f.write(f"Total INELASTIC DEMAND: {total_inelastic_demand}\n")
    f.write(f"Total ELASTIC DEMAND: {total_elastic_demand}\n")

    supply_bids = ['size' + str(ls) for ls in scenario.blocks_sellers]
    supply = scenario.df_sellers[supply_bids].sum(axis=1)
    f.write(f"Total supply: {supply.sum()}\n")

    total_supply = sum(allocation.SellersAllocation.y_st[s, t] for s in sellers for t in scenario.periods)
    total_demand = sum(allocation.BuyersAllocation.x_bt[b, t] for b in buyers for t in scenario.periods)

    fulfilled_elastic_demand = sum(
        allocation.BuyersAllocation.x_btl[b, t, lb] for b in buyers for t in scenario.periods for lb in
        scenario.blocks_buyers)
    f.write(f"Fulfilled elastic demand: {fulfilled_elastic_demand}\n")

    f.write(f"Supply = {total_supply}\n")
    f.write(f"Demand = {total_demand}\n")

    if not configuration.relaxation:
        f.write(f"\nFinal MIP gap value: {model.MIPGap}\n")
    f.write(f"Nodes: {len(nodes)}\n")
    f.write(f"Branches: {int(len(allocation.TransmissionNetworkAllocation.f_vwt) / (2 * len(scenario.periods)))}\n")
    f.write(f"Buyers: {len(buyers)}\n")
    f.write(f"Sellers: {len(sellers)}\n")
    f.write(f"Constraints: {model.NumConstrs}\n")
    f.write(f"Variables: {model.NumVars}\n")
    f.write(f"Runtime in sec: {model.Runtime}\n")

    if configuration.relaxation:
        count_frac, count_binary = 0, 0
        for i in allocation.SellersAllocation.u_st.keys():
            if 0 < allocation.SellersAllocation.u_st[i] < 1:
                count_frac += 1
            else:
                count_binary += 1

        f.write(f"COUNT FRACTIONAL: {count_frac}\n")
        f.write(f"COUNT BINARY: {count_binary}\n")

    f.write(f"\nCONFIGURATION:\n")
    for key, value in vars(configuration).items():
        f.write(f"  {key}: {value}\n")
    f.write("\n")
    f.close()
