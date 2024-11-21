class Scenario:
    """Buyers, sellers and network data.
    """

    def __init__(self, name, df_buyers, df_sellers, network, nodes_agents, periods, blocks_buyers, blocks_sellers,
                 r_star):
        self.name = name
        self.df_buyers = df_buyers
        self.df_sellers = df_sellers
        self.network = network
        self.nodes_agents = nodes_agents
        self.periods = periods
        self.blocks_buyers = blocks_buyers
        self.blocks_sellers = blocks_sellers
        self.r_star = r_star

    def __str__(self):
        return self.name
