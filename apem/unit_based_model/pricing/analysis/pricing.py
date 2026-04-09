from abc import ABC
from typing import Any, Optional


class Objective(ABC):
    """
    Common container for compensation metrics reported by participant group.

    ``buyers``, ``sellers``, and ``network`` are aggregates over demand, supply,
    and transmission-network participants, respectively. ``total`` is their sum.
    Per-entity dictionaries expose the same values at participant/line level.
    """

    def __init__(
        self,
        total: float,
        buyers: float,
        sellers: float,
        network: float,
        per_buyer: dict[Any, float],
        per_seller: dict[Any, float],
        per_line: dict[Any, float],
    ) -> None:
        self._total = total
        self._buyers = buyers
        self._sellers = sellers
        self._network = network
        self._per_buyer = per_buyer
        self._per_seller = per_seller
        self._per_line = per_line


class GLOCS(Objective):
    """
    Global lost opportunity costs (GLOCs).

    For participant ``l`` with optimal allocation ``z*`` and prices ``p``:

    :math:`\mathrm{GLOC}_l(p \mid z^*) = \hat{u}_l(p) - u_l(z^* \mid p)`.

    Here, :math:`\hat{u}_l(p)` is the maximum profit/utility participant
    ``l`` can obtain over all feasible deviations at prices ``p``. Therefore,
    GLOCs capture incentives to deviate from the welfare-maximizing allocation
    to any feasible alternative.

    Component interpretation:

    - ``glocs_buyers``: aggregate GLOC over buyers
    - ``glocs_sellers``: aggregate GLOC over sellers
    - ``glocs_network``: aggregate GLOC over network/line participants
    - ``total_glocs``: aggregate GLOC over all participants
    """

    def __init__(
        self,
        total_glocs: float,
        glocs_buyers: float,
        glocs_sellers: float,
        glocs_network: float,
        glocs_per_buyer: dict[Any, float],
        glocs_per_seller: dict[Any, float],
        glocs_per_line: dict[Any, float],
    ) -> None:
        super().__init__(total_glocs, glocs_buyers, glocs_sellers, glocs_network, glocs_per_buyer, glocs_per_seller,
                         glocs_per_line)

    @property
    def total_glocs(self) -> float:
        return self._total

    @property
    def glocs_buyers(self) -> float:
        return self._buyers

    @property
    def glocs_sellers(self) -> float:
        return self._sellers

    @property
    def glocs_network(self) -> float:
        return self._network

    @property
    def glocs_per_buyer(self) -> dict[Any, float]:
        return self._per_buyer

    @property
    def glocs_per_seller(self) -> dict[Any, float]:
        return self._per_seller

    @property
    def glocs_per_line(self) -> dict[Any, float]:
        return self._per_line


class LLOCS(Objective):
    """
    Local lost opportunity costs (LLOCs).

    For participant ``l`` with optimal allocation ``z*`` and prices ``p``:

    :math:`\mathrm{LLOC}_l(p \mid z^*) = \hat{u}'_l(p) - u_l(z^* \mid p)`.

    :math:`\hat{u}'_l(p)` maximizes utility only over allocations in the domain
    of the active cost/valuation function at ``z*`` (fixed
    commitment/operating regime). Therefore, LLOCs capture incentives for local
    deviations, such as volume changes, while not allowing commitment
    switching.

    Component interpretation:

    - ``llocs_buyers``: aggregate LLOC over buyers
    - ``llocs_sellers``: aggregate LLOC over sellers
    - ``llocs_network``: aggregate LLOC over network/line participants
    - ``total_llocs``: aggregate LLOC over all participants
    """

    def __init__(
        self,
        total_llocs: float,
        llocs_buyers: float,
        llocs_sellers: float,
        llocs_network: float,
        llocs_per_buyer: dict[Any, float],
        llocs_per_seller: dict[Any, float],
        llocs_per_line: dict[Any, float],
    ) -> None:
        super().__init__(total_llocs, llocs_buyers, llocs_sellers, llocs_network, llocs_per_buyer, llocs_per_seller,
                         llocs_per_line)

    @property
    def total_llocs(self) -> float:
        return self._total

    @property
    def llocs_buyers(self) -> float:
        return self._buyers

    @property
    def llocs_sellers(self) -> float:
        return self._sellers

    @property
    def llocs_network(self) -> float:
        return self._network

    @property
    def llocs_per_buyer(self) -> dict[Any, float]:
        return self._per_buyer

    @property
    def llocs_per_seller(self) -> dict[Any, float]:
        return self._per_seller

    @property
    def llocs_per_line(self) -> dict[Any, float]:
        return self._per_line


