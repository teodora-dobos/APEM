from abc import ABC, abstractmethod


class PricingAlgorithm(ABC):

    @abstractmethod
    def compute_prices(self, allocation, market_data, file_prices="", prices=None):
        pass


class Pricing(ABC):
    pass


class MWPS:
    def __init__(self, total_mwps, mwps_buyers, mwps_sellers, mwps_network, mwps_per_buyer, mwps_per_seller,
                 mwps_per_line):
        self._total_mwps = total_mwps
        self._mwps_buyers = mwps_buyers
        self._mwps_sellers = mwps_sellers
        self._mwps_network = mwps_network
        self._mwps_per_buyer = mwps_per_buyer
        self._mwps_per_seller = mwps_per_seller
        self._mwps_per_line = mwps_per_line

    @property
    def total_mwps(self):
        return self._total_mwps

    @property
    def mwps_buyers(self):
        return self._mwps_buyers

    @property
    def mwps_sellers(self):
        return self._mwps_sellers

    @property
    def mwps_network(self):
        return self._mwps_network

    @property
    def mwps_per_buyer(self):
        return self._mwps_per_buyer

    @property
    def mwps_per_seller(self):
        return self._mwps_per_seller

    @property
    def mwps_per_line(self):
        return self._mwps_per_line


class PricingSuccess(Pricing):

    def __init__(self, node_prices, line_congestion_prices, mwps=None):
        self._node_prices = node_prices
        self._line_congestion_prices = line_congestion_prices
        self.mwps = mwps

    @property
    def node_prices(self):
        return self._node_prices

    @property
    def line_congestion_prices(self):
        return self._line_congestion_prices


class PricingError(Pricing):
    def __init__(self, status):
        self.status = status
