class BuyersAllocation:
    """
    The results of an allocation that relate to the buyers.
    """

    def __init__(self, x_bt, x_btl, df_buyers, blocks_buyers):
        self.x_bt = x_bt
        self.x_btl = x_btl
        self.df_buyers = df_buyers
        self.blocks_buyers = blocks_buyers

    def demand_acceptance_ratio(self) -> float:
        """
        Compute demand acceptance ratio for all periods. It does not include the inelastic demand.

        :return: the fraction of elastic demand that is fulfilled in the allocation
        """
        buyers = self.df_buyers['buyer'].unique()
        periods = self.df_buyers['period'].unique()

        total_demand = self.df_buyers['max_dem'].sum()
        accepted_demand = sum(self.x_btl[b, t, l] for b in buyers for t in periods for l in self.blocks_buyers)

        return round(accepted_demand / total_demand, 2)


class SellersAllocation:
    """
    The results of an allocation that relate to the sellers.
    """

    def __init__(self, y_st, y_stl, u_st, phi_st, df_sellers):
        self.y_st = y_st
        self.y_stl = y_stl
        self.u_st = u_st
        self.phi_st = phi_st
        self.df_sellers = df_sellers

    def supply_acceptance_ratio(self) -> float:
        """
        Compute supply acceptance ratio for all periods.

        :return: the fraction of available supply that is accepted in the allocation
        """
        sellers = self.df_sellers['seller'].unique()
        periods = self.df_sellers['period'].unique()

        total_supply = self.df_sellers['max_prod'].sum()
        accepted_supply = sum(self.y_st[s, t] for s in sellers for t in periods)

        return round(accepted_supply / total_supply, 2)


class TransmissionNetworkAllocation:
    """
    The results of an allocation that relate to the transmission network.
    """

    def __init__(self, f_vwt, alpha_vt, slack_vt, network, periods, f_vwkt=None):
        self.f_vwt = f_vwt
        self.f_vwkt = f_vwkt or {}
        self.alpha_vt = alpha_vt
        self.slack_vt = slack_vt
        self.network = network
        self.periods = periods

    def congested_lines(self) -> dict:
        """
        Compute congested lines.

        :return: dictionary with the congested lines for each period
        """
        result = {}
        for t in self.periods:
            result[t] = []
            if self.network.is_multigraph():
                for v, w, k, data in self.network.edges(keys=True, data=True):
                    flow = self.f_vwkt.get((v, w, k, t), self.f_vwt.get((v, w, t), 0))
                    capacity = data['F_max']
                    if abs(flow) >= capacity:
                        result[t].append((v, w, k))
            else:
                for v, w, data in self.network.edges(data=True):
                    flow = self.f_vwt[v, w, t]
                    capacity = data['F_max']
                    if abs(flow) >= capacity:
                        result[t].append((v, w))

        return result


class Allocation:
    """
    Data and information related to an allocation, including the values of the optimization variables and statistics
    from the optimizer.
    """

    def __init__(self, welfare, x_bt, y_st, x_btl, y_stl, f_vwt, alpha_vt, u_st, phi_st, slack_vt, power_flow_model, runtime,
                 num_vars, num_constrs, MIP_gap, num_cont_vars, num_bin_vars, dataset, f_vwkt=None):
        self.welfare = welfare
        self.runtime = runtime
        self.MIP_gap = MIP_gap
        self.num_constrs = num_constrs
        self.num_vars = num_vars
        self.num_cont_vars = num_cont_vars
        self.num_bin_vars = num_bin_vars
        self.power_flow_model = power_flow_model
        self.dataset = dataset
        self.BuyersAllocation = BuyersAllocation(x_bt, x_btl, dataset.df_buyers, dataset.blocks_buyers)
        self.SellersAllocation = SellersAllocation(y_st, y_stl, u_st, phi_st, dataset.df_sellers)
        self.TransmissionNetworkAllocation = TransmissionNetworkAllocation(f_vwt, alpha_vt, slack_vt, dataset.network,
                                                                           dataset.periods, f_vwkt)

    @property
    def status(self):
        return 1

    def consumed_real_power_per_node_period(self, node: int, period: int) -> float:
        """
        Compute total real power consumed in specified node and period.

        :param node: Node for which the consumed real power is computed.
        :param period: Period for which the consumed real power in a node is computed.
        :return: Total consumed real power per specified node and period.
        """
        buyers = self.dataset.nodes_agents[node]['buyers']
        return sum(self.BuyersAllocation.x_bt[b, period] for b in buyers)

    def excess_supply(self) -> float:
        """
        Compute total excess supply.

        :return: The difference between the accepted supply and demand.
        """
        buyers = self.dataset.df_buyers['buyer'].unique()
        sellers = self.dataset.df_sellers['seller'].unique()
        periods = self.dataset.df_sellers['period'].unique()

        accepted_demand = sum(
            self.BuyersAllocation.x_btl[b, t, l] for b in buyers for t in periods for l in self.dataset.blocks_buyers
        )
        accepted_supply = sum(self.SellersAllocation.y_st[s, t] for s in sellers for t in periods)

        return accepted_supply - accepted_demand

    def generated_real_power_per_node_period(self, node: int, period: int) -> float:
        """
        Compute total real power generated in specified node and period.

        :param node: Node for which the generated real power is computed.
        :param period: Period for which the generated real power in a node is computed.
        :return: Total generated real power per specified node and period.
        """
        sellers = self.dataset.nodes_agents[node]['sellers']
        return sum(self.SellersAllocation.y_st[s, period] for s in sellers)