"""
Example script for running all market-metric-based node rankings.

The script:
1. solves a baseline economic dispatch (no interdicted nodes),
2. computes PTDF inputs for PTDF-stress ranking,
3. runs every market-metric ranking method from `node_ranking.rank_nodes`,
4. prints top-k nodes per metric,
5. saves ranking CSVs, top-k node plots, and metadata to a timestamped folder.

You can adapt the run by editing the constants near the top of the file:
- `DATASET`: unit-based dataset used for dispatch and network parsing.
- `PERIOD`: period to evaluate (`None` means period-averaged inputs).
- `VOLL`: value of lost load used in dispatch and load-weighted LMP scoring.
- `SLACK_NODE`: slack node for PTDF (`None` means first graph node in PTDF order).
- `TOP_K_PRINT`: number of top nodes printed per ranking.
- `TOP_K_PLOT`: number of top-ranked nodes highlighted in each saved plot.
"""

from __future__ import annotations

from collections import defaultdict, deque
import csv
from datetime import datetime, timezone
import json
import os
import re
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if "MPLCONFIGDIR" not in os.environ:
    os.environ["MPLCONFIGDIR"] = str(ROOT / ".matplotlib_cache")

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import geopandas as gpd
import networkx as nx
from shapely.geometry import LineString, Point

# Ensure repo root is on sys.path when run directly
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from apem.unit_based_model.enums import UnitBased_Datasets
from apem.unit_based_model.utils.paths import RAW_DATA_DIR
from node_ranking.economic_dispatch import (
    build_dispatch_inputs,
    solve_economic_dispatch,
)
from node_ranking.market_scores import compute_ptdf
from node_ranking.rank_nodes import (
    rank_nodes_by_dispatch_volume,
    rank_nodes_by_gamma_capacity_congestion_score,
    rank_nodes_by_gamma_capacity_score,
    rank_nodes_by_ptdf_stress_score,
    rank_nodes_by_scarcity_score,
    rank_nodes_by_shadow_score,
)

DATASET = UnitBased_Datasets.PyPSAEurSmall
PERIOD = None
VOLL = 500.0
SLACK_NODE = None
TOP_K_PRINT = 10
TOP_K_PLOT = 10


