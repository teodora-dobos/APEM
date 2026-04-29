from power_flow_relaxations.models.nodal_base_model import NodalBaseModel

import numpy as np

class DCOPF(NodalBaseModel):
    """
    Linearized DC optimal power flow (DCOPF) relaxation on the nodal model scaffold.

    This model keeps only active-power network physics with voltage-angle variables
    and branch susceptances. Reactive-power AC relations are omitted, yielding a
    fast linear approximation commonly used as a baseline.
    
    Note: this is the relaxation-benchmark DCOPF variant (MOSEK-based), not the APEM market-clearing Gurobi DCOPF.
    """

    def __init__(self, scenario, configuration, **kwargs) -> None:
        """
        Initialize the DCOPF model and create bus-angle decision variables.

        Parameters
        ----------
        scenario:
            Unit-based scenario containing bids and transmission network.
        configuration:
            Solver configuration passed to the base nodal model.
        **kwargs:
            Optional arguments forwarded to :class:`NodalBaseModel`.

        Notes
        -----
        Creates `theta_vt` with shape `[n_nodes, n_periods]`, representing voltage
        phase angles used in linearized flow equations.
        """
        super().__init__(scenario, configuration, **kwargs)

        self.theta_vt = self.model.variable("theta_vt", [len(self.network), len(self.periods)])

    def power_constraints(self):
        """
        Add DC branch-flow and thermal-limit constraints.

        For each directed branch and period, enforce symmetric active-power flow
        limits and a linear DC flow relation between phase-angle differences and
        active power flow, with tolerance band `p_vwt_line_tol`.
        """
        for t, _ in self.periods:
            for i_v, v in self.nodes: 
                for i_w, _ in self.neighbours[v]:
                        
                    self.model.constraint(
                        self.p_vwt[i_v, i_w, t] >= - self.F_max[i_v, i_w] * (1 + self.I_viol[i_v, i_w, t] * self.I_viol_weight)
                    )
                    self.model.constraint(
                        self.p_vwt[i_v, i_w, t] <= self.F_max[i_v, i_w] * (1 + self.I_viol[i_v, i_w, t] * self.I_viol_weight)
                    )
                    self.model.constraint(
                        self.p_vwt[i_v, i_w, t] - self.B[i_v, i_w] * (self.theta_vt[i_v, t] - self.theta_vt[i_w, t]) <= self.p_vwt_line_tol
                    )
                    self.model.constraint(
                        self.p_vwt[i_v, i_w, t] - self.B[i_v, i_w] * (self.theta_vt[i_v, t] - self.theta_vt[i_w, t]) >= -self.p_vwt_line_tol
                    )


    def reference_constraints(self):
        """
        Fix the slack/reference bus angle to zero across all periods.

        This removes the rotational invariance of voltage angles and makes the
        linear system identifiable.
        """
        self.model.constraint(self.theta_vt[self.reference_bus[0], :] == 0)

    def get_V_vt_values(self) -> dict[tuple[int, int], tuple[float, float]]:
        """
        Reconstruct unit-magnitude complex voltage components from bus angles.

        Returns
        -------
        dict[tuple[int, int], tuple[float, float]]
            Mapping `(node, period) -> (V_d, V_q)` where
            `V_d = cos(theta)` and `V_q = sin(theta)`.
        """
        value = self.theta_vt.level().reshape([len(self.network), len(self.periods)])
        return {
            (v, period): (np.cos(value[i_v, t]), np.sin(value[i_v, t]))  # type: ignore
            for i_v, v in self.nodes
            for t, period in self.periods
            if value is not None
        }

    def __str__(self):
        """Return the model tag used in logs/results."""
        return "DCOPF_CVXPY"
