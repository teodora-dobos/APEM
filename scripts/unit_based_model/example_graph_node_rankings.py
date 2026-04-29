"""
Example script for computing graph and PTDF-based node rankings.

The script:
1. parses one unit-based dataset from APEM,
2. computes the PTDF matrix for a chosen slack bus,
3. ranks nodes by PTDF impact, degree centrality, and betweenness centrality,
4. creates per-metric top-k node plots on the APEM Germany map,
5. writes all outputs to a timestamped evaluation folder.

You can adapt the run by editing the constants near the top of the file:
- `DATASET`: unit-based dataset used for parsing and ranking.
- `SLACK_NODE`: node label used as PTDF slack bus (`None` means first node in graph order).
- `PTDF_METHODS`: PTDF-based node ranking aggregations to compute.
- `TOP_K_PRINT`: number of top-ranked items printed to stdout for quick inspection.
- `TOP_K_PLOT`: number of top-ranked nodes highlighted in each metric plot.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

if "MPLCONFIGDIR" not in os.environ:
    os.environ["MPLCONFIGDIR"] = str(Path(__file__).resolve().parents[2] / ".matplotlib_cache")

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import geopandas as gpd
import networkx as nx
from shapely.geometry import LineString, Point

# Ensure repo root is on sys.path when run directly
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from apem.unit_based_model.enums import UnitBased_Datasets
from apem.unit_based_model.utils.paths import RAW_DATA_DIR
from node_ranking.market_scores import compute_ptdf
from node_ranking.rank_nodes import (
    rank_nodes_by_betweenness,
    rank_nodes_by_degree,
    rank_nodes_by_ptdf,
)

DATASET = UnitBased_Datasets.PyPSAEurLarge
SLACK_NODE = None
PTDF_METHODS = ("sum", "max", "weighted_sum")
TOP_K_PRINT = 10
TOP_K_PLOT = 10


def _scenario_name() -> str:
    return DATASET.name


def _output_dir(scenario_name: str) -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_dir = (
        ROOT
        / "results"
        / "unit_based_model"
        / f"{scenario_name}_results"
        / "evaluation"
        / "node_ranking"
        / timestamp
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def _ranking_to_df(ranking: list[tuple[object, float]], key_name: str) -> pd.DataFrame:
    return pd.DataFrame(
        [{key_name: key, "score": float(score)} for key, score in ranking]
    )


def _safe_metric_name(metric_name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_]+", "_", metric_name.strip()).strip("_").lower()


def _extract_coord_map(graph: nx.Graph, nodes_agents: dict) -> dict:
    coord_map = {}
    for node in graph.nodes():
        data = nodes_agents.get(node, None)
        if data is None:
            data = nodes_agents.get(str(node), None)
        if isinstance(data, dict):
            lat = data.get("latitude")
            lon = data.get("longitude")
            if lat is not None and lon is not None:
                coord_map[node] = (float(lon), float(lat))
    return coord_map


def _save_topk_node_highlight_plot_fallback(
    graph: nx.Graph,
    ranking: list[tuple[object, float]],
    metric_name: str,
    output_path: Path,
    top_k: int,
) -> None:
    """Fallback drawing if geographic coordinates are unavailable."""
    positions = nx.spring_layout(graph, seed=42)
    ranking = [(node, float(score)) for node, score in ranking]
    top = ranking[:top_k]
    top_nodes = [node for node, _ in top]
    top_set = set(top_nodes)
    score_map = dict(ranking)

    fig, ax = plt.subplots(figsize=(13, 10))
    nx.draw_networkx_edges(graph, positions, ax=ax, edge_color="#D9D9D9", width=0.6, alpha=0.35)

    other_nodes = [node for node in graph.nodes() if node not in top_set]
    if other_nodes:
        nx.draw_networkx_nodes(
            graph,
            positions,
            nodelist=other_nodes,
            node_size=18,
            node_color="#AFAFAF",
            alpha=0.6,
            linewidths=0.0,
            ax=ax,
        )

    if top_nodes:
        top_scores = np.array([score_map[node] for node in top_nodes], dtype=float)
        vmin, vmax = float(np.min(top_scores)), float(np.max(top_scores))
        if np.isclose(vmin, vmax):
            node_colors = ["#D95F0E" for _ in top_nodes]
            colorbar = False
        else:
            node_colors = top_scores
            colorbar = True

        collection = nx.draw_networkx_nodes(
            graph,
            positions,
            nodelist=top_nodes,
            node_size=82,
            node_color=node_colors,
            cmap="YlOrRd",
            edgecolors="#111111",
            linewidths=0.45,
            ax=ax,
        )

        if colorbar:
            cbar = fig.colorbar(collection, ax=ax, fraction=0.046, pad=0.02)
            cbar.set_label("Metric score")

        rank_labels = {node: str(idx + 1) for idx, node in enumerate(top_nodes)}
        nx.draw_networkx_labels(graph, positions, labels=rank_labels, font_size=8, font_color="black", ax=ax)

    label_lines = [f"Top {min(top_k, len(ranking))} nodes:"]
    label_lines.extend([f"{idx + 1}: {node}" for idx, (node, _) in enumerate(top)])
    ax.text(
        1.01,
        1.0,
        "\n".join(label_lines),
        transform=ax.transAxes,
        va="top",
        ha="left",
        fontsize=8,
        family="monospace",
    )

    ax.set_title(f"Top {min(top_k, len(ranking))} Nodes by {metric_name}")
    ax.axis("off")
    fig.tight_layout()
    fig.savefig(output_path, dpi=220, bbox_inches="tight")
    plt.close(fig)


def save_topk_node_highlight_plot(
    graph: nx.Graph,
    ranking: list[tuple[object, float]],
    metric_name: str,
    output_path: Path,
    top_k: int,
    coord_map: dict,
) -> None:
    """
    Plot top-k nodes on the same Germany map used in APEM network plots.

    Falls back to a spring-layout graph plot if coordinates are missing.
    """
    ranking = [(node, float(score)) for node, score in ranking]
    top = ranking[:top_k]
    top_nodes = [node for node, _ in top]
    top_set = set(top_nodes)
    score_map = dict(ranking)

    all_nodes = list(graph.nodes())
    if not all(node in coord_map for node in all_nodes):
        _save_topk_node_highlight_plot_fallback(
            graph=graph,
            ranking=ranking,
            metric_name=metric_name,
            output_path=output_path,
            top_k=top_k,
        )
        return

    nodes_df = gpd.GeoDataFrame(
        {
            "node": all_nodes,
            "longitude": [coord_map[node][0] for node in all_nodes],
            "latitude": [coord_map[node][1] for node in all_nodes],
        },
        geometry=[Point(coord_map[node][0], coord_map[node][1]) for node in all_nodes],
        crs="EPSG:4326",
    )

    edge_rows = []
    for u, v, _data in graph.edges(data=True):
        if u not in coord_map or v not in coord_map:
            continue
        edge_rows.append(
            {
                "from_node": u,
                "to_node": v,
                "geometry": LineString([Point(*coord_map[u]), Point(*coord_map[v])]),
            }
        )

    line_df = gpd.GeoDataFrame(edge_rows, geometry="geometry", crs="EPSG:4326")
    top_df = nodes_df[nodes_df["node"].isin(top_nodes)].copy()
    top_df["score"] = top_df["node"].map(score_map).astype(float)

    fig, ax = plt.subplots(figsize=(15, 15))
    map_germany = gpd.read_file(RAW_DATA_DIR / "gadm41_DEU_shp" / "gadm41_DEU_1.shp")
    map_germany.plot(ax=ax, color="lightgray", alpha=0.5)
    map_germany.boundary.plot(ax=ax, color="lightgray", linewidth=1.0)

    if not line_df.empty:
        line_df.plot(ax=ax, color="gray", linewidth=0.8, alpha=0.5)

    other_df = nodes_df[~nodes_df["node"].isin(top_set)]
    if not other_df.empty:
        other_df.plot(ax=ax, markersize=22, color="#AFAFAF", alpha=0.65)

    if not top_df.empty:
        vmin, vmax = float(top_df["score"].min()), float(top_df["score"].max())
        if np.isclose(vmin, vmax):
            top_df.plot(ax=ax, markersize=88, color="#D95F0E", edgecolor="black", linewidth=0.4)
        else:
            top_df.plot(
                ax=ax,
                markersize=88,
                column="score",
                cmap="YlOrRd",
                edgecolor="black",
                linewidth=0.4,
                legend=False,
            )
            sm = plt.cm.ScalarMappable(cmap="YlOrRd", norm=plt.Normalize(vmin=vmin, vmax=vmax))
            sm.set_array([])
            cbar = fig.colorbar(sm, ax=ax, fraction=0.046, pad=0.02)
            cbar.set_label("Metric score")

    ax.set_title(f"Top {min(top_k, len(ranking))} Nodes by {metric_name}")
    ax.axis("off")
    fig.tight_layout()
    fig.savefig(output_path, dpi=220, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    scenario = DATASET.value.parse_data()
    graph = scenario.network
    scenario_name = str(scenario.name) if getattr(scenario, "name", None) else _scenario_name()

    ptdf, edges, nodes, mask, slack_node = compute_ptdf(graph, slack=SLACK_NODE, b_attr="B")

    output_dir = _output_dir(scenario_name)

    # PTDF-based node rankings with multiple aggregation methods
    ptdf_rankings: dict[str, list[tuple[object, float]]] = {}
    plot_paths: dict[str, str] = {}
    coord_map = _extract_coord_map(graph, scenario.nodes_agents)

    for method in PTDF_METHODS:
        ranking = rank_nodes_by_ptdf(
            ptdf=ptdf,
            edges=edges,
            nodes=nodes,
            mask=mask,
            G=graph,
            method=method,
            fmax_attr="F_max",
        )
        ptdf_rankings[method] = ranking
        _ranking_to_df(ranking, "node").to_csv(output_dir / f"node_ranking_ptdf_{method}.csv", index=False)
        metric_name = f"ptdf_{method}"
        plot_path = output_dir / f"top_nodes_{_safe_metric_name(metric_name)}.png"
        save_topk_node_highlight_plot(
            graph=graph,
            ranking=ranking,
            metric_name=metric_name,
            output_path=plot_path,
            top_k=TOP_K_PLOT,
            coord_map=coord_map,
        )
        plot_paths[metric_name] = str(plot_path)

    # Graph-based node rankings
    degree_ranking = rank_nodes_by_degree(graph)
    betweenness_ranking = rank_nodes_by_betweenness(graph)
    _ranking_to_df(degree_ranking, "node").to_csv(output_dir / "node_ranking_degree.csv", index=False)
    _ranking_to_df(betweenness_ranking, "node").to_csv(output_dir / "node_ranking_betweenness.csv", index=False)
    degree_plot = output_dir / f"top_nodes_{_safe_metric_name('degree')}.png"
    betweenness_plot = output_dir / f"top_nodes_{_safe_metric_name('betweenness')}.png"
    save_topk_node_highlight_plot(
        graph=graph,
        ranking=degree_ranking,
        metric_name="degree",
        output_path=degree_plot,
        top_k=TOP_K_PLOT,
        coord_map=coord_map,
    )
    save_topk_node_highlight_plot(
        graph=graph,
        ranking=betweenness_ranking,
        metric_name="betweenness",
        output_path=betweenness_plot,
        top_k=TOP_K_PLOT,
        coord_map=coord_map,
    )
    plot_paths["degree"] = str(degree_plot)
    plot_paths["betweenness"] = str(betweenness_plot)

    metadata = {
        "scenario": scenario_name,
        "slack_node": slack_node,
        "num_nodes": len(nodes),
        "num_lines": len(edges),
        "ptdf_shape": list(ptdf.shape),
        "ptdf_methods": list(PTDF_METHODS),
        "top_k_plot": TOP_K_PLOT,
        "plots": plot_paths,
        "output_dir": str(output_dir),
    }
    with open(output_dir / "metadata.json", "w", encoding="utf-8") as handle:
        json.dump(metadata, handle, indent=2)

    print(f"Scenario: {scenario_name}")
    print(f"Slack node: {slack_node}")
    print(f"Output dir: {output_dir}")

    for method in PTDF_METHODS:
        print(f"\nTop {TOP_K_PRINT} nodes by PTDF ({method}):")
        for node, score in ptdf_rankings[method][:TOP_K_PRINT]:
            print(node, score)

    print(f"\nTop {TOP_K_PRINT} nodes by degree centrality:")
    for node, score in degree_ranking[:TOP_K_PRINT]:
        print(node, score)

    print(f"\nTop {TOP_K_PRINT} nodes by betweenness centrality:")
    for node, score in betweenness_ranking[:TOP_K_PRINT]:
        print(node, score)

if __name__ == "__main__":
    main()