def _create_output_dir(scenario_name: str) -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_dir = (
        ROOT
        / "results"
        / "unit_based_model"
        / f"{scenario_name}_results"
        / "evaluation"
        / "market_metric_rankings"
        / timestamp
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def _save_ranking_csv(path: Path, ranking: list[tuple[object, float]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["rank", "node", "score"])
        for idx, (node, score) in enumerate(ranking, start=1):
            writer.writerow([idx, node, float(score)])


def _print_top_k(metric_name: str, ranking: list[tuple[object, float]], top_k: int) -> None:
    print(f"\n{metric_name} (top {min(top_k, len(ranking))}):")
    for idx, (node, score) in enumerate(ranking[:top_k], start=1):
        print(f"  {idx:2d}. node={node} score={float(score):.6f}")


def _safe_metric_name(metric_name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_]+", "_", metric_name.strip()).strip("_").lower()


def _build_line_ids_in_ptdf_order(
    edges: list[tuple[object, object, dict]],
    lines: dict[str, dict[str, float | tuple[str, str]]],
) -> list[str | None]:
    line_ids_by_pair: dict[tuple[str, str], deque[str]] = defaultdict(deque)
    for line_id, line_data in lines.items():
        u, v = line_data["ends"]
        pair = tuple(sorted((str(u), str(v))))
        line_ids_by_pair[pair].append(line_id)

    line_ids: list[str | None] = []
    for u, v, _ in edges:
        pair = tuple(sorted((str(u), str(v))))
        if line_ids_by_pair[pair]:
            line_ids.append(line_ids_by_pair[pair].popleft())
        else:
            line_ids.append(None)
    return line_ids


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
                coord = (float(lon), float(lat))
                coord_map[node] = coord
                coord_map[str(node)] = coord
    return coord_map


def _normalize_ranking_nodes(
    graph: nx.Graph,
    ranking: list[tuple[object, float]],
) -> list[tuple[object, float]]:
    node_by_str = {str(node): node for node in graph.nodes()}
    normalized: list[tuple[object, float]] = []
    for node, score in ranking:
        if node in node_by_str.values():
            normalized.append((node, float(score)))
            continue
        mapped = node_by_str.get(str(node))
        if mapped is not None:
            normalized.append((mapped, float(score)))
    return normalized


def _save_topk_node_highlight_plot_fallback(
    graph: nx.Graph,
    ranking: list[tuple[object, float]],
    metric_name: str,
    output_path: Path,
    top_k: int,
) -> None:
    positions = nx.spring_layout(graph, seed=42)
    ranking = _normalize_ranking_nodes(graph, ranking)
    top_nodes = [node for node, _ in ranking[:top_k]]
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

    ax.set_title(f"Top {min(top_k, len(ranking))} Nodes by {metric_name}")
    ax.axis("off")
    fig.tight_layout()
    fig.savefig(output_path, dpi=220, bbox_inches="tight")
    plt.close(fig)


def _save_topk_node_highlight_plot(
    graph: nx.Graph,
    ranking: list[tuple[object, float]],
    metric_name: str,
    output_path: Path,
    top_k: int,
    coord_map: dict,
) -> None:
    ranking = _normalize_ranking_nodes(graph, ranking)
    top = ranking[:top_k]
    top_nodes = [node for node, _ in top]
    top_set = set(top_nodes)
    score_map = dict(ranking)

    all_nodes = list(graph.nodes())
    if not all(node in coord_map or str(node) in coord_map for node in all_nodes):
        _save_topk_node_highlight_plot_fallback(
            graph=graph,
            ranking=ranking,
            metric_name=metric_name,
            output_path=output_path,
            top_k=top_k,
        )
        return

    node_coords = {}
    for node in all_nodes:
        if node in coord_map:
            node_coords[node] = coord_map[node]
        else:
            node_coords[node] = coord_map[str(node)]

    nodes_df = gpd.GeoDataFrame(
        {
            "node": all_nodes,
            "longitude": [node_coords[node][0] for node in all_nodes],
            "latitude": [node_coords[node][1] for node in all_nodes],
        },
        geometry=[Point(node_coords[node][0], node_coords[node][1]) for node in all_nodes],
        crs="EPSG:4326",
    )

    edge_rows = []
    for u, v, _data in graph.edges(data=True):
        if u not in node_coords or v not in node_coords:
            continue
        edge_rows.append(
            {
                "from_node": u,
                "to_node": v,
                "geometry": LineString([Point(*node_coords[u]), Point(*node_coords[v])]),
            }
        )

    line_df = gpd.GeoDataFrame(edge_rows, geometry="geometry", crs="EPSG:4326")
    top_df = nodes_df[nodes_df["node"].isin(top_set)].copy()
    top_df["score"] = top_df["node"].map(score_map).astype(float)

    fig, ax = plt.subplots(figsize=(15, 15))
    try:
        map_germany = gpd.read_file(RAW_DATA_DIR / "gadm41_DEU_shp" / "gadm41_DEU_1.shp")
        map_germany.plot(ax=ax, color="lightgray", alpha=0.5)
        map_germany.boundary.plot(ax=ax, color="lightgray", linewidth=1.0)
    except Exception:
        pass

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
    nodes, generators, lines = build_dispatch_inputs(DATASET, period=PERIOD)
    baseline_result = solve_economic_dispatch(
        dataset=DATASET,
        fail_nodes=[],
        period=PERIOD,
        VOLL=VOLL,
    )
    if baseline_result is None:
        raise RuntimeError("Economic dispatch solve failed.")

    scenario = DATASET.value.parse_data()
    scenario_name = str(scenario.name) if getattr(scenario, "name", None) else DATASET.name
    graph = scenario.network
    coord_map = _extract_coord_map(graph, getattr(scenario, "nodes_agents", {}))

    ptdf, edges, ptdf_nodes, mask, slack_node = compute_ptdf(graph, slack=SLACK_NODE, b_attr="B")
    line_ids_in_ptdf_order = _build_line_ids_in_ptdf_order(
        edges=edges,
        lines=lines,
    )
    line_margins: list[float] = []
    for line_id in line_ids_in_ptdf_order:
        if line_id is None:
            line_margins.append(0.0)
            continue
        flow = float(baseline_result["flows"][line_id])
        capacity = float(lines[line_id]["capacity"])
        margin = max(0.0, capacity - abs(flow))
        line_margins.append(margin)
    line_margins_arr = np.asarray(line_margins, dtype=float)

    rankings: dict[str, list[tuple[object, float]]] = {
        "rent_weighted_dispatch_score": rank_nodes_by_shadow_score(
            nodes=nodes,
            generators=generators,
            baseline_result=baseline_result,
        ),
        "dispatch_volume_score": rank_nodes_by_dispatch_volume(
            nodes=nodes,
            generators=generators,
            baseline_result=baseline_result,
        ),
        "gamma_capacity_score": rank_nodes_by_gamma_capacity_score(
            nodes=nodes,
            generators=generators,
            baseline_result=baseline_result,
        ),
        "load_weighted_lmp_score": rank_nodes_by_scarcity_score(
            nodes=nodes,
            baseline_result=baseline_result,
            VOLL=VOLL,
            cap_lambda=True,
        ),
        "gamma_capacity_congestion_score": rank_nodes_by_gamma_capacity_congestion_score(
            nodes=nodes,
            generators=generators,
            lines=lines,
            baseline_result=baseline_result,
        ),
        "ptdf_stress_score": rank_nodes_by_ptdf_stress_score(
            ptdf=ptdf,
            nodes=ptdf_nodes,
            mask=mask,
            generators=generators,
            line_margins=line_margins_arr,
            epsilon=1e-6,
        ),
    }

    output_dir = _create_output_dir(scenario_name)
    plot_paths: dict[str, str] = {}

    for metric_name, ranking in rankings.items():
        _print_top_k(metric_name, ranking, TOP_K_PRINT)
        _save_ranking_csv(output_dir / f"{metric_name}.csv", ranking)
        plot_path = output_dir / f"top_nodes_{_safe_metric_name(metric_name)}.png"
        _save_topk_node_highlight_plot(
            graph=graph,
            ranking=ranking,
            metric_name=metric_name,
            output_path=plot_path,
            top_k=TOP_K_PLOT,
            coord_map=coord_map,
        )
        plot_paths[metric_name] = str(plot_path)

    metadata = {
        "dataset": DATASET.name,
        "scenario_name": scenario_name,
        "period": PERIOD,
        "voll": VOLL,
        "slack_node": str(slack_node),
        "top_k_print": TOP_K_PRINT,
        "top_k_plot": TOP_K_PLOT,
        "baseline_cost": float(baseline_result["cost"]),
        "baseline_shed_total": float(baseline_result["shed_total"]),
        "num_nodes": len(nodes),
        "num_generators": len(generators),
        "num_lines": len(lines),
        "ranking_files": {name: f"{name}.csv" for name in rankings},
        "plot_files": plot_paths,
    }
    with (output_dir / "metadata.json").open("w", encoding="utf-8") as handle:
        json.dump(metadata, handle, indent=2)

    print(f"\nSaved ranking outputs to: {output_dir}")


if __name__ == "__main__":
    main()