class MWPS(Objective):
    """
    Make-whole payments (MWPs).

    For participant ``l`` with optimal allocation ``z*`` and prices ``p``:

    :math:`\mathrm{MWP}_l(p \mid z^*) = \max(-u_l(z^* \mid p), 0)`.

    MWPs are the compensation required to prevent losses under the realized
    dispatch and prices (individual rationality). They are equivalent to LOCs
    that only consider deviation to non-participation (leaving the market),
    and are a subset of GLOCs.

    Component interpretation:

    - ``mwps_buyers``: make-whole payments assigned to buyers
    - ``mwps_sellers``: make-whole payments assigned to sellers
    - ``mwps_network``: network/congestion-related payment component
    - ``total_mwps``: total uplift amount
    """

    def __init__(
        self,
        total_mwps: float,
        mwps_buyers: float,
        mwps_sellers: float,
        mwps_network: float,
        mwps_per_buyer: dict[Any, float],
        mwps_per_seller: dict[Any, float],
        mwps_per_line: dict[Any, float],
    ) -> None:
        super().__init__(total_mwps, mwps_buyers, mwps_sellers, mwps_network, mwps_per_buyer, mwps_per_seller,
                         mwps_per_line)

    @property
    def total_mwps(self) -> float:
        return self._total

    @property
    def mwps_buyers(self) -> float:
        return self._buyers

    @property
    def mwps_sellers(self) -> float:
        return self._sellers

    @property
    def mwps_network(self) -> float:
        return self._network

    @property
    def mwps_per_buyer(self) -> dict[Any, float]:
        return self._per_buyer

    @property
    def mwps_per_seller(self) -> dict[Any, float]:
        return self._per_seller

    @property
    def mwps_per_line(self) -> dict[Any, float]:
        return self._per_line


class Pricing:
    """
    Pricing result.
    """

    def __init__(
        self,
        node_prices: dict[tuple[Any, Any], float],
        line_congestion_prices: Optional[dict[Any, float]] = None,
        used_algorithm: Optional[str] = None,
        runtime: Optional[float] = None,
        num_vars: Optional[int] = None,
        num_constrs: Optional[int] = None,
        glocs: Optional[GLOCS] = None,
        llocs: Optional[LLOCS] = None,
        mwps: Optional[MWPS] = None,
        line_congestion_prices_per_edge: Optional[dict[Any, float]] = None,
    ) -> None:
        self._node_prices = node_prices
        self._line_congestion_prices = line_congestion_prices
        self._line_congestion_prices_per_edge = line_congestion_prices_per_edge
        self.used_algorithm = used_algorithm
        self.runtime = runtime
        self.num_vars = num_vars
        self.num_constrs = num_constrs
        self.glocs = glocs
        self.llocs = llocs
        self.mwps = mwps

    @property
    def node_prices(self) -> dict[tuple[Any, Any], float]:
        return self._node_prices

    @property
    def line_congestion_prices(self) -> Optional[dict[Any, float]]:
        return self._line_congestion_prices

    @property
    def line_congestion_prices_per_edge(self) -> Optional[dict[Any, float]]:
        return self._line_congestion_prices_per_edge

    @property
    def status(self) -> int:
        return 1
