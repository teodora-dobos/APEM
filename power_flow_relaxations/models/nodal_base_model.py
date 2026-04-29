from typing import Optional
from abc import abstractmethod
import pandas as pd
import numpy as np
import sys

from mosek.fusion import Matrix, Model, Domain, ObjectiveSense, Expr, SolutionError, ProblemStatus, SolutionStatus
import mosek.fusion.pythonic # Don't remove this import, it is needed for the Mosek Fusion API to work properly
from types import SimpleNamespace

from apem.unit_based_model.error import Error
from apem.unit_based_model.allocation.allocation import SellersAllocation, Allocation
from apem.unit_based_model.solver_configuration import SolverConfiguration as Configuration
from apem.unit_based_model.allocation.power_flow_model import PowerFlowModel
from apem.unit_based_model.allocation.analysis.stats import compute_stats
from apem.unit_based_model.data.parsing.scenario import Scenario
from apem.unit_based_model.utils.extraction import preprocess_as_dict


class NodalBaseModel(PowerFlowModel):
    """
    Shared optimization scaffold for nodal power-flow relaxations.

    This base class handles:
    - scenario normalization/parsing into indexed sets and tensors,
    - variable creation and common market/network constraints,
    - objective assembly for welfare or zonal-tracking modes,
    - solving, optional integrality forcing, and allocation extraction.

    Subclasses provide relaxation-specific network equations by implementing
    `power_constraints`, `reference_constraints`, and `get_V_vt_values`.
    """

    def read_scenario(self, scenario):
        """
        Normalize and ingest a scenario into model-ready structures.

        Harmonizes expected buyer/seller columns, creates index mappings for
        entities and periods, builds node-neighbor and node-agent mappings, and
        precomputes dictionary lookups for bids, capacities, and costs.
        """
        # Normalize required columns for this model
        if "max_real_dem" not in scenario.df_buyers.columns and "max_dem" in scenario.df_buyers.columns:
            scenario.df_buyers = scenario.df_buyers.copy()
            scenario.df_buyers["max_real_dem"] = scenario.df_buyers["max_dem"]
        for col in ["min_real_dem", "min_reactive_dem", "max_reactive_dem"]:
            if col not in scenario.df_buyers.columns:
                scenario.df_buyers[col] = 0

        if "max_real_prod" not in scenario.df_sellers.columns and "max_prod" in scenario.df_sellers.columns:
            scenario.df_sellers = scenario.df_sellers.copy()
            scenario.df_sellers["max_real_prod"] = scenario.df_sellers["max_prod"]
        if "min_real_prod" not in scenario.df_sellers.columns and "min_prod" in scenario.df_sellers.columns:
            scenario.df_sellers["min_real_prod"] = scenario.df_sellers["min_prod"]
        for col in ["min_reactive_prod", "max_reactive_prod"]:
            if col not in scenario.df_sellers.columns:
                scenario.df_sellers[col] = 0

        buyers_list = scenario.df_buyers["buyer"].unique().tolist()
        sellers_list = scenario.df_sellers["seller"].unique().tolist()
        periods_list = scenario.periods if hasattr(scenario, "periods") else scenario.df_buyers["period"].unique().tolist()

        self.buyers = list(enumerate(buyers_list))
        self.buyer_indices = {buyer: i for i, buyer in self.buyers}
        self.sellers = list(enumerate(sellers_list))
        self.seller_indices = {seller: i for i, seller in self.sellers}
        self.periods = list(enumerate(periods_list))
        self.blocks_buyers = list(enumerate(scenario.blocks_buyers))
        self.blocks_sellers = list(enumerate(scenario.blocks_sellers))
        self.network = scenario.network
        self.nodes = list(enumerate(self.network))
        self.node_indices = {node: i for i, node in self.nodes}
        self.reference_bus = self.node_indices[scenario.r_star], scenario.r_star
        self.neighbours = {
            node: [(self.node_indices[w], w) for w in self.network[node]] for node in self.network
        }

        self.nodes_agents = scenario.nodes_agents
        self.node_buyers = {
            node: [
                self.buyer_indices[buyer]
                for buyer in self.nodes_agents[node]["buyers"]
            ]
            for node in self.network
        }
        self.node_sellers = {
            node: [
                self.seller_indices[seller]
                for seller in self.nodes_agents[node]["sellers"]
            ]
            for node in self.network
        }

        self.buyer_val_dict, self.buyer_size_dict = {}, {}
        self.seller_cost_dict, self.seller_size_dict = {}, {}

        self.min_real_dem = preprocess_as_dict(
            scenario.df_buyers, ["buyer", "period"], "min_real_dem"
        )
        self.max_real_dem = preprocess_as_dict(
            scenario.df_buyers, ["buyer", "period"], "max_real_dem"
        )
        self.min_reactive_dem = preprocess_as_dict(
            scenario.df_buyers, ["buyer", "period"], "min_reactive_dem"
        )
        self.max_reactive_dem = preprocess_as_dict(
            scenario.df_buyers, ["buyer", "period"], "max_reactive_dem"
        )

        self.min_real_prod = preprocess_as_dict(
            scenario.df_sellers, ["seller", "period"], "min_real_prod"
        )
        self.max_real_prod = preprocess_as_dict(
            scenario.df_sellers, ["seller", "period"], "max_real_prod"
        )
        self.min_reactive_prod = preprocess_as_dict(
            scenario.df_sellers, ["seller", "period"], "min_reactive_prod"
        )
        self.max_reactive_prod = preprocess_as_dict(
            scenario.df_sellers, ["seller", "period"], "max_reactive_prod"
        )

        self.no_load_cost = preprocess_as_dict(
            scenario.df_sellers, ["seller", "period"], "no_load_cost"
        )
        self.min_uptime = preprocess_as_dict(
            scenario.df_sellers, ["seller", "period"], "min_uptime"
        )

        for block in scenario.blocks_buyers:
            self.buyer_val_dict[block] = preprocess_as_dict(
                scenario.df_buyers, ["buyer", "period"], "val", block
            )
            self.buyer_size_dict[block] = preprocess_as_dict(
                scenario.df_buyers, ["buyer", "period"], "size", block
            )

        for block in scenario.blocks_sellers:
            self.seller_cost_dict[block] = preprocess_as_dict(
                scenario.df_sellers, ["seller", "period"], "cost", block
            )
            self.seller_size_dict[block] = preprocess_as_dict(
                scenario.df_sellers, ["seller", "period"], "size", block
            )

    def initialize_parameters(self):
        """
        Convert dictionary-based inputs into dense NumPy tensors.

        Produces tensor/matrix representations for buyer values/sizes, seller
        costs/sizes, no-load costs, and real/reactive demand/supply bounds, all
        aligned with internal `(entity, period, block)` indexing.
        """
        self.buyer_val_tensor = np.zeros((len(self.buyers), len(self.periods), len(self.blocks_buyers)))
        for lb, block in self.blocks_buyers:
            for b, buyer in self.buyers:
                for t, period in self.periods:
                    self.buyer_val_tensor[b, t, lb] = self.buyer_val_dict[block][
                        buyer, period
                    ]
        
        self.buyer_size_tensor = np.zeros((len(self.buyers), len(self.periods), len(self.blocks_buyers)))
        for lb, block in self.blocks_buyers:
            for b, buyer in self.buyers:
                for t, period in self.periods:
                    self.buyer_size_tensor[b, t, lb] = self.buyer_size_dict[block][
                        buyer, period
                    ]

        self.seller_cost_tensor = np.zeros((len(self.sellers), len(self.periods), len(self.blocks_sellers)))
        for ls, block in self.blocks_sellers:
            for s, seller in self.sellers:
                for t, period in self.periods:
                    self.seller_cost_tensor[s, t, ls] = self.seller_cost_dict[block][
                        seller, period
                    ]

        self.seller_size_tensor = np.zeros((len(self.sellers), len(self.periods), len(self.blocks_sellers)))
        for ls, block in self.blocks_sellers:
            for s, seller in self.sellers:
                for t, period in self.periods:
                    self.seller_size_tensor[s, t, ls] = self.seller_size_dict[block][
                        seller, period
                    ]

        self.no_load_cost_matrix = np.zeros((len(self.sellers), len(self.periods)))
        for s, seller in self.sellers:
            for t, period in self.periods:
                self.no_load_cost_matrix[s, t] = self.no_load_cost[seller, period]

        # Buyer Parameters
        self.min_real_dem_tensor = np.zeros((len(self.buyers), len(self.periods)))
        for b, buyer in self.buyers:
            for t, period in self.periods:
                self.min_real_dem_tensor[b, t] = self.min_real_dem[buyer, period]

        self.max_real_dem_tensor = np.zeros((len(self.buyers), len(self.periods)))
        for b, buyer in self.buyers:
            for t, period in self.periods:
                self.max_real_dem_tensor[b, t] = self.max_real_dem[buyer, period]

        self.min_reactive_dem_tensor = np.zeros((len(self.buyers), len(self.periods)))
        for b, buyer in self.buyers:
            for t, period in self.periods:
                self.min_reactive_dem_tensor[b, t] = self.min_reactive_dem[buyer, period]

        self.max_reactive_dem_tensor = np.zeros((len(self.buyers), len(self.periods)))
        for b, buyer in self.buyers:
            for t, period in self.periods:
                self.max_reactive_dem_tensor[b, t] = self.max_reactive_dem[
                    buyer, period
                ]

        # Seller Parameters
        self.min_real_prod_tensor = np.zeros((len(self.sellers), len(self.periods)))
        for s, seller in self.sellers:
            for t, period in self.periods:
                self.min_real_prod_tensor[s, t] = self.min_real_prod[seller, period]

        self.max_real_prod_tensor = np.zeros((len(self.sellers), len(self.periods)))
        for s, seller in self.sellers:
            for t, period in self.periods:
                self.max_real_prod_tensor[s, t] = self.max_real_prod[seller, period]

        self.min_reactive_prod_tensor = np.zeros((len(self.sellers), len(self.periods)))
        for s, seller in self.sellers:
            for t, period in self.periods:
                self.min_reactive_prod_tensor[s, t] = self.min_reactive_prod[
                    seller, period
                ]

        self.max_reactive_prod_tensor = np.zeros((len(self.sellers), len(self.periods)))
        for s, seller in self.sellers:
            for t, period in self.periods:
                self.max_reactive_prod_tensor[s, t] = self.max_reactive_prod[
                    seller, period
                ]

    def initialize_model(self, configuration):
        """
        Create the MOSEK model and declare common decision variables.

        Includes buyer and seller block-dispatch variables, commitment/start-up
        variables, branch active/reactive flows, nodal imbalance slacks, and
        current-limit violation variables. Commitment is relaxed or binary based
        on `configuration.relaxation`.
        """
        self.model = Model()

        self.problem_status = None
        self.solution_status = None

        self.p_bt = self.model.variable("p_bt", [len(self.buyers), len(self.periods)], Domain.greaterThan(0.0))
        self.p_btl = self.model.variable("p_btl", [len(self.buyers), len(self.periods), len(self.blocks_buyers)], Domain.greaterThan(0.0))
        self.q_bt = self.model.variable("q_bt", [len(self.buyers), len(self.periods)])

        self.p_st = self.model.variable("p_st", [len(self.sellers), len(self.periods)], Domain.greaterThan(0.0))
        self.p_stl = self.model.variable("p_stl", [len(self.sellers), len(self.periods), len(self.blocks_sellers)], Domain.greaterThan(0.0))
        self.q_st = self.model.variable("q_st", [len(self.sellers), len(self.periods)])

        if configuration is not None and configuration.relaxation:
            self.u_st = self.model.variable("u_st", [len(self.sellers), len(self.periods)], Domain.greaterThan(0.0))
        else:
            self.u_st = self.model.variable("u_st", [len(self.sellers), len(self.periods)], Domain.binary())
            
        self.phi_st = self.model.variable("phi_st", [len(self.sellers), len(self.periods)], Domain.greaterThan(0.0))

        self.p_vwt = self.model.variable("p_vwt", [len(self.nodes), len(self.nodes), len(self.periods)])
        self.q_vwt = self.model.variable("q_vwt", [len(self.nodes), len(self.nodes), len(self.periods)])

        self.p_imb = self.model.variable("p_imb", [len(self.nodes), len(self.periods)], Domain.greaterThan(0.0))
        self.q_imb = self.model.variable("q_imb", [len(self.nodes), len(self.periods)], Domain.greaterThan(0.0))

        self.I_viol = self.model.variable("I_viol", [len(self.nodes), len(self.nodes), len(self.periods)], Domain.greaterThan(0.0))

    def initialize_network_arrays(self, enforce_sparse=False):
        """
        Build electrical parameter arrays from the scenario network.

        Parameters
        ----------
        enforce_sparse:
            If `True`, store matrices as MOSEK sparse `Matrix`; otherwise NumPy
            arrays are used.

        Generates `V_min`, `V_max`, conductance `G`, susceptance `B`, branch
        ratings `F_max`, and derived apparent limits `S_max`.
        """
        self.V_min = np.array([self.network.nodes[v].get("V_min", 1.) for _, v in self.nodes])
        self.V_max = np.array([self.network.nodes[v].get("V_max", 1.) for _, v in self.nodes])

        G = np.zeros((len(self.nodes), len(self.nodes)))
        B = np.zeros((len(self.nodes), len(self.nodes)))
        F_max = np.zeros((len(self.nodes), len(self.nodes)))
        for i_v, v in self.nodes:
            for i_w, w in self.neighbours[v]:
                G[i_v, i_w] = self.network[v][w].get("G", 0.)
                B[i_v, i_w] = self.network[v][w].get("B", 0.)
                F_max[i_v, i_w] = self.network[v][w].get("F_max", 0.)
        S_max = abs(F_max * self.V_max[:, None])

        if enforce_sparse:
            self.G = Matrix.sparse(G)
            self.B = Matrix.sparse(B)
            self.F_max = Matrix.sparse(F_max)
            self.S_max = Matrix.sparse(S_max)
        else:
            self.G = G
            self.B = B
            self.F_max = F_max
            self.S_max = S_max

    def set_tolerances(self, p_vwt_line_tol=5e-4, q_vwt_line_tol=5e-4, I_viol_weight=3e-1, p_imb_weight=3e-1, q_imb_weight=3e-1):
        """
        Configure tolerance and penalty coefficients used across constraints.

        Parameters control line-equation residual bands and scaling of slack
        variables for current-limit and nodal-balance violations.
        """
        self.p_vwt_line_tol = p_vwt_line_tol
        self.q_vwt_line_tol = q_vwt_line_tol
        self.I_viol_weight = I_viol_weight
        self.p_imb_weight = p_imb_weight
        self.q_imb_weight = q_imb_weight

    def __init__(
        self,
        scenario: Scenario,
        configuration: Configuration,
        tolerances: Optional[dict[str, float]] = None,
    ):
        """
        Construct a nodal relaxation model from a scenario.

        Parameters
        ----------
        scenario:
            Input market/network scenario.
        configuration:
            Solver configuration used for variable domains and runtime settings.
        tolerances:
            Optional overrides for line/balance tolerance and penalty weights.

        Initialization order is: scenario parsing -> parameter tensors -> 
        variable creation -> network arrays -> tolerance setup.
        """
        # PowerFlowModel has no __init__; avoid passing args to object.__init__
        super().__init__()
        # Keep references for downstream use
        self.scenario = scenario
        self.configuration = configuration
        self.read_scenario(scenario)
        self.initialize_parameters()
        self.initialize_model(configuration)
        self.initialize_network_arrays()
        self.tolerances = tolerances
        self.set_tolerances(**(tolerances or {}))

    def get_thermal_limit_objective(self, welfare_scale = 1):
        """
        Return normalized penalty term for current-limit violations.

        The term is scaled by `welfare_scale` and averaged over the size of
        `I_viol` to keep magnitudes comparable across instances.
        """
        violation = welfare_scale / (np.prod(self.I_viol.shape)) * Expr.sum(self.I_viol)
        return violation

    def get_imbalance_objective(self, welfare_scale = 1):
        """
        Return normalized penalty term for nodal real/reactive imbalance slack.

        Uses aggregated `p_imb` and `q_imb` variables with scaling by
        `welfare_scale` and tensor sizes.
        """
        imbalance = welfare_scale / (np.prod(self.p_imb.shape)) * Expr.sum(self.p_imb) + welfare_scale / (np.prod(self.q_imb.shape)) * Expr.sum(self.q_imb)
        return imbalance

    def get_objective(
        self,
        zonal_allocation: Optional[SellersAllocation] = None,
        min_vol: Optional[bool] = False,
    ) -> tuple:
        """
        Build the objective expression and objective sense.

        If `zonal_allocation` is not provided, returns a welfare-maximization
        objective with imbalance and thermal-violation penalties. If
        `zonal_allocation` is provided, returns a deviation-minimization objective:
        either minimum-volume deviation (`min_vol=True`) or cost-weighted deviation
        plus commitment mismatch (`min_vol=False`).
        """

        if isinstance(zonal_allocation, SellersAllocation):
            if len(self.blocks_sellers) > 0:
                diff_stl = self.model.variable("diff_y_stl",
                        [
                            len(self.sellers),
                            len(self.periods),
                            len(self.blocks_sellers)
                        ],
                        Domain.greater_than(0.0),
                    )
                
                u_diff_st = self.model.variable("diff_u_st", 
                    [
                        len(self.sellers),
                        len(self.periods)
                    ],
                    Domain.greater_than(0.0),
                )

                for s, seller in self.sellers:
                    for t, period in self.periods:
                        for ls, block in self.blocks_sellers:
                            self.model.constraint(
                                zonal_allocation.p_stl[seller, period, block] - self.p_stl[s, t, ls]
                                <= diff_stl[s, t, ls]
                            )

                            self.model.constraint(
                                self.p_stl[s, t, ls] - zonal_allocation.p_stl[seller, period, block]
                                <= diff_stl[s, t, ls]
                            )

                if min_vol:
                    welfare_scale = np.sum(np.abs(self.seller_size_tensor)) # type: ignore
                    return (ObjectiveSense.Minimize, Expr.sum(diff_stl) 
                            + self.get_imbalance_objective(welfare_scale)
                            + self.get_thermal_limit_objective(welfare_scale)
                    )
                else:
                    for s, seller in self.sellers:
                        for t, period in self.periods:
                            self.model.constraint(
                                zonal_allocation.u_st[seller, period] - self.u_st[s, t]
                                <= u_diff_st[s, t]
                            )

                            self.model.constraint(
                                self.u_st[s, t] - zonal_allocation.u_st[seller, period]
                                <= u_diff_st[s, t]
                            )

                    welfare_scale = (
                        np.sum(np.abs(self.seller_cost_tensor)) # type: ignore
                        + np.sum(np.abs(self.no_load_cost_matrix)) # type: ignore
                    )

                    return (ObjectiveSense.Minimize,
                        Expr.sum(Expr.vstack([
                                    Expr.mulElm(self.seller_cost_tensor[:, t, :], 
                                                Expr.reshape(diff_stl[:, t, :], [len(self.sellers), len(self.blocks_sellers)]))
                                for t, _ in self.periods]))
                        + Expr.sum(Expr.mulElm(self.no_load_cost_matrix, u_diff_st))
                        + self.get_imbalance_objective(welfare_scale)
                        + self.get_thermal_limit_objective(welfare_scale)
                    )
            else:
                raise ValueError(
                    "Zonal allocation is not compatible with the current scenario. blocks_sellers can't be empty!"
                )
        else:
            welfare_scale = (
                np.sum(np.abs(self.buyer_val_tensor)) # type: ignore
                + np.sum(np.abs(self.seller_cost_tensor)) # type: ignore
                + np.sum(np.abs(self.no_load_cost_matrix)) # type: ignore
            )

            return (ObjectiveSense.Maximize, 
                    Expr.sum(Expr.vstack([
                                Expr.mulElm(self.buyer_val_tensor[:, t, :], 
                                            Expr.reshape(self.p_btl[:, t, :], [len(self.buyers), len(self.blocks_buyers)]))
                            for t, _ in self.periods]))
                    - Expr.sum(Expr.vstack([
                                Expr.mulElm(self.seller_cost_tensor[:, t, :], 
                                            Expr.reshape(self.p_stl[:, t, :], [len(self.sellers), len(self.blocks_sellers)]))
                        for t, _ in self.periods]))
                    - Expr.sum(Expr.mulElm(self.no_load_cost_matrix, self.u_st))
                    - self.get_imbalance_objective(welfare_scale)
                    - self.get_thermal_limit_objective(welfare_scale)
            )

    def bid_constraints(self, u_fixed: Optional[dict] = None):
        """
        Add buyer/seller bid, capacity, and unit-commitment constraints.

        Enforces block limits, aggregate dispatch identities, real/reactive bounds,
        and minimum-uptime relations. If `u_fixed` is provided, commitment values
        are fixed per seller and period before constraint assembly.
        """

        if isinstance(u_fixed, dict):
            for t, period in self.periods:
                for s, seller in self.sellers:
                    if (seller, period) in u_fixed:
                        self.model.constraint(self.u_st[s, t] == u_fixed[seller, period])

        for t, _ in self.periods:
            for b, _ in self.buyers:
                for lb, _ in self.blocks_buyers:
                    self.model.constraint(self.p_btl[b, t, lb] <= self.buyer_size_tensor[b, t, lb])

                self.model.constraint(self.p_bt[b, t] == Expr.sum(self.p_btl[b, t, :]))
                self.model.constraint(self.p_bt[b, t] >= self.min_real_dem_tensor[b, t])
                self.model.constraint(self.p_bt[b, t] <= self.max_real_dem_tensor[b, t])
                self.model.constraint(self.q_bt[b, t] >= self.min_reactive_dem_tensor[b, t])
                self.model.constraint(self.q_bt[b, t] <= self.max_reactive_dem_tensor[b, t])

            for s, _ in self.sellers:
                for ls, _ in self.blocks_sellers:
                    self.model.constraint(self.p_stl[s, t, ls] <= self.seller_size_tensor[s, t, ls] * self.u_st[s, t])
                self.model.constraint(self.p_st[s, t] == Expr.sum(self.p_stl[s, t, :]))
                self.model.constraint(self.p_st[s, t] >= (self.min_real_prod_tensor[s, t] * self.u_st[s, t]))
                self.model.constraint(self.p_st[s, t] <= (self.max_real_prod_tensor[s, t] * self.u_st[s, t]))
                self.model.constraint(self.q_st[s, t] >= (self.min_reactive_prod_tensor[s, t] * self.u_st[s, t]))
                self.model.constraint(self.q_st[s, t] <= (self.max_reactive_prod_tensor[s, t] * self.u_st[s, t]))

        if len(self.periods) > 1:
            # Uptime constraints (hard to vectorize)
            for s, seller in self.sellers:
                for t, period in self.periods:
                    if t > 0:
                        self.model.constraint(self.phi_st[s, t] - self.u_st[s, t] + self.u_st[s, t - 1] >= 0)

                    if t >= self.min_uptime[seller, period]:
                        phi_sum = 0
                        for i in range(t - self.min_uptime[seller, period], t):
                            phi_sum += self.phi_st[s, i]
                        self.model.constraint(
                            phi_sum - self.u_st[s, t] <= 0
                        )

        self.model.constraint(self.u_st == Domain.inRange(0, 1))

    def current_rating_constraints(self):
        """
        Impose conic apparent-power/current rating limits on each branch.

        For each directed edge and period, constrains `(p, q)` flow magnitudes via
        a quadratic cone, with multiplicative slack through `I_viol`.
        """
        for t, _ in self.periods:
            for i_v, v in self.nodes:
                for i_w, w in self.neighbours[v]:
                    self.model.constraint(
                        Expr.vstack(self.V_min[i_v] * self.F_max[i_v, i_w] * (1 + self.I_viol[i_v, i_w, t] * self.I_viol_weight), self.p_vwt[i_v, i_w, t], self.q_vwt[i_v, i_w, t]) == Domain.inQCone()
                    )
    
    @abstractmethod
    def power_constraints(self):
        """
        Add power flow constraints to the model. These constraints typically represent the power flow equations in the network.
        :return: set of power flow constraints
        """
        raise NotImplementedError("This method should be implemented in subclasses.")

    @abstractmethod
    def reference_constraints(self):
        """
        Add reference constraints to the model. These constraints typically set the voltage or power flow at a reference node to a specific value.
        To access the reference node use self.scenario.r_star
        :return: set of reference constraints
        """
        raise NotImplementedError("This method should be implemented in subclasses.")

    def bus_constraints(self):
        """
        Add nodal real/reactive balance constraints with imbalance slack.

        For each node and period, enforces supply - demand - outgoing flow = 0
        within weighted slack variables `p_imb` and `q_imb`.
        """
        for t, _ in self.periods:
            for i_v, v in self.nodes:
                neighbours = [(i_v, i_w, t) for i_w, _ in self.neighbours[v]]
                sellers = [(s, t) for s in self.node_sellers[v]]
                buyers = [(b, t) for b in self.node_buyers[v]]

                # === Real Power Balance ===
                seller_real = Expr.sum(self.p_st[sellers]) if sellers else 0
                buyer_real = Expr.sum(self.p_bt[buyers]) if buyers else 0
                flow_out_real = Expr.sum(self.p_vwt[neighbours]) if neighbours else 0

                self.model.constraint((seller_real - buyer_real - flow_out_real) <= self.p_imb[i_v, t] * self.p_imb_weight)
                self.model.constraint((seller_real - buyer_real - flow_out_real) >= - self.p_imb[i_v, t] * self.p_imb_weight)

                # === Reactive Power Balance ===
                seller_reactive = Expr.sum(self.q_st[sellers]) if sellers else 0
                buyer_reactive = Expr.sum(self.q_bt[buyers]) if buyers else 0
                flow_out_reactive = Expr.sum(self.q_vwt[neighbours]) if neighbours else 0

                self.model.constraint((seller_reactive - buyer_reactive - flow_out_reactive) <= self.q_imb[i_v, t] * self.q_imb_weight)
                self.model.constraint((seller_reactive - buyer_reactive - flow_out_reactive) >= - self.q_imb[i_v, t] * self.q_imb_weight)

    def get_p_bt_values(self) -> dict:
        """
        Get the values of the p_bt variable.

        :return: Dictionary with (buyer, period) as keys and p_bt values as values.
        """
        value = self.p_bt.level().reshape((len(self.buyers), len(self.periods)))
        return {
            (buyer, period): value[b, t]
            for b, buyer in self.buyers
            for t, period in self.periods
            if value is not None
        }

    def get_p_btl_values(self) -> dict:
        """
        Get the values of the p_btl variable.

        :return: Dictionary with (buyer, period, block) as keys and p_btl values as values.
        """
        value = self.p_btl.level().reshape((len(self.buyers), len(self.periods), len(self.blocks_buyers)))
        return {
            (buyer, period, block): value[b, t, lb]
            for b, buyer in self.buyers
            for t, period in self.periods
            for lb, block in self.blocks_buyers
            if value is not None
        }

    def get_q_bt_values(self) -> dict:
        """
        Get the values of the q_bt variable.

        :return: Dictionary with (buyer, period) as keys and q_bt values as values.
        """
        value = self.q_bt.level().reshape((len(self.buyers), len(self.periods)))
        return {
            (buyer, period): value[b, t]
            for b, buyer in self.buyers
            for t, period in self.periods
            if value is not None
        }

    def get_p_st_values(self) -> dict:
        """
        Get the values of the p_st variable.

        :return: Dictionary with (seller, period) as keys and p_st values as values.
        """
        value = self.p_st.level().reshape((len(self.sellers), len(self.periods)))
        return {
            (seller, period): value[s, t]
            for s, seller in self.sellers
            for t, period in self.periods
            if value is not None
        }

    def get_p_stl_values(self) -> dict:
        """
        Get the values of the p_stl variable.

        :return: Dictionary with (seller, period, block) as keys and p_stl values as values.
        """
        value = self.p_stl.level().reshape((len(self.sellers), len(self.periods), len(self.blocks_sellers)))
        return {
            (seller, period, block): value[s, t, ls]
            for s, seller in self.sellers
            for t, period in self.periods
            for ls, block in self.blocks_sellers
            if value is not None
        }

    def get_q_st_values(self) -> dict:
        """
        Get the values of the q_st variable.

        :return: Dictionary with (seller, period) as keys and q_st values as values.
        """
        value = self.q_st.level().reshape((len(self.sellers), len(self.periods)))
        return {
            (seller, period): value[s, t]
            for s, seller in self.sellers
            for t, period in self.periods
            if value is not None
        }

    def get_u_st_values(self, binary=True) -> dict:
        """
        Get the values of the u_st variable.

        :return: Dictionary with (seller, period) as keys and u_st values as values.
        """
        value = self.u_st.level().reshape((len(self.sellers), len(self.periods)))
        if binary:
            return {
                (seller, period): np.round(value[s, t])  # type: ignore
                for s, seller in self.sellers
                for t, period in self.periods
                if value is not None
            }
        else:
            return {
                (seller, period): value[s, t]
                for s, seller in self.sellers
                for t, period in self.periods
                if value is not None
            }

    def get_phi_st_values(self) -> dict:
        """
        Get the values of the phi_st variable.

        :return: Dictionary with (seller, period) as keys and phi_st values as values.
        """
        value = self.phi_st.level().reshape((len(self.sellers), len(self.periods)))
        return {
            (seller, period): value[s, t]
            for s, seller in self.sellers
            for t, period in self.periods
            if value is not None
        }

    def get_p_vwt_values(self) -> dict:
        """
        Get the values of the p_vwt variable.

        :return: Dictionary with (node, neighbor, period) as keys and f_vwt values as values.
        """
        value = self.p_vwt.level().reshape((len(self.nodes), len(self.nodes), len(self.periods)))
        return {
            (v, w, period): value[i_v, i_w, t]
            for i_v, v in self.nodes
            for i_w, w in self.neighbours[v]
            for t, period in self.periods
            if value is not None
        }

    def get_q_vwt_values(self) -> dict:
        """
        Get the values of the q_vwt variable.

        :return: Dictionary with (node, neighbor, period) as keys and q_vwt values as values.

        """
        value = self.q_vwt.level().reshape((len(self.nodes), len(self.nodes), len(self.periods)))
        return {
            (v, w, period): value[i_v, i_w, t]
            for i_v, v in self.nodes
            for i_w, w in self.neighbours[v]
            for t, period in self.periods
            if value is not None
        }

    @abstractmethod
    def get_V_vt_values(self) -> dict[tuple[int, int], tuple[float, float]]:
        """
        Get the values of the V_vt variable.

        :return: Dictionary with (node, period) as keys and V_vt values as values.
        """
        raise NotImplementedError(
            "The get_V_vt_values method should be implemented in subclasses to return the voltage values."
        )

    def collect_constraints(self, u_fixed: Optional[dict] = None, verbose=False):
        """
        Assemble the full model constraint set in canonical order.

        Parameters
        ----------
        u_fixed:
            Optional commitment fixes passed to :meth:`bid_constraints`.
        verbose:
            If `True`, prints progress while adding constraint groups.
        """
        if verbose:
            print("Collecting power constraints...")
        self.power_constraints()
        if verbose:
            print("Collecting reference constraints...")
        self.reference_constraints()
        if verbose:
            print("Collecting bus constraints...")
        self.bus_constraints()
        if verbose:
            print("Collecting bid constraints...")
        self.bid_constraints(u_fixed)

    def solve(
        self,
        results_file: Optional[str] = None,
        stats_file: Optional[str] = None,
        u_fixed: Optional[dict] = None,
        min_vol: Optional[bool] = False,
        zonal_allocation: Optional[SellersAllocation] = None,
        verbose: bool = False,
        force_integrality: bool = True,
        **kwargs
    ) -> Allocation | Error:
        """
        Solve the relaxation and return an allocation-like result object.

        Parameters
        ----------
        results_file:
            Optional CSV path for raw variable dumps (or failure status).
        stats_file:
            Optional path for computed run statistics.
        u_fixed:
            Optional fixed commitments to enforce during solve.
        min_vol:
            Objective mode flag for zonal-tracking formulations.
        zonal_allocation:
            Optional target allocation for redispatch-style tracking objective.
        verbose:
            Enable MOSEK solver logs and build-step prints.
        force_integrality:
            If relaxed commitments produce fractional values, rerun once with
            rounded binary commitments fixed.
        **kwargs:
            Reserved for compatibility.

        Returns
        -------
        Allocation | Error
            Allocation-like object on success; lightweight error object otherwise.
        """

        self.collect_constraints(u_fixed, verbose)

        # Solve the optimization problem
        self.model.objective(*self.get_objective(zonal_allocation, min_vol))

        if verbose:
            self.model.setLogHandler(sys.stdout)

        try:
            self.model.solve()
        except SolutionError as e:
            return Error(str(e))

        self.problem_status = self.model.getProblemStatus()
        self.solution_status = self.model.getPrimalSolutionStatus()
        self.solve_time = self.model.getSolverDoubleInfo("optimizerTime")

        # Check if the optimization was successful
        if self.solution_status in [SolutionStatus.Optimal, SolutionStatus.Feasible]:
            if self.solution_status == SolutionStatus.Feasible:
                print("The solution is feasible but not optimal.")

            u_st_values = self.get_u_st_values(binary=False)
            if force_integrality and any(not (np.isclose(val, 0, atol=1e-5) or np.isclose(val, 1, atol=1e-5)) for val in u_st_values.values()):
                print("Solving again with fixed u_st values to ensure integrality.")
                u_binary = self.get_u_st_values(binary=True)
                # Reinitialize the model to reset all constraints
                self.__init__(self.scenario, self.configuration, tolerances=self.tolerances)

                self.collect_constraints(u_fixed=u_binary, verbose=verbose)
                self.model.objective(*self.get_objective(zonal_allocation, min_vol))

                try:
                    self.model.solve()
                except SolutionError as e:
                    return Error(str(e))

                self.problem_status = self.model.getProblemStatus()
                self.solution_status = self.model.getPrimalSolutionStatus()

                if self.solution_status not in [SolutionStatus.Optimal, SolutionStatus.Feasible]:
                    return Error("The solution is not optimal or feasible after forcing integrality: " + str(self.problem_status))

            allocation = self.get_allocation()

            if stats_file:
                compute_stats(
                    stats_file,
                    self.scenario,
                    self.configuration,
                    allocation,
                    SimpleNamespace(**allocation.stats)
                )

            if results_file:
                results = [
                    {"variable": var._ModelVariable__name, "value": var.level(), "size": var.getSize()}
                    for var in [self.p_bt, self.p_btl, self.q_bt,
                                self.p_st, self.p_stl, self.q_st,
                                self.p_vwt, self.q_vwt, self.u_st,
                                self.phi_st]
                ]
                df = pd.DataFrame(results, columns=["variable", "value", "size"])
                df.to_csv(results_file, index=False)

            return allocation
        else:
            if results_file:
                status_message = {
                    ProblemStatus.PrimalInfeasible: "Model is primal infeasible",
                    ProblemStatus.DualInfeasible: "Model is dual infeasible",
                    ProblemStatus.PrimalAndDualInfeasible: "Model is primal and dual infeasible",
                    ProblemStatus.IllPosed: "Model is ill-posed",
                    ProblemStatus.PrimalInfeasibleOrUnbounded: "Model is primal infeasible or unbounded",
                    ProblemStatus.Unknown: "Solver encountered an error",
                }.get(self.problem_status, "Optimization failed with unknown status")

                error_data = [
                    {"status": self.problem_status, "message": status_message}
                ]

                df = pd.DataFrame(error_data, columns=["status", "message"])
                df.to_csv(results_file, index=False)

            print(f"{self} allocation error with code {self.problem_status}. {self.solution_status}")
            return Error(str(self.problem_status))

    def get_allocation(self):
        """
        Build a lightweight allocation object from the solved model values.

        Returns a `RelaxAllocation` object with buyer, seller, and network
        allocations, summary stats, helper methods for welfare and feasibility
        checks, and reconstructed voltage components `V_vt`.

        Raises `ValueError` if solve status is missing or the solution is not
        feasible/optimal.
        """
        if self.model is not None and self.problem_status is not None and self.solution_status is not None:
            if self.solution_status not in [SolutionStatus.Feasible, SolutionStatus.Optimal]:
                raise ValueError(
                    f"The solution is not optimal or feasible: {self.solution_status}"
                )
            
            self.model.dataReport()
            stats = {
                "welfare": self.model.primalObjValue(),
                "runtime": self.solve_time if self.solve_time is not None else self.model.getSolverDoubleInfo("optimizerTime"),
                "MIP_gap": self.model.getSolverDoubleInfo("mioObjRelGap"),
            }

            # Lightweight allocation object compatible with run_relaxations expectations
            class SimpleBuyersAllocation:
                def __init__(self, p_bt, p_btl, df_buyers, blocks_buyers):
                    self.x_bt = p_bt
                    self.x_btl = p_btl
                    self.df_buyers = df_buyers
                    self.blocks_buyers = blocks_buyers

            class SimpleSellersAllocation:
                def __init__(self, p_st, p_stl, u_st, phi_st, df_sellers):
                    self.y_st = p_st
                    self.y_stl = p_stl
                    self.u_st = u_st
                    self.phi_st = phi_st
                    self.df_sellers = df_sellers

            class SimpleTransmissionNetworkAllocation:
                def __init__(self, f_vwt, q_vwt, network, periods):
                    self.f_vwt = f_vwt
                    self.q_vwt = q_vwt
                    self.network = network
                    # periods may be a list of ints or list of (idx, value)
                    self.periods = [t if not isinstance(t, tuple) else t[1] for t in periods]

            class RelaxAllocation:
                def __init__(self, buyers_alloc, sellers_alloc, network_alloc, stats, scenario, V_vt):
                    self.BuyersAllocation = buyers_alloc
                    self.SellersAllocation = sellers_alloc
                    self.TransmissionNetworkAllocation = network_alloc
                    self.stats = stats
                    self.scenario = scenario
                    self.V_vt = V_vt

                def compute_welfare(self):
                    return self.stats["welfare"]

                def compute_feasibility_violations(self, violations=None, print_summary=False):
                    requested = set(violations or ["line", "line_current_limit"])
                    flow_mismatch = []
                    thermal_excess = []

                    for (v, w, period), p_vw in self.TransmissionNetworkAllocation.f_vwt.items():
                        q_vw = self.TransmissionNetworkAllocation.q_vwt.get((v, w, period), 0.0)

                        # Thermal limit check based on per-branch apparent flow magnitude.
                        line_mag = float(np.hypot(p_vw, q_vw))
                        v_min = self.scenario.network.nodes[v].get("V_min", 1.0)
                        f_max = self.scenario.network[v][w].get("F_max", 0.0)
                        thermal_limit = abs(v_min * f_max)
                        thermal_excess.append(max(0.0, line_mag - thermal_limit))

                        # Flow equation mismatch using recovered complex voltages.
                        if (v, period) in self.V_vt and (w, period) in self.V_vt:
                            Vd_v, Vq_v = self.V_vt[(v, period)]
                            Vd_w, Vq_w = self.V_vt[(w, period)]
                            g_vw = self.scenario.network[v][w].get("G", 0.0)
                            b_vw = self.scenario.network[v][w].get("B", 0.0)

                            vv_sq = Vd_v ** 2 + Vq_v ** 2
                            re_vvw = Vd_v * Vd_w + Vq_v * Vq_w
                            im_vvw = Vq_v * Vd_w - Vd_v * Vq_w

                            p_calc = g_vw * (vv_sq - re_vvw) + b_vw * im_vvw
                            q_calc = -b_vw * (vv_sq - re_vvw) + g_vw * im_vvw
                            flow_mismatch.append(float(np.hypot(p_vw - p_calc, q_vw - q_calc)))

                    result = {}
                    if "line" in requested:
                        result["line (A)"] = float(np.mean(flow_mismatch)) if flow_mismatch else np.nan
                    if "line_current_limit" in requested or not violations:
                        result["line_current_limit (A)"] = float(np.mean(thermal_excess)) if thermal_excess else np.nan
                    return result

            p_bt = self.get_p_bt_values()
            p_st = self.get_p_st_values()
            p_btl = self.get_p_btl_values()
            p_stl = self.get_p_stl_values()
            q_bt = self.get_q_bt_values()  # kept for completeness
            q_st = self.get_q_st_values()
            p_vwt = self.get_p_vwt_values()
            _ = self.get_q_vwt_values()  # computed but not used in RelaxAllocation
            V_vt = self.get_V_vt_values()
            u_st = self.get_u_st_values()
            phi_st = self.get_phi_st_values()

            buyers_alloc = SimpleBuyersAllocation(p_bt, p_btl, self.scenario.df_buyers, self.scenario.blocks_buyers)
            sellers_alloc = SimpleSellersAllocation(p_st, p_stl, u_st, phi_st, self.scenario.df_sellers)
            network_alloc = SimpleTransmissionNetworkAllocation(p_vwt, self.get_q_vwt_values(), self.scenario.network, self.scenario.periods)

            return RelaxAllocation(buyers_alloc, sellers_alloc, network_alloc, stats, self.scenario, V_vt)
        else:
            raise ValueError(
                "No allocation has been computed yet. Please call the solve() method first."
            )

    @abstractmethod
    def __str__(self) -> str:
        raise NotImplementedError(
            "The __str__ method should be implemented in subclasses to provide a meaningful string representation."
        )
