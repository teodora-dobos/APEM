from tqdm import tqdm
from mosek.fusion import Domain, Expr
import numpy as np
import gc
from scipy.stats import qmc
from apem.unit_based_model.error import Error
from power_flow_relaxations.models import Jabr
from power_flow_relaxations.utils.network import partition_graph

class QC(Jabr):
    """
    Implementation of QC relaxation for ACOPF using CVXPY.
    """

    def global_qmc_envelope_bounds(self):
        """
        Compute bounds on theta_v - theta_w, sin(theta_v - theta_w), cos(theta_v - theta_w)
        by sampling voltage magnitudes and angles, then filtering based on thermal limits.

        Returns
        -------
        delta_theta_min, delta_theta_max, sin_min, sin_max, cos_min, cos_max : arrays [N, N]
        """

        if self.degree == 0:
            raise ValueError("Degree must be at least 1 to perform sampling.")

        N = len(self.nodes)
        T = len(self.periods)
        
        # Initialize output arrays
        delta_theta_min = np.full((N, N, T), -np.pi / 2)
        delta_theta_max = np.full((N, N, T), np.pi / 2)
        sin_min = np.full((N, N, T), -1.0)
        sin_max = np.full((N, N, T), 1.0)
        cos_min = np.full((N, N, T), -1.0)
        cos_max = np.full((N, N, T), 1.0)

        # Partition the graph
        components = partition_graph(self.network, 12)
        for comp_id, component in enumerate(components):
            print(f"[QC] Processing component {comp_id + 1}/{len(components)} with {len(component)} nodes")
            nodes = [(i_v, v) for i_v, v in self.nodes if v in component]
            component_index = {v: i for i, v in enumerate(component)}
            neighbours = {
                node: [(self.node_indices[w], w) for w in self.network[node] if w in component[node]] for node in self.network if node in component
            }
            size = len(component)
            sobol = qmc.Sobol(d=2 * size, scramble=True, seed=self.qmc_seed + comp_id).random_base2(m=self.degree)

            V_samples = np.full((2 ** self.degree, size, T), 1.0)
            theta_samples = np.full((2 ** self.degree, size, T), 0.0)
            for i_v, v in nodes:
                V_samples[:, component_index[v], :] = self.V_min[i_v] + (self.V_max[i_v] - self.V_min[i_v]) * sobol[:, 2 * component_index[v], None]
                if i_v == self.reference_bus[0]:
                    theta_samples[:, component_index[v], :] = 0.0
                else:
                    theta_samples[:, component_index[v], :] = np.pi * (2 * sobol[:, 2 * component_index[v] + 1, None] - 1)
            del sobol

            for i_v, v in nodes:
                for i_w, w in neighbours[v]:
                    feasible = np.zeros((2 ** self.degree, T), dtype=bool)
                    G_vw = self.G[i_v, i_w]
                    B_vw = self.B[i_v, i_w]
                    S_max_vw = self.S_max[i_v, i_w]

                    Vv_samples = V_samples[:, component_index[v], :]
                    Vw_samples = V_samples[:, component_index[w], :]

                    thetav_samples = theta_samples[:, component_index[v], :]
                    thetaw_samples = theta_samples[:, component_index[w], :]

                    delta_theta = thetav_samples - thetaw_samples
                    delta_theta = np.arctan(np.sin(delta_theta) / np.cos(delta_theta))
                    del thetav_samples, thetaw_samples

                    cos_dt = np.cos(delta_theta)
                    sin_dt = np.sin(delta_theta)

                    p_vw = G_vw * Vv_samples**2 - Vv_samples * Vw_samples * (G_vw * cos_dt + B_vw * sin_dt)
                    q_vw = -B_vw * Vv_samples**2 - Vv_samples * Vw_samples * (-B_vw * cos_dt + G_vw * sin_dt)
                    S_vw = np.sqrt(p_vw**2 + q_vw**2)
                    del p_vw, q_vw, Vv_samples, Vw_samples

                    feasible |= (S_vw <= S_max_vw)
                    del S_vw

                    delta_theta_f = delta_theta[feasible]
                    sin_f = sin_dt[feasible]
                    cos_f = cos_dt[feasible]
                    del sin_dt, cos_dt, delta_theta

                    delta_theta_min[i_v, i_w, :], delta_theta_max[i_v, i_w, :] = np.min(delta_theta_f), np.max(delta_theta_f)
                    sin_min[i_v, i_w, :], sin_max[i_v, i_w, :] = np.min(sin_f), np.max(sin_f)
                    cos_min[i_v, i_w, :], cos_max[i_v, i_w, :] = np.min(cos_f), np.max(cos_f)

            del V_samples, theta_samples, nodes, component_index, neighbours
            gc.collect()

        gc.collect()
        return delta_theta_min, delta_theta_max, sin_min, sin_max, cos_min, cos_max

    def local_qmc_envelope_bounds(self, jabr_allocation, eps_V, eps_theta):
        """
        Compute per-edge bounds on theta_v - theta_w, sin(theta_v - theta_w), cos(theta_v - theta_w)
        by sampling around the Jabr solution with Sobol sequences, filtering based on thermal limits.
        Adaptive theta perturbation is applied per edge.
        """
        if self.degree == 0:
            raise ValueError("Degree must be at least 1 to perform sampling.")

        V_vt_jabr = jabr_allocation.V_vt  # Dict[(node, period), (Vd, Vq)]
        N = len(self.nodes)
        T = len(self.periods)

        # Extract voltage magnitudes and angles from Jabr solution
        V_jabr = np.zeros((N, T))
        theta_jabr = np.zeros((N, T))
        for t_idx, period in self.periods:
            for i_v, v in self.nodes:
                Vd_vt, Vq_vt = V_vt_jabr[v, period]
                V_jabr[i_v, t_idx] = np.sqrt(Vd_vt**2 + Vq_vt**2)
                theta_jabr[i_v, t_idx] = np.arctan2(Vq_vt, Vd_vt)

        print(f"[QC] Performing local sampling around Jabr solution (eps_V={eps_V}, eps_θ={eps_theta})")

        # Initialize output arrays
        delta_theta_min = np.full((N, N, T), -np.pi / 2)
        delta_theta_max = np.full((N, N, T), np.pi / 2)
        sin_min = np.full((N, N, T), -1.0)
        sin_max = np.full((N, N, T), 1.0)
        cos_min = np.full((N, N, T), -1.0)
        cos_max = np.full((N, N, T), 1.0)


        for t, period in self.periods:
            components = partition_graph(self.network, 10, min_size=8, max_size=16)
            for comp_id, component in enumerate(components):
                nodes = [(i_v, v) for i_v, v in self.nodes if v in component]
                component_index = {v: i for i, v in enumerate(component)}
                neighbours = {
                    node: [(self.node_indices[w], w) for w in self.network[node] if w in component[node]] for node in self.network if node in component
                }
                size = len(component)
                sobol = qmc.Sobol(d=2 * size, scramble=True, seed=self.qmc_seed + comp_id).random_base2(m=self.degree)

                V_samples = np.full((2 ** self.degree, size, T), 1.0)
                theta_samples = np.full((2 ** self.degree, size, T), 0.0)
                for i_v, v in nodes:
                    if i_v == self.reference_bus[0]:
                        V_samples[:, component_index[v], t] = 1.0
                        theta_samples[:, component_index[v], t] = 0.0
                    else:
                        V_samples[:, component_index[v], t] = V_jabr[i_v, t] + eps_V * (self.V_max[i_v] - self.V_min[i_v]) / 2 * sobol[:, 2 * component_index[v]]
                        theta_samples[:, component_index[v], t] = theta_jabr[i_v, t] + eps_theta * np.pi * (2 * sobol[:, 2 * component_index[v] + 1] - 1)
                del sobol

                for i_v, v in nodes:
                    for i_w, w in neighbours[v]:
                        feasible = np.zeros((2 ** self.degree,), dtype=bool)
                        G_vw = self.G[i_v, i_w]
                        B_vw = self.B[i_v, i_w]
                        S_max_vw = self.S_max[i_v, i_w]

                        Vv_samples = V_samples[:, component_index[v], t]
                        Vw_samples = V_samples[:, component_index[w], t]

                        thetav_samples = theta_samples[:, component_index[v], t]
                        thetaw_samples = theta_samples[:, component_index[w], t]

                        delta_theta = thetav_samples - thetaw_samples
                        delta_theta = np.arctan(np.sin(delta_theta) / np.cos(delta_theta))

                        del thetav_samples, thetaw_samples

                        cos_dt = np.cos(delta_theta)
                        sin_dt = np.sin(delta_theta)

                        p_vw = G_vw * Vv_samples**2 - Vv_samples * Vw_samples * (G_vw * cos_dt + B_vw * sin_dt)
                        q_vw = -B_vw * Vv_samples**2 - Vv_samples * Vw_samples * (-B_vw * cos_dt + G_vw * sin_dt)
                        S_vw = np.sqrt(p_vw**2 + q_vw**2)
                        del p_vw, q_vw, Vv_samples, Vw_samples

                        feasible |= (S_vw <= S_max_vw)
                        del S_vw
                        if not np.any(feasible):
                            print(f"[QC] Warning: No feasible samples found for edge ({v}, {w}) at period {period} during local sampling.")
                            continue

                        delta_theta_f = delta_theta[feasible]
                        sin_f = sin_dt[feasible]
                        cos_f = cos_dt[feasible]

                        del delta_theta, sin_dt, cos_dt

                        delta_theta_min[i_v, i_w, t], delta_theta_max[i_v, i_w, t] = np.min(delta_theta_f), np.max(delta_theta_f)
                        sin_min[i_v, i_w, t], sin_max[i_v, i_w, t] = np.min(sin_f), np.max(sin_f)
                        cos_min[i_v, i_w, t], cos_max[i_v, i_w, t] = np.min(cos_f), np.max(cos_f)

                del V_samples, theta_samples, nodes, component_index, neighbours
                gc.collect()

        gc.collect()
        return delta_theta_min, delta_theta_max, sin_min, sin_max, cos_min, cos_max
    
    def mccormick_envelope(self, t, x, y, xL, xU, yL, yU):
        """
        Add McCormick envelope constraints for the bilinear term `t = x * y`.

        Uses variable bounds `(xL, xU)` and `(yL, yU)` to add the four linear
        inequalities that define the convex hull relaxation.
        """
        self.model.constraint(t >= xL * y + yL * x - xL * yL)
        self.model.constraint(t >= xU * y + yU * x - xU * yU)
        self.model.constraint(t <= xL * y + yU * x - xL * yU)
        self.model.constraint(t <= xU * y + yL * x - xU * yL)

    def square_envelope(self, t, x, xL, xU):
        """
        Add convex-envelope constraints for the quadratic term `t = x^2`.

        Uses an upper linear secant bound on `[xL, xU]` and a rotated-cone lower
        bound to keep `t` as a convex relaxation of `x^2`.
        """
        self.model.constraint(t <= (xL + xU) * x - xL * xU)
        self.model.constraint(Expr.vstack([t, Expr.constTerm(0.5), x]) == Domain.inRotatedQCone())

    def sin_envelope(self, t, x, xL, xU):
        """
        Add convex relaxation bounds for the nonlinear term `t = sin(x)`.

        Builds tangent/chord-based bounds over `[xL, xU]` to approximate the sine
        graph with linear constraints.
        """
        xM = max(abs(xL), abs(xU))
        self.model.constraint(t <= np.cos(xM / 2) * (x - xM / 2) + np.sin(xM / 2))
        self.model.constraint(t >= np.cos(xM / 2) * (x + xM / 2) - np.sin(xM / 2))

        if xL < xU and xL >= 0:
            self.model.constraint(
                t >= (np.sin(xL) - np.sin(xU)) / (xL - xU) * (x - xL) + np.sin(xL)
            )
        if xL < xU and xU <= 0:
            self.model.constraint(
                t <= (np.sin(xL) - np.sin(xU)) / (xL - xU) * (x - xL) + np.sin(xL)
            )

    def cos_envelope(self, t, x, xL, xU):
        """
        Add convex relaxation bounds for the nonlinear term `t = cos(x)`.

        Uses a quadratic-cone-supported upper bound and a chord lower bound over
        `[xL, xU]` to approximate the cosine graph.
        """
        xM = max(abs(xL), abs(xU))
        if xM != 0:
            alpha = (1 - np.cos(xM)) / (xM**2)
            y = self.model.variable(1, Domain.unbounded())
            self.model.constraint(Expr.vstack([y, Expr.constTerm(0.5), x]) == Domain.inRotatedQCone())
            self.model.constraint(t + alpha * y <= 1)

        if xL < xU:
            self.model.constraint(t >= (np.cos(xL) - np.cos(xU)) / (xL - xU) * (x - xL) + np.cos(xL))

    def __init__(self, scenario, configuration, degree=8, seed=42, local_sampling=True, eps_V=0.1, eps_theta=0.15, custom_envelope_bounds=None, **kwargs):
        super().__init__(scenario, configuration, **kwargs)

        if degree < 1:
            raise ValueError("Degree must be at least 1 to perform sampling.")

        self.degree = degree if not hasattr(self, "degree") else self.degree
        self.V_abs_vt = self.model.variable("V_abs_vt", [len(self.nodes), len(self.periods)], Domain.greaterThan(0))
        self.theta_vt = self.model.variable("theta_vt", [len(self.nodes), len(self.periods)])
        self.qmc_seed = seed if not hasattr(self, "qmc_seed") else self.qmc_seed
        
        # Sampling parameters
        self.local_sampling = local_sampling if not hasattr(self, "local_sampling") else self.local_sampling

        self.eps_V = eps_V if not hasattr(self, "eps_V") else self.eps_V
        self.eps_theta = eps_theta if not hasattr(self, "eps_theta") else self.eps_theta

        self.custom_envelope_bounds = custom_envelope_bounds if not hasattr(self, "custom_envelope_bounds") else self.custom_envelope_bounds
        self.jabr_kwargs = kwargs if not hasattr(self, "jabr_kwargs") else self.jabr_kwargs
        self.jabr_allocation = None if not hasattr(self, "jabr_allocation") else self.jabr_allocation

    def solve(self, **kwargs):
        allocation = super().solve(**kwargs)

        if not self.local_sampling:
            return allocation

        if isinstance(allocation, Error):
            if isinstance(self.jabr_allocation, (Error, None)):
                return allocation
            else:
                return self.jabr_allocation

        jabr_violations = self.jabr_allocation.compute_feasibility_violations(violations=["line"], print_summary=False)
        actual_violations = allocation.compute_feasibility_violations(violations=["line"], print_summary=False)
        jabr_line = jabr_violations.get("line (A)")
        actual_line = actual_violations.get("line (A)")
        if jabr_line is None or actual_line is None:
            return allocation

        if actual_line > jabr_line:
            print(f"[QC] Warning: QC solution has higher line violations ({actual_violations['line (A)']:.4f} A) than Jabr ({jabr_violations['line (A)']:.4f} A). Reverting to Jabr solution.")
            return self.jabr_allocation
        else:
            return allocation

        
    def power_constraints(self):
        super().power_constraints()

        if self.custom_envelope_bounds is not None:
            delta_theta_min, delta_theta_max, sin_min, sin_max, cos_min, cos_max = self.custom_envelope_bounds
        else:
            if self.local_sampling:
                print("[QC] Solving Jabr relaxation for local sampling...")
                jabr_model = Jabr(self.scenario, self.configuration, **self.jabr_kwargs)
                self.jabr_allocation = jabr_model.solve(force_integrality=True)
                delta_theta_min, delta_theta_max, sin_min, sin_max, cos_min, cos_max = self.local_qmc_envelope_bounds(self.jabr_allocation, self.eps_V, self.eps_theta)
                self.custom_envelope_bounds = (delta_theta_min, delta_theta_max, sin_min, sin_max, cos_min, cos_max)
            else:
                print("[QC] Performing global sampling across full voltage/angle ranges")
                delta_theta_min, delta_theta_max, sin_min, sin_max, cos_min, cos_max = self.global_qmc_envelope_bounds()
                self.custom_envelope_bounds = (delta_theta_min, delta_theta_max, sin_min, sin_max, cos_min, cos_max)

        for t, _ in self.periods:
            for i_v, v in self.nodes:
                self.square_envelope(self.c_vwt[t][i_v, i_v],
                                    self.V_abs_vt[i_v, t],
                                    self.V_min[i_v],
                                    self.V_max[i_v],
                                )
                        
                for i_w, _ in self.neighbours[v]:

                    m_vwt = self.model.variable(f"m_[{i_v}, {i_w}, {t}]", 1, Domain.greaterThan(0)) # V_abs_vt[i_v, t] * V_abs_vt[i_w, t]
                    self.mccormick_envelope(
                        m_vwt,
                        self.V_abs_vt[i_v, t],
                        self.V_abs_vt[i_w, t],
                        self.V_min[i_v],
                        self.V_max[i_v],
                        self.V_min[i_w],
                        self.V_max[i_w]
                    )

                    cos_vwt = self.model.variable(f"cos_[{i_v}, {i_w}, {t}]", 1) # cos(theta_vt[i_v, t] - theta_vt[i_w, t])
                    self.cos_envelope(
                        cos_vwt,
                        self.theta_vt[i_v, t] - self.theta_vt[i_w, t],
                        delta_theta_min[i_v, i_w, t],
                        delta_theta_max[i_v, i_w, t]
                    )
                
                    sin_vwt = self.model.variable(f"sin_[{i_v}, {i_w}, {t}]", 1) # sin(theta_vt[i_v, t] - theta_vt[i_w, t])
                    self.sin_envelope(
                        sin_vwt,
                        self.theta_vt[i_v, t] - self.theta_vt[i_w, t],
                        delta_theta_min[i_v, i_w, t],
                        delta_theta_max[i_v, i_w, t]
                    )
                    
                    self.mccormick_envelope(
                        self.c_vwt[t][i_v, i_w],
                        m_vwt,
                        cos_vwt,
                        self.V_min[i_v] * self.V_min[i_w],
                        self.V_max[i_v] * self.V_max[i_w],
                        cos_min[i_v, i_w, t],
                        cos_max[i_v, i_w, t]
                    )

                    self.mccormick_envelope(
                        self.s_vwt[t][i_v, i_w],
                        m_vwt,
                        sin_vwt,
                        self.V_min[i_v] * self.V_min[i_w],
                        self.V_max[i_v] * self.V_max[i_w],
                        sin_min[i_v, i_w, t],
                        sin_max[i_v, i_w, t]
                    )

    def __str__(self):  # type: ignore
        return "QC"
