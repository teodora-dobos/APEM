import random
import networkx as nx
import numpy as np


def symbolic_cholesky(adj: np.ndarray) -> np.ndarray:
    n = adj.shape[0]

    # Optional minimum degree ordering
    degrees = adj.sum(axis=1)
    perm = np.argsort(degrees)
    adj = adj[perm][:, perm]

    # Track adjacency during elimination
    chordal = adj.copy()
    for k in range(n):
        neighbors = np.where(chordal[k, k + 1 :] != 0)[0] + (k + 1)
        for i in range(len(neighbors)):
            for j in range(i + 1, len(neighbors)):
                chordal[neighbors[i], neighbors[j]] = 1
                chordal[neighbors[j], neighbors[i]] = 1

    np.fill_diagonal(chordal, 0)

    inv_perm = np.argsort(perm)
    chordal = chordal[inv_perm][:, inv_perm]
    return chordal


def compute_chordal_extension(graph: nx.Graph) -> nx.Graph:
    adj = nx.to_numpy_array(graph)
    adj_chordal_ext = symbolic_cholesky(adj)
    return nx.from_numpy_array(adj_chordal_ext, nodelist=graph.nodes())


def construct_clique_graph(cliques: list[list]) -> nx.Graph:
    edges = []
    for i, clique_i in enumerate(cliques):
        for j, clique_j in enumerate(cliques):
            intersection = len(set(clique_i).intersection(set(clique_j)))
            if i < j and intersection > 0:
                edges.append((i, j, intersection))

    clique_graph: nx.Graph = nx.Graph()
    clique_graph.add_weighted_edges_from(edges)
    return clique_graph


def perfect_elimination_ordering(graph: nx.Graph, reverse: bool = False) -> list:
    if not nx.is_chordal(graph):
        raise ValueError("Expected chordal graph")

    nodes = list(enumerate(graph.nodes()))
    indices = {v: i for i, v in nodes}

    n = len(nodes)
    labels = np.zeros(n, dtype=int)
    visited = np.zeros(n, dtype=bool)
    peo = []

    for _ in range(n):
        i_v, v = nodes[np.argmax(labels * (~visited))]
        visited[i_v] = True
        peo.append(v)

        for u in graph[v]:
            i_u = indices[u]
            if not visited[i_u]:
                labels[i_u] = labels[i_u] + 1
    if not reverse:
        peo.reverse()
    return peo


def psd_completion(graph: nx.Graph, W: np.ndarray, inplace: bool = False):
    if W.shape[0] != W.shape[1] or W.shape[0] != len(graph):
        raise ValueError("Weight matrix must be square and match the number of nodes in the graph.")

    peo = perfect_elimination_ordering(graph, reverse=True)

    if not inplace:
        W = W.copy()

    nodes = list(enumerate(graph.nodes()))
    node_indices = {v: i for i, v in nodes}

    def indices(nodes):
        return [node_indices[v] for v in nodes]

    subnodes = [peo.pop(0)]
    while peo:
        v = peo.pop(0)

        S = [v]
        U = [u for u in subnodes if u in graph[v]]
        T = [u for u in subnodes if u not in U]

        W_SU = W[np.ix_(indices(S), indices(U))]
        W_UU = W[np.ix_(indices(U), indices(U))]
        W_TU = W[np.ix_(indices(T), indices(U))]

        W[np.ix_(indices(S), indices(T))] = W_SU @ np.linalg.pinv(W_UU) @ W_TU.T
        W[np.ix_(indices(T), indices(S))] = W_TU @ np.linalg.pinv(W_UU) @ W_SU.T

        subnodes.append(v)

    return W


def psd_completion2(graph: nx.Graph, W: np.ndarray, inplace: bool = False):
    if W.shape[0] != W.shape[1] or W.shape[0] != 2 * len(graph):
        raise ValueError("Weight matrix must be square and match the number of nodes in the graph.")

    peo = perfect_elimination_ordering(graph, reverse=True)

    if not inplace:
        W = W.copy()

    nodes = list(enumerate(graph.nodes()))
    node_indices = {v: i for i, v in nodes}

    def indices(nodes):
        idx = []
        for v in nodes:
            idx.append(2 * node_indices[v])
            idx.append(2 * node_indices[v] + 1)
        return idx

    subnodes = [peo.pop(0)]
    while peo:
        v = peo.pop(0)

        S = [v]
        U = [u for u in subnodes if u in graph[v]]
        T = [u for u in subnodes if u not in U]

        W_SU = W[np.ix_(indices(S), indices(U))]
        W_UU = W[np.ix_(indices(U), indices(U))]
        W_TU = W[np.ix_(indices(T), indices(U))]

        W[np.ix_(indices(S), indices(T))] = W_SU @ np.linalg.pinv(W_UU) @ W_TU.T
        W[np.ix_(indices(T), indices(S))] = W_TU @ np.linalg.pinv(W_UU) @ W_SU.T

        subnodes.append(v)

    return W


