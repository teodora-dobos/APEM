from mosek.fusion import Domain, Expr
import numpy as np
import networkx as nx
from power_flow_relaxations.models.nodal_base_model import NodalBaseModel
from power_flow_relaxations.utils.network import compute_chordal_extension, construct_clique_graph, compute_reduced_cliques, psd_completion2

class ChordalShor(NodalBaseModel):
    """
    Chordal-decomposed Shor SDP relaxation for ACOPF.

    Uses clique-wise PSD matrices from a chordal extension of the network graph,
    plus overlap-consistency constraints, to approximate the dense Shor SDP with
    improved scalability on sparse grids.
    """

    def __init__(self, scenario, configuration, clique_reduction: float = 0.2, **kwargs):
        """
        Build the chordal Shor model and clique-wise PSD variables.

        Forces relaxation mode, computes a chordal extension, extracts reduced
        cliques, creates one PSD matrix per clique and period, and precomputes
        edge-to-clique mappings used by the flow constraints.
        """
        if configuration is not None:
            configuration.relaxation = True
        super().__init__(scenario, configuration, **kwargs)

        self.clique_reduction = clique_reduction if not hasattr(self, "clique_reduction") else self.clique_reduction
        self.chordal_extension = compute_chordal_extension(self.network)
        self.cliques = compute_reduced_cliques(self.chordal_extension, reduction=self.clique_reduction)

        self.clique_matrices = [[self.model.variable(f"W[{t}][{clique}]", Domain.inPSDCone(2 * len(clique))) for t, _ in self.periods] for clique in self.cliques]

        self.edge_to_clique_matrix = {}
        for t, _ in self.periods:
            for _, v in self.nodes:
                for _, w in self.neighbours[v] + [(_, v)]:
                    for clique, W in zip(self.cliques, self.clique_matrices):
                        if v in clique and w in clique:
                            idx_v = clique.index(v)
                            idx_w = clique.index(w)
                            self.edge_to_clique_matrix[v, w, t] = (W[t], idx_v, idx_w)
                            break

    def chordal_consistency_constraints(self):
        """
        Enforce agreement between overlapping clique PSD matrices.

        A maximum spanning tree of the clique-intersection graph is used as the
        stitching structure. For each tree edge `(C_i, C_j)`, all shared real/imag
        lifted entries corresponding to node pairs in `C_i ∩ C_j` are constrained
        equal for every period.

        This ensures local clique matrices define a globally consistent lifted
        representation on overlaps.
        """
        clique_tree = construct_clique_graph(self.cliques)
        maximum_tree = nx.maximum_spanning_tree(clique_tree, algorithm="prim")

        for i, j in maximum_tree.edges():
            W_i = self.clique_matrices[i]
            clique_i = self.cliques[i]
            W_j = self.clique_matrices[j]
            clique_j = self.cliques[j]
            intersection = set(clique_i).intersection(set(clique_j))
            for k_v, v in enumerate(intersection):
                for k_w, w in enumerate(intersection):
                    if k_v <= k_w:
                        idx_i_v = clique_i.index(v)
                        idx_i_w = clique_i.index(w)
                        idx_j_v = clique_j.index(v)
                        idx_j_w = clique_j.index(w)
                        for t, _ in self.periods:
                            self.model.constraint(W_i[t][2 * idx_i_v, 2 * idx_i_w] == W_j[t][2 * idx_j_v, 2 * idx_j_w])
                            self.model.constraint(W_i[t][2 * idx_i_v + 1, 2 * idx_i_w] == W_j[t][2 * idx_j_v + 1, 2 * idx_j_w])
                            self.model.constraint(W_i[t][2 * idx_i_v, 2 * idx_i_w + 1] == W_j[t][2 * idx_j_v, 2 * idx_j_w + 1])
                            self.model.constraint(W_i[t][2 * idx_i_v + 1, 2 * idx_i_w + 1] == W_j[t][2 * idx_j_v + 1, 2 * idx_j_w + 1])

    def power_constraints(self):
        """
        Add AC power-flow relaxation constraints in clique-matrix form.

        Enforces PSD-block symmetry, voltage-magnitude bounds, and active/reactive
        flow equations with tolerance bands, then adds current-rating and
        inter-clique consistency constraints.
        """
        for t, _ in self.periods:
            for W in self.clique_matrices:
                W_t = W[t]
                self.model.constraint(W_t == Expr.transpose(W_t))

            for i_v, v in self.nodes:
                (W_vvt, idx_v, _) = self.edge_to_clique_matrix[v, v, t]

                V_abs_sq = W_vvt[2 * idx_v, 2 * idx_v] + W_vvt[2 * idx_v + 1, 2 * idx_v + 1]

                # Voltage magnitude constraints
                self.model.constraint(
                    V_abs_sq >= self.V_min[i_v] ** 2
                )
                self.model.constraint(
                    V_abs_sq <= self.V_max[i_v] ** 2
                )

                for i_w, w in self.neighbours[v]:
                    (W_vwt, idx_v, idx_w) = self.edge_to_clique_matrix[v, w, t]
                    real_W = (V_abs_sq - (W_vwt[2 * idx_v, 2 * idx_w] + W_vwt[2 * idx_v + 1, 2 * idx_w + 1]))
                    imag_W = (W_vwt[2 * idx_v, 2 * idx_w + 1] - W_vwt[2 * idx_v + 1, 2 * idx_w])

                    # Real power flow constraints
                    self.model.constraint(
                        (self.p_vwt[i_v, i_w, t] - (self.G[i_v, i_w] * real_W + self.B[i_v, i_w] * imag_W)) <= self.p_vwt_line_tol
                    )
                    self.model.constraint(
                        (self.p_vwt[i_v, i_w, t] - (self.G[i_v, i_w] * real_W + self.B[i_v, i_w] * imag_W)) >= -self.p_vwt_line_tol
                    )
                    
                    # Reactive power flow constraints
                    self.model.constraint(
                        (self.q_vwt[i_v, i_w, t] - (- self.B[i_v, i_w] * real_W + self.G[i_v, i_w] * imag_W)) <= self.q_vwt_line_tol
                    )
                    self.model.constraint(
                        (self.q_vwt[i_v, i_w, t] - (- self.B[i_v, i_w] * real_W + self.G[i_v, i_w] * imag_W)) >= -self.q_vwt_line_tol
                    )

        self.current_rating_constraints()
        self.chordal_consistency_constraints()

    def reference_constraints(self):
        """
        Anchor the voltage-angle reference bus in the lifted space.

        Enforces unit reference magnitude and zero quadrature cross terms so the
        global angle reference is fixed.
        """
        for t, _ in self.periods:
            (W_rrt, idx_r, _) = self.edge_to_clique_matrix[self.reference_bus[1], self.reference_bus[1], t]
            self.model.constraint(
                W_rrt[2 * idx_r, 2 * idx_r] == 1
            )
            for i_v, v in self.neighbours[self.reference_bus[1]]:
                (W_rv, idx_rv_r, idx_rv_v) = self.edge_to_clique_matrix[self.reference_bus[1], v, t]
                (W_vr, idx_vr_r, idx_vr_v) = self.edge_to_clique_matrix[v, self.reference_bus[1], t]
                self.model.constraint(
                    W_rv[2 * idx_rv_r + 1, 2 * idx_rv_v] == 0
                )
                self.model.constraint(
                    W_rv[2 * idx_rv_v, 2 * idx_rv_r + 1] == 0
                )
                self.model.constraint(
                    W_vr[2 * idx_vr_r + 1, 2 * idx_vr_v] == 0
                )
                self.model.constraint(
                    W_vr[2 * idx_vr_v, 2 * idx_vr_r + 1] == 0
                )

    def __str__(self):  # type: ignore
        """Return the model tag used in logs/results."""
        return "ChordalShor"

    def get_V_vt_values(self) -> dict:
        """
        Recover approximate bus voltages from clique-based SDP matrices.

        For each period, aggregates clique matrix entries into a global lifted
        matrix, symmetrizes and PSD-completes it, extracts a rank-1 approximation
        from the dominant eigenpair, rotates the result to the reference angle, and
        returns `(V_d, V_q)` per node and period.
        """

        voltages = []
        for t, _ in self.periods:
            W_global = np.zeros((2 * len(self.nodes), 2 * len(self.nodes)), dtype=complex)
            W_counts = np.zeros((2 * len(self.nodes), 2 * len(self.nodes)), dtype=int)

            for clique, W_i in zip(self.cliques, self.clique_matrices):
                for k_v, v in enumerate(clique):
                    for k_w, w in enumerate(clique):
                        i_v = self.node_indices[v]
                        i_w = self.node_indices[w]
                        W_i_values = W_i[t].level().reshape((2 * len(clique), 2 * len(clique)))
                        W_global[2 * i_v, 2 * i_w] += W_i_values[2 * k_v, 2 * k_w]
                        W_counts[2 * i_v, 2 * i_w] += 1
                        W_global[2 * i_v + 1, 2 * i_w] += W_i_values[2 * k_v + 1, 2 * k_w]
                        W_counts[2 * i_v + 1, 2 * i_w] += 1
                        W_global[2 * i_v, 2 * i_w + 1] += W_i_values[2 * k_v, 2 * k_w + 1]
                        W_counts[2 * i_v, 2 * i_w + 1] += 1
                        W_global[2 * i_v + 1, 2 * i_w + 1] += W_i_values[2 * k_v + 1, 2 * k_w + 1]
                        W_counts[2 * i_v + 1, 2 * i_w + 1] += 1

            W_global = np.divide(W_global, W_counts, where=W_counts != 0)
            W_global = (W_global + W_global.T) / 2

            W_completed = psd_completion2(self.chordal_extension, W_global)

            eigvals, eigvecs = np.linalg.eigh(W_completed)
            idx = np.argmax(eigvals)
            lambda1 = eigvals[idx]
            u1 = eigvecs[:, idx]

            V_approx = np.sqrt(lambda1) * u1

            V_approx = np.array([V_approx[2 * i] + 1j * V_approx[2 * i + 1] for i in range(len(self.nodes))])

            phase_ref = np.angle(V_approx[self.reference_bus[0]])
            V_approx = V_approx * np.exp(-1j * phase_ref)

            voltages.append(list(zip(V_approx.real, V_approx.imag)))

        return {
            (v, period): voltages[t][i_v]
            for i_v, v in self.nodes
            for t, period in self.periods
        }
