from typing import Any

from power_flow_relaxations.models.nodal_base_model import NodalBaseModel

from mosek.fusion import Expr, Domain
from collections import deque


class Jabr(NodalBaseModel):
    """
    Jabr-style SOCP relaxation of ACOPF on the nodal market model.

    The model introduces auxiliary voltage-product variables:
    - `c_vw` for cosine-like real products,
    - `s_vw` for sine-like imaginary products,
    and enforces second-order cone envelopes that relax nonconvex AC equalities.
    """

    def __init__(self, scenario, configuration, **kwargs):
        """
        Initialize Jabr relaxation variables on top of the base nodal model.

        Parameters
        ----------
        scenario:
            Unit-based scenario (network, bids, periods).
        configuration:
            Solver configuration object.
        **kwargs:
            Extra options forwarded to :class:`NodalBaseModel`.

        Notes
        -----
        Creates per-period dense matrices `c_vwt` and `s_vwt` of shape
        `[n_nodes, n_nodes]` used in relaxed AC flow equations.
        """
        super().__init__(scenario, configuration, **kwargs)

        self.c_vwt = [self.model.variable(f"c_vw[{t}]", [len(self.nodes), len(self.nodes)]) for t, _ in self.periods]
        self.s_vwt = [self.model.variable(f"s_vw[{t}]", [len(self.nodes), len(self.nodes)]) for t, _ in self.periods]

    def power_constraints(self):
        """
        Add Jabr SOCP power-flow constraints for every period and branch.

        Includes:
        - active/reactive flow consistency with `(c_vw, s_vw)` terms,
        - cone constraints coupling diagonal and off-diagonal voltage products,
        - symmetry/skew-symmetry structure (`c = c^T`, `s = -s^T`),
        - voltage magnitude bounds on diagonal entries of `c`.

        Finally delegates thermal current limits to
        :meth:`NodalBaseModel.current_rating_constraints`.
        """
        for t, _ in self.periods:
            c_vw = self.c_vwt[t]
            s_vw = self.s_vwt[t]
            diag_c = c_vw.diag()

            # Consistency constraints
            for i_v, v in self.nodes:
                for i_w, _ in self.neighbours[v]:

                    # Real power flow constraints
                    self.model.constraint(self.p_vwt[i_v, i_w, t] - self.G[i_v, i_w] * (diag_c[i_v] - c_vw[i_v, i_w]) + self.B[i_v, i_w] * s_vw[i_v, i_w] <= self.p_vwt_line_tol)
                    self.model.constraint(self.p_vwt[i_v, i_w, t] - self.G[i_v, i_w] * (diag_c[i_v] - c_vw[i_v, i_w]) + self.B[i_v, i_w] * s_vw[i_v, i_w] >= -self.p_vwt_line_tol)

                    # Reactive power flow constraints
                    self.model.constraint(self.q_vwt[i_v, i_w, t] - (- self.B[i_v, i_w] * (diag_c[i_v] - c_vw[i_v, i_w]) + self.G[i_v, i_w] * s_vw[i_v, i_w]) <= self.q_vwt_line_tol)
                    self.model.constraint(self.q_vwt[i_v, i_w, t] - (- self.B[i_v, i_w] * (diag_c[i_v] - c_vw[i_v, i_w]) + self.G[i_v, i_w] * s_vw[i_v, i_w]) >= -self.q_vwt_line_tol)

                    diag_diff = (diag_c[i_v] - diag_c[i_w]) / 2
                    diag_sum = (diag_c[i_v] + diag_c[i_w]) / 2
                    self.model.constraint(Expr.vstack([diag_sum, diag_diff, c_vw[i_v, i_w], s_vw[i_v, i_w]]) == Domain.inQCone())

            self.model.constraint(
                c_vw == Expr.transpose(c_vw)
            )
            self.model.constraint(
                s_vw == -Expr.transpose(s_vw)
            )

            # Voltage magnitude constraints
            self.model.constraint(
                diag_c >= self.V_min ** 2
            )
            self.model.constraint(
                diag_c <= self.V_max ** 2
            )

        self.current_rating_constraints()

    def reference_constraints(self):
        """
        Set reference-bus voltage magnitude in lifted coordinates.

        For each period, constrains the reference-bus diagonal `c_rr` entry to 1,
        corresponding to unit voltage magnitude at the slack bus.
        """
        for t, _ in self.periods:
            self.model.constraint(
                self.c_vwt[t][self.reference_bus[0], self.reference_bus[0]] == 1
            )

    def __str__(self):  # type: ignore
        """Return model identifier used in logs/results."""
        return "Jabr"

    def get_V_vt_values(self) -> dict:
        """
        Recover approximate bus voltages from solved `(c_vw, s_vw)` values.

        Starts from the reference bus voltage, traverses the network graph, and
        reconstructs neighboring complex voltages using local `c_vw`/`s_vw`
        relationships. Returns `(V_d, V_q)` per node and period.
        """
        c_vwt_values = [self.c_vwt[t].level().reshape((len(self.nodes), len(self.nodes))) for t, _ in self.periods]
        s_vwt_values = [self.s_vwt[t].level().reshape((len(self.nodes), len(self.nodes))) for t, _ in self.periods]

        voltages = [
            {i_v: None for i_v, _ in self.nodes} | {self.reference_bus[0]: (1.0, 0.0)},
        ] * len(self.periods)

        visited = set()
        queue: deque[tuple[int, Any]] = deque()
        queue.append(self.reference_bus)
        visited.add(self.reference_bus[0])
        while queue:
            i_v, v = queue.popleft()
            for i_w, w in self.neighbours[v]:
                if i_w not in visited:
                    # Calculate the voltage at w based on the voltage at v
                    # Python type inference is not strong enough to know that voltages[t][v] always exists
                    # and is a tuple of (V_dv, V_qv). So we ignore the type error here.

                    for t, _ in self.periods:
                        V_dv, V_qv = voltages[t][i_v]  # type: ignore
                        V_dw = (
                            V_dv * c_vwt_values[t][i_v, i_w]  # type: ignore
                            - V_qv * s_vwt_values[t][i_v, i_w]  # type: ignore
                        ) / (V_dv**2 + V_qv**2)
                        V_qw = (
                            V_qv * c_vwt_values[t][i_v, i_w]  # type: ignore
                            + V_dv * s_vwt_values[t][i_v, i_w]  # type: ignore
                        ) / (V_dv**2 + V_qv**2)
                        voltages[t][i_w] = (V_dw, V_qw)  # type: ignore

                    queue.append((i_w, w))
                    visited.add(i_w)

        return {
            (v, period): voltages[t][i_v]
            for i_v, v in self.nodes
            for t, period in self.periods
        }
