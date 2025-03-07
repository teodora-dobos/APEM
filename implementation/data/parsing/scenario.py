import pandas as pd


class Scenario:
    """
    Buyers, sellers and network data.
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


class ZonalScenario:
    """
    Data expected in the Euphemia implementation.
    """

    def __init__(self, name: str, periods: list, step_orders: pd.DataFrame, block_orders: pd.DataFrame,
                 complex_orders: pd.DataFrame, complex_step_orders: pd.DataFrame, scalable_complex_orders: pd.DataFrame,
                 scalable_step_orders: pd.DataFrame):
        self.name = name
        self.periods = periods
        self.step_orders = step_orders
        self.block_orders = block_orders
        self.complex_orders = complex_orders
        self.complex_step_orders = complex_step_orders
        self.scalable_complex_orders = scalable_complex_orders
        self.scalable_step_orders = scalable_step_orders

    def __str__(self):
        return self.name
