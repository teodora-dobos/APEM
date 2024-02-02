class MarketData:

    def __init__(self, df_buyers, df_sellers, network, periods, blocks_buyers, blocks_sellers, R_star, nodes_agents):
        self.df_buyers = df_buyers
        self.df_sellers = df_sellers
        self.network = network
        self.periods = periods
        self.blocks_buyers = blocks_buyers
        self.blocks_sellers = blocks_sellers
        self.R_star = R_star
        self.nodes_agents = nodes_agents