def compute_reduced_cliques(graph: nx.Graph, reduction: float = 0.2, real_valued: bool = True) -> list[list]:
    if nx.is_chordal(graph):
        cliques = {k: list(clique) for k, clique in enumerate(nx.chordal_graph_cliques(graph))}
    else:
        cliques = {k: list(clique) for k, clique in enumerate(nx.find_cliques(graph))}

    clique_tree = nx.maximum_spanning_tree(construct_clique_graph(list(cliques.values())), algorithm="prim")

    n = len(cliques)
    N = len(cliques) * reduction
    while len(cliques) > N:
        deltas = []
        for i, j, data in clique_tree.edges(data=True):
            weight = data["weight"]
            d_i = len(cliques[i])
            d_j = len(cliques[j])
            d_ij = d_i + d_j - weight
            if real_valued:
                deltas.append(
                    (i, j, d_ij * (2 * d_ij + 1) - (d_i * (2 * d_i + 1) + d_j * (2 * d_j + 1) + weight * (2 * weight + 1)))
                )
            else:
                deltas.append(
                    (
                        i,
                        j,
                        d_ij * (d_ij + 1) / 2
                        - (d_i * (d_i + 1) / 2 + d_j * (d_j + 1) / 2 + weight * (weight + 1) / 2),
                    )
                )

        i, j, _ = min(deltas, key=lambda item: item[2])
        merged_clique = list(set(cliques[i]) | set(cliques[j]))
        cliques = {k: clique for k, clique in cliques.items() if k not in (i, j)}
        cliques[n] = merged_clique
        n += 1

        neighbors = set(clique_tree.neighbors(i)) | set(clique_tree.neighbors(j))
        clique_tree.remove_node(i)
        clique_tree.remove_node(j)
        for neighbor in neighbors:
            if neighbor != i and neighbor != j:
                weight = len(set(merged_clique).intersection(set(cliques[neighbor])))
                if weight > 0:
                    clique_tree.add_edge(n - 1, neighbor, weight=weight)

    return list(cliques.values())


def random_connected_subgraph(graph: nx.Graph, n_nodes: int, seed: int = 42) -> nx.Graph:
    if not nx.is_connected(graph):
        raise ValueError("Input graph must be connected.")

    rng = random.Random(seed)
    start_node = rng.choice(list(graph.nodes()))
    sub_nodes = {start_node}

    while len(sub_nodes) < n_nodes:
        frontier = {neighbor for node in sub_nodes for neighbor in graph.neighbors(node)}
        frontier = frontier - sub_nodes
        if not frontier:
            raise ValueError("Cannot find enough connected nodes to form the subgraph.")
        sub_nodes.add(rng.choice(list(frontier)))

    return graph.subgraph(sub_nodes).copy()


def partition_graph(G: nx.Graph, target_size, min_size=8, max_size=None, tolerance=0.2):
    """
    Partition a graph into roughly equal-sized connected subgraphs using edge-cut minimization.

    Parameters:
    - G (nx.Graph): The input graph to partition.
    - target_size (int): Desired size of each partition (number of nodes).
    - min_size (int): Minimum acceptable size of a partition.
    - max_size (int, optional): Maximum acceptable size of a partition. Defaults to 2 * target_size.
    - tolerance (float): Allowable deviation from target_size (fraction).

    Returns:
    - list of nx.Graph: The resulting partitions (each is a connected subgraph).
    """
    if max_size is None:
        max_size = int(2 * target_size)

    partitions = []
    remaining_graph = G.copy()

    while remaining_graph.number_of_nodes() > max_size:
        cut_value, (set1, set2) = nx.stoer_wagner(remaining_graph)
        if len(set1) < min_size or len(set2) < min_size:
            break

        best_partition = None
        best_balance = None
        for subset in (set1, set2):
            balance = abs(len(subset) - target_size) / target_size
            if balance <= tolerance and (best_balance is None or balance < best_balance):
                best_balance = balance
                best_partition = subset

        if best_partition is not None:
            partitions.append(remaining_graph.subgraph(best_partition).copy())
            remaining_nodes = set(remaining_graph.nodes()) - set(best_partition)
            remaining_graph = remaining_graph.subgraph(remaining_nodes).copy()
        else:
            break

    if remaining_graph.number_of_nodes() >= min_size:
        partitions.append(remaining_graph)

    return partitions
