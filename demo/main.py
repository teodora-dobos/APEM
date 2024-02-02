from demo.allocation.allocation import Allocation
from demo.data.parse_data import parse_data
from demo.pricing.ip import IP
from demo.data.market_data import MarketData
from demo.pricing.price_analysis import PriceAnalysis
from demo.allocation.dcopf import compute_primal_solution


def analyze_prices(algorithm, algorithm_name, alloc, data):
    pricing = algorithm.compute_prices(alloc, data, file_prices=f"../results/{algorithm_name}_prices.txt")

    analysis = PriceAnalysis(pricing, alloc, data)

    analysis.compute_mwps(alloc, df_buyers, df_sellers, periods, blocks_buyers, blocks_sellers,
                          mwps_file='../results/ip_mwps.txt')


# choose dataset
dataset = "IEEE_RTS"

# parse dataset
df_sellers, df_buyers, network, periods, nodes_agents, R_star, blocks_buyers, blocks_sellers = parse_data(dataset)

# compute allocation
obj, status, runtime, u_st_dict, x_bt, x_btl, y_st, y_stl, u_st, f_vwt, alpha_vt, phi_st, shadow_prices = \
    compute_primal_solution(
        df_sellers, df_buyers, network, periods, R_star, nodes_agents, blocks_buyers, blocks_sellers,
        allocation_file="../results/allocation.txt"
    )

allocation = Allocation(obj, x_bt, y_st, x_btl, y_stl, f_vwt, u_st)
market_data = MarketData(df_buyers, df_sellers, network, periods, blocks_buyers, blocks_sellers, R_star, nodes_agents)

# choose pricing rule, compute and analyze prices
ip = IP()
analyze_prices(ip, "ip", allocation, market_data)
