from abc import ABC


class Objective(ABC):
    def __init__(self, total, buyers, sellers, network, per_buyer, per_seller, per_line):
        self._total = total
        self._buyers = buyers
        self._sellers = sellers
        self._network = network
        self._per_buyer = per_buyer
        self._per_seller = per_seller
        self._per_line = per_line


class GLOCS(Objective):
    """
    Global lost opportunity costs.
    """

    def __init__(self, total_glocs, glocs_buyers, glocs_sellers, glocs_network, glocs_per_buyer, glocs_per_seller,
                 glocs_per_line):
        super().__init__(total_glocs, glocs_buyers, glocs_sellers, glocs_network, glocs_per_buyer, glocs_per_seller,
                         glocs_per_line)

    @property
    def total_glocs(self):
        return self._total

    @property
    def glocs_buyers(self):
        return self._buyers

    @property
    def glocs_sellers(self):
        return self._sellers

    @property
    def glocs_network(self):
        return self._network

    @property
    def glocs_per_buyer(self):
        return self._per_buyer

    @property
    def glocs_per_seller(self):
        return self._per_seller

    @property
    def glocs_per_line(self):
        return self._per_line


class LLOCS(Objective):
    """
    Local lost opportunity costs.
    """

    def __init__(self, total_llocs, llocs_buyers, llocs_sellers, llocs_network, llocs_per_buyer, llocs_per_seller,
                 llocs_per_line):
        super().__init__(total_llocs, llocs_buyers, llocs_sellers, llocs_network, llocs_per_buyer, llocs_per_seller,
                         llocs_per_line)

    @property
    def total_llocs(self):
        return self._total

    @property
    def llocs_buyers(self):
        return self._buyers

    @property
    def llocs_sellers(self):
        return self._sellers

    @property
    def llocs_network(self):
        return self._network

    @property
    def llocs_per_buyer(self):
        return self._per_buyer

    @property
    def llocs_per_seller(self):
        return self._per_seller

    @property
    def llocs_per_line(self):
        return self._per_line


class MWPS(Objective):
    """
    Make-whole payments.
    """

    def __init__(self, total_mwps, mwps_buyers, mwps_sellers, mwps_network, mwps_per_buyer, mwps_per_seller,
                 mwps_per_line):
        super().__init__(total_mwps, mwps_buyers, mwps_sellers, mwps_network, mwps_per_buyer, mwps_per_seller,
                         mwps_per_line)

    @property
    def total_mwps(self):
        return self._total

    @property
    def mwps_buyers(self):
        return self._buyers

    @property
    def mwps_sellers(self):
        return self._sellers

    @property
    def mwps_network(self):
        return self._network

    @property
    def mwps_per_buyer(self):
        return self._per_buyer

    @property
    def mwps_per_seller(self):
        return self._per_seller

    @property
    def mwps_per_line(self):
        return self._per_line


class Pricing:
    """
    Pricing result.
    """

    def __init__(self, node_prices, line_congestion_prices, used_algorithm, runtime, num_vars, num_constrs,
                 glocs=None, llocs=None, mwps=None):
        self._node_prices = node_prices
        self._line_congestion_prices = line_congestion_prices
        self.used_algorithm = used_algorithm
        self.runtime = runtime
        self.num_vars = num_vars
        self.num_constrs = num_constrs
        self.glocs = glocs
        self.llocs = llocs
        self.mwps = mwps

    @property
    def node_prices(self):
        return self._node_prices

    @property
    def line_congestion_prices(self):
        return self._line_congestion_prices

    @property
    def status(self):
        return 1
