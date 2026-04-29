from mosek.fusion import Domain, Expr
import numpy as np
from power_flow_relaxations.models.nodal_base_model import NodalBaseModel


class Shor(NodalBaseModel):
    """
    Dense Shor SDP relaxation of ACOPF using a real-valued lifted matrix.

    The model uses a single PSD matrix per period to represent quadratic voltage
    products, then links active/reactive branch flows to linear expressions in that
    matrix. This is the non-chordal baseline SDP formulation.
    """

    def __init__(self, scenario, configuration, **kwargs):
        """
        Initialize the dense SDP relaxation and create lifted PSD variables.

        Parameters
        ----------
        scenario:
            Unit-based scenario with network/bids.
        configuration:
            Solver configuration; relaxation mode is forced to `True`.
        **kwargs:
            Forwarded to :class:`NodalBaseModel`.

        Notes
        -----
        Creates one PSD matrix `W[t]` of size `(2N x 2N)` for each period, where
        `N` is the number of buses.
        """
        if configuration is not None:
            configuration.relaxation = True
        super().__init__(scenario, configuration, **kwargs)

        self.W = [self.model.variable(f"W[{t}]", Domain.inPSDCone(2 * len(self.nodes))) for t, _ in self.periods]

    def power_constraints(self):
        """
        Add lifted AC power-flow constraints from the Shor SDP formulation.

        For each period:
        - constructs real/imag surrogate matrices from `W[t]`,
        - enforces symmetry of `W[t]`,
        - imposes linearized active/reactive flow equations with tolerances,
        - bounds nodal squared voltage magnitudes via diagonal terms,
        - applies branch current-rating constraints.
        """
        n = len(self.nodes)
        for t, _ in self.periods:
            W_t = self.W[t]
            diag_S = Expr.vstack([W_t[2 * i, 2 * i] + W_t[2 * i + 1, 2 * i + 1] for i in range(n)])

            # 0:n-1 --> 0, 2, ..., 2n
            # n:2n-1 --> 1, 3, ..., 2n-1 
            #W_im = W_t[:n, n:] - W_t[n:, :n]
            #W_1 = W_t[[(2 * i, 2 * j + 1) for i in range(n) for j in range(n)]] 
            W_1 = Expr.hstack([W_t[[(2 * i, 2 * j) for i in range(n)]] for j in range(n)])
            W_2 = Expr.hstack([W_t[[(2 * i, 2 * j + 1) for i in range(n)]] for j in range(n)])
            W_3 = Expr.hstack([W_t[[(2 * i + 1, 2 * j) for i in range(n)]] for j in range(n)])
            W_4 = Expr.hstack([W_t[[(2 * i + 1, 2 * j + 1) for i in range(n)]] for j in range(n)])
            W_im = W_2 - W_3
            W_re = Expr.repeat(diag_S, n, 1) - (W_1 + W_4)

            self.model.constraint(W_t == Expr.transpose(W_t))

            # Real power flow constraints
            self.model.constraint(
                self.p_vwt[:, :, t] - (Expr.mulElm(self.G, W_re) + Expr.mulElm(self.B, W_im)) <= self.p_vwt_line_tol
            )

            self.model.constraint(
                self.p_vwt[:, :, t] - (Expr.mulElm(self.G, W_re) + Expr.mulElm(self.B, W_im)) >= -self.p_vwt_line_tol
            )

            # Reactive power flow constraints
            self.model.constraint(
                self.q_vwt[:, :, t] - (- Expr.mulElm(self.B, W_re) + Expr.mulElm(self.G, W_im)) <= self.q_vwt_line_tol
            )

            self.model.constraint(
                self.q_vwt[:, :, t] - (- Expr.mulElm(self.B, W_re) + Expr.mulElm(self.G, W_im)) >= -self.q_vwt_line_tol
            )

            # Voltage magnitude constraints
            self.model.constraint(
                diag_S >= self.V_min ** 2
            )

            self.model.constraint(
                diag_S <= self.V_max ** 2
            )

        self.current_rating_constraints()

    def reference_constraints(self):
        """
        Anchor reference-bus voltage angle and magnitude in lifted coordinates.

        Enforces:
        - zero imaginary component at the reference bus,
        - unit real component magnitude at the reference bus.
        """
        for t, _ in self.periods:
            self.model.constraint(self.W[t][self.reference_bus[0] + 1, :] == 0)
            self.model.constraint(self.W[t][:, self.reference_bus[0] + 1] == 0)
            self.model.constraint(self.W[t][self.reference_bus[0] + 1, self.reference_bus[0] + 1] == 0)
            self.model.constraint(self.W[t][self.reference_bus[0], self.reference_bus[0]] == 1)

    def __str__(self):  # type: ignore
        """Return model identifier used in logs/results."""
        return "Shor"

    def get_V_vt_values(self) -> dict:
        """
        Recover approximate bus voltages from the solved Shor SDP matrices.

        For each period, symmetrizes `W[t]`, extracts a rank-1 approximation from
        the dominant eigenpair, reconstructs complex voltages, rotates them so the
        reference-bus angle is zero, and returns `(V_d, V_q)` per node and period.
        """

        voltages = []
        n = len(self.nodes)
        for t, _ in self.periods:
            W_t = self.W[t].level().reshape((2 * len(self.nodes), 2 * len(self.nodes)))
            W_t = (W_t + W_t.T) / 2

            eigvals, eigvecs = np.linalg.eigh(W_t)
            idx = np.argmax(eigvals)
            lambda1 = eigvals[idx]
            u1 = eigvecs[:, idx]
            V_approx = np.sqrt(lambda1) * u1

            V_approx = np.array([V_approx[2 * i] + 1j * V_approx[2 * i + 1] for i in range(n)])

            phase_ref = np.angle(V_approx[self.reference_bus[0]])
            V_approx = V_approx * np.exp(-1j * phase_ref)

            voltages.append(list(zip(V_approx.real, V_approx.imag)))

        return {
            (v, period): voltages[t][i_v]
            for i_v, v in self.nodes
            for t, period in self.periods
        }
