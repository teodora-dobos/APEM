"""
Example script for comparing Euphemia cut types on one order-book-based dataset.

The script:
1. runs one order-book-based dataset for the selected cut types, or reuses the latest matching run if enabled,
2. extracts run metadata, final welfare/runtime metrics, diagnostic counts, and final MCP prices,
3. writes summary tables and pairwise price-difference reports to a timestamped evaluation folder.

Edit the constants near the top to choose:
- `DATASET`
- `NETWORK_MODEL`
- `CUT_TYPES`
- `CONFIG_OVERRIDES`
- `REUSE_EXISTING_RUNS`

Each execution writes a new timestamped evaluation folder under:
`results/order_book_based_model/euphemia/<DATASET>/evaluation/cut_type_comparison/`

Notes:
- `REUSE_EXISTING_RUNS` is disabled by default because `run.json` does not persist every Euphemia
  override, so recomputing is the safer apples-to-apples comparison.
- Final prices are parsed from `evaluation/evaluation.txt`, because `prices/prices.csv` stores price
  variables for every feasible pricing subproblem encountered during the run.
"""

from __future__ import annotations

import ast
from datetime import datetime, timezone
import itertools
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

if "MPLCONFIGDIR" not in os.environ:
    os.environ["MPLCONFIGDIR"] = str(ROOT / ".matplotlib_cache")

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from apem.order_book_based_model.euphemia.enums.cut_types import CutTypes
from apem.order_book_based_model.euphemia.enums.datasets import OrderBookBased_Datasets
from apem.order_book_based_model.euphemia.runner import solve_euphemia

DATASET = OrderBookBased_Datasets.TEST_3NODE
NETWORK_MODEL = "FBMC"
CUT_TYPES = (CutTypes.PB, CutTypes.CB, CutTypes.NG)
CONFIG_OVERRIDES = {
    "network_model": NETWORK_MODEL,
    "disable_reinsertion": True,
    "calculate_corrected_welfare": True,
}
REUSE_EXISTING_RUNS = True

PRICE_PATTERN = re.compile(r"^MCP\[(?P<zone>.+?),(?P<period>\d+)\]$")


def order_book_based_results_root(dataset: OrderBookBased_Datasets) -> Path:
    """Return the canonical order-book-based results root for one dataset."""
    return ROOT / "results" / "order_book_based_model" / "euphemia" / dataset.name


def evaluation_root(dataset: OrderBookBased_Datasets) -> Path:
    """Return the folder used for cut-type comparison outputs."""
    return order_book_based_results_root(dataset) / "evaluation" / "cut_type_comparison"


def create_output_dir(dataset: OrderBookBased_Datasets, network_model: str) -> Path:
    """Create a timestamped evaluation folder so comparisons are not overwritten."""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_dir = evaluation_root(dataset) / f"{timestamp}_{network_model.lower()}"
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def load_json(path: Path) -> dict[str, Any]:
    """Read a JSON file."""
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def count_txt_files(folder: Path) -> int:
    """Count plain-text diagnostic files inside one folder."""
    if not folder.exists():
        return 0
    return sum(1 for candidate in folder.glob("*.txt") if candidate.is_file())


def parse_float(value: str | None) -> float | None:
    """Convert a text token to float when possible."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_int(value: str | None) -> int | None:
    """Convert a text token to int when possible."""
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def parse_evaluation_metrics(run_dir: Path) -> dict[str, Any]:
    """Parse the human-readable evaluation file emitted by the Euphemia run."""
    evaluation_path = run_dir / "evaluation" / "evaluation.txt"
    metrics: dict[str, Any] = {
        "iterations_from_evaluation": None,
        "final_welfare_from_evaluation": None,
        "corrected_welfare": None,
        "time_passed_seconds": None,
        "final_prices_dict": None,
        "no_solution_iteration_limit": None,
    }
    if not evaluation_path.exists():
        return metrics

    for raw_line in evaluation_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line.startswith("Iterations:"):
            metrics["iterations_from_evaluation"] = parse_int(line.split(":", maxsplit=1)[1].strip())
        elif line.startswith("Final welfare:"):
            metrics["final_welfare_from_evaluation"] = parse_float(line.split(":", maxsplit=1)[1].strip())
        elif line.startswith("Corrected welfare:"):
            metrics["corrected_welfare"] = parse_float(line.split(":", maxsplit=1)[1].strip())
        elif line.startswith("Time passed:"):
            seconds_text = line.split(":", maxsplit=1)[1].replace("seconds", "").strip()
            metrics["time_passed_seconds"] = parse_float(seconds_text)
        elif line.startswith("Clearing prices "):
            prices_literal = line.split("Clearing prices ", maxsplit=1)[1].strip()
            try:
                metrics["final_prices_dict"] = ast.literal_eval(prices_literal)
            except (SyntaxError, ValueError):
                metrics["final_prices_dict"] = None
        elif line.startswith("No solution in iteration limit of "):
            limit_text = line.rsplit(" ", maxsplit=1)[1]
            metrics["no_solution_iteration_limit"] = parse_int(limit_text)

    return metrics


def build_final_price_table(
    cut_type: CutTypes,
    evaluation_metrics: dict[str, Any],
) -> pd.DataFrame:
    """Normalize final MCP prices from the evaluation file into a long-form table."""
    prices = evaluation_metrics.get("final_prices_dict")
    if not isinstance(prices, dict) or not prices:
        return pd.DataFrame(columns=["cut_type", "cut_type_label", "zone", "period", "price"])

    rows = []
    for raw_key, raw_value in prices.items():
        if isinstance(raw_key, tuple) and len(raw_key) == 2:
            zone, period = raw_key
        else:
            zone, period = "SYSTEM", raw_key

        rows.append(
            {
                "cut_type": cut_type.name,
                "cut_type_label": cut_type.value,
                "zone": str(zone),
                "period": int(period),
                "price": float(raw_value),
            }
        )

    return pd.DataFrame(rows).sort_values(["zone", "period"]).reset_index(drop=True)


def count_price_rows(run_dir: Path) -> tuple[int, int]:
    """Return the total number of stored price rows and MCP rows in prices.csv."""
    prices_path = run_dir / "prices" / "prices.csv"
    if not prices_path.exists():
        return 0, 0

    prices = pd.read_csv(prices_path)
    if "variable" not in prices.columns:
        return len(prices), 0

    is_mcp = prices["variable"].astype(str).str.match(PRICE_PATTERN)
    return len(prices), int(is_mcp.sum())


def latest_matching_run(
    dataset: OrderBookBased_Datasets,
    cut_type: CutTypes,
    network_model: str,
) -> Path | None:
    """Find the latest successful run for one dataset/cut-type/network-model tuple."""
    dataset_root = order_book_based_results_root(dataset)
    if not dataset_root.exists():
        return None

    candidates: list[tuple[str, float, Path]] = []
    for run_json_path in dataset_root.glob("*/*/run.json"):
        metadata = load_json(run_json_path)
        if metadata.get("dataset") != dataset.name:
            continue
        if metadata.get("cut_type") != cut_type.value:
            continue
        if str(metadata.get("network_model", "")).upper() != network_model.upper():
            continue
        if metadata.get("reinsertion_run"):
            continue
        if metadata.get("status") != "success":
            continue

        created_at = str(metadata.get("created_at_utc", ""))
        run_dir = run_json_path.parent
        candidates.append((created_at, run_dir.stat().st_mtime, run_dir))

    if not candidates:
        return None

    candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return candidates[0][2]


def ensure_run_for_cut_type(
    dataset: OrderBookBased_Datasets,
    cut_type: CutTypes,
    config_overrides: dict[str, Any],
) -> tuple[Path, str]:
    """Reuse or compute a cut-type run."""
    network_model = str(config_overrides.get("network_model", "ATC")).upper()
    if REUSE_EXISTING_RUNS:
        existing_run = latest_matching_run(dataset, cut_type, network_model)
        if existing_run is not None:
            return existing_run, "reused"

    run_dir = Path(solve_euphemia(dataset, cut_type, config_overrides))
    return run_dir, "computed"


def summarize_run(
    dataset: OrderBookBased_Datasets,
    cut_type: CutTypes,
    source: str,
    run_dir: Path,
    metadata: dict[str, Any],
    evaluation_metrics: dict[str, Any],
    final_prices: pd.DataFrame,
) -> dict[str, Any]:
    """Assemble one summary row for the cut-type comparison table."""
    total_price_rows, total_mcp_rows = count_price_rows(run_dir)
    return {
        "dataset": dataset.name,
        "scenario_name": metadata.get("scenario_name"),
        "cut_type": cut_type.name,
        "cut_type_label": cut_type.value,
        "source": source,
        "status": metadata.get("status"),
        "network_model": metadata.get("network_model"),
        "found_solution": metadata.get("found_solution"),
        "iteration": metadata.get("iteration"),
        "iterations_from_evaluation": evaluation_metrics.get("iterations_from_evaluation"),
        "best_objective": metadata.get("best_objective"),
        "final_welfare_from_evaluation": evaluation_metrics.get("final_welfare_from_evaluation"),
        "corrected_welfare": evaluation_metrics.get("corrected_welfare"),
        "elapsed_seconds": metadata.get("elapsed_seconds"),
        "time_passed_seconds": evaluation_metrics.get("time_passed_seconds"),
        "model_status": metadata.get("model_status"),
        "run_id": metadata.get("run_id"),
        "created_at_utc": metadata.get("created_at_utc"),
        "ended_at_utc": metadata.get("ended_at_utc"),
        "final_price_count": len(final_prices),
        "final_price_min": final_prices["price"].min() if not final_prices.empty else None,
        "final_price_mean": final_prices["price"].mean() if not final_prices.empty else None,
        "final_price_max": final_prices["price"].max() if not final_prices.empty else None,
        "stored_price_row_count": total_price_rows,
        "stored_mcp_row_count": total_mcp_rows,
        "pab_file_count": count_txt_files(run_dir / "pab"),
        "block_inm_threshold_file_count": count_txt_files(run_dir / "block_inm_threshold"),
        "complex_mic_file_count": count_txt_files(run_dir / "complex_mic"),
        "complex_mic_inm_threshold_file_count": count_txt_files(run_dir / "complex_mic_inm_threshold"),
        "scalable_mic_file_count": count_txt_files(run_dir / "scalable_mic"),
        "scalable_mic_inm_threshold_file_count": count_txt_files(run_dir / "scalable_mic_inm_threshold"),
        "run_dir": str(run_dir),
    }


def pivot_prices_by_zone_period(prices: pd.DataFrame, cut_types: tuple[CutTypes, ...]) -> pd.DataFrame:
    """Reshape final prices to one row per zone and period."""
    if prices.empty:
        return pd.DataFrame(columns=["zone", "period"] + [cut_type.name for cut_type in cut_types])

    pivoted = (
        prices.pivot(index=["zone", "period"], columns="cut_type", values="price")
        .reset_index()
        .rename_axis(columns=None)
        .sort_values(["zone", "period"])
        .reset_index(drop=True)
    )
    ordered_columns = ["zone", "period"] + [cut_type.name for cut_type in cut_types if cut_type.name in pivoted.columns]
    return pivoted.loc[:, ordered_columns]


def compare_final_prices(
    prices: pd.DataFrame,
    cut_types: tuple[CutTypes, ...],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Build detailed and summary pairwise price-difference tables."""
    if prices.empty:
        empty_detail = pd.DataFrame(
            columns=["zone", "period", "cut_type_left", "cut_type_right", "price_left", "price_right", "price_diff"]
        )
        empty_summary = pd.DataFrame(
            columns=[
                "cut_type_left",
                "cut_type_right",
                "overlap_count",
                "mean_abs_price_diff",
                "max_abs_price_diff",
                "identical_within_1e-6",
            ]
        )
        return empty_detail, empty_summary

    detailed_frames = []
    summary_rows = []
    ordered_cut_types = [cut_type.name for cut_type in cut_types]

    for left_name, right_name in itertools.combinations(ordered_cut_types, 2):
        left_prices = prices.loc[prices["cut_type"] == left_name, ["zone", "period", "price"]].rename(
            columns={"price": "price_left"}
        )
        right_prices = prices.loc[prices["cut_type"] == right_name, ["zone", "period", "price"]].rename(
            columns={"price": "price_right"}
        )
        merged = left_prices.merge(right_prices, on=["zone", "period"], how="inner")
        if merged.empty:
            summary_rows.append(
                {
                    "cut_type_left": left_name,
                    "cut_type_right": right_name,
                    "overlap_count": 0,
                    "mean_abs_price_diff": None,
                    "max_abs_price_diff": None,
                    "identical_within_1e-6": False,
                }
            )
            continue

        merged["cut_type_left"] = left_name
        merged["cut_type_right"] = right_name
        merged["price_diff"] = merged["price_right"] - merged["price_left"]
        merged["abs_price_diff"] = merged["price_diff"].abs()
        detailed_frames.append(
            merged[["zone", "period", "cut_type_left", "cut_type_right", "price_left", "price_right", "price_diff"]]
        )
        summary_rows.append(
            {
                "cut_type_left": left_name,
                "cut_type_right": right_name,
                "overlap_count": len(merged),
                "mean_abs_price_diff": merged["abs_price_diff"].mean(),
                "max_abs_price_diff": merged["abs_price_diff"].max(),
                "identical_within_1e-6": bool((merged["abs_price_diff"] <= 1e-6).all()),
            }
        )

    detailed = (
        pd.concat(detailed_frames, ignore_index=True)
        if detailed_frames
        else pd.DataFrame(
            columns=["zone", "period", "cut_type_left", "cut_type_right", "price_left", "price_right", "price_diff"]
        )
    )
    summary = pd.DataFrame(summary_rows)
    return detailed, summary


def round_numeric_columns(dataframe: pd.DataFrame, digits: int = 6) -> pd.DataFrame:
    """Round numeric columns for stable CSV output."""
    if dataframe.empty:
        return dataframe
    rounded = dataframe.copy()
    numeric_columns = rounded.select_dtypes(include=["number"]).columns
    rounded.loc[:, numeric_columns] = rounded.loc[:, numeric_columns].round(digits)
    return rounded


def sanitize_filename(token: str) -> str:
    """Convert a label to a stable lowercase filename token."""
    return re.sub(r"[^a-z0-9]+", "_", token.lower()).strip("_")


def create_plots_dir(output_dir: Path) -> Path:
    """Create the plot output directory."""
    plots_dir = output_dir / "plots"
    plots_dir.mkdir(parents=True, exist_ok=True)
    return plots_dir


def save_metric_bar_chart(
    summary: pd.DataFrame,
    metric: str,
    output_file: Path,
    *,
    title: str,
    ylabel: str,
) -> bool:
    """Save a simple cut-type bar chart for one numeric metric."""
    if summary.empty or metric not in summary.columns:
        return False

    chart = summary.loc[summary[metric].notna(), ["cut_type", metric]].copy()
    if chart.empty:
        return False

    labels = chart["cut_type"].astype(str).tolist()
    values = chart[metric].astype(float).tolist()
    x_positions = np.arange(len(labels))

    plt.figure(figsize=(8, 5))
    bars = plt.bar(x_positions, values, color=["#1f77b4", "#ff7f0e", "#2ca02c"][: len(labels)])
    plt.xticks(x_positions, labels)
    plt.ylabel(ylabel)
    plt.title(title)
    plt.grid(axis="y", alpha=0.3)

    for bar, value in zip(bars, values):
        plt.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height(),
            f"{value:.3f}",
            ha="center",
            va="bottom",
            fontsize=9,
        )

    plt.tight_layout()
    plt.savefig(output_file, dpi=200)
    plt.close()
    return True


def save_diagnostic_count_chart(summary: pd.DataFrame, output_file: Path) -> bool:
    """Save a grouped bar chart for diagnostic artifact counts."""
    diagnostic_columns = [
        "pab_file_count",
        "block_inm_threshold_file_count",
        "complex_mic_file_count",
        "complex_mic_inm_threshold_file_count",
        "scalable_mic_file_count",
        "scalable_mic_inm_threshold_file_count",
    ]
    available_columns = [column for column in diagnostic_columns if column in summary.columns]
    if summary.empty or not available_columns:
        return False

    chart = summary.loc[:, ["cut_type"] + available_columns].copy()
    chart = chart.fillna(0.0)
    if chart.empty:
        return False

    labels = chart["cut_type"].astype(str).tolist()
    x_positions = np.arange(len(labels))
    width = 0.12 if available_columns else 0.8

    plt.figure(figsize=(11, 6))
    for index, column in enumerate(available_columns):
        offsets = x_positions + (index - (len(available_columns) - 1) / 2) * width
        plt.bar(offsets, chart[column].astype(float).to_numpy(), width=width, label=column.replace("_file_count", ""))

    plt.xticks(x_positions, labels)
    plt.ylabel("Diagnostic File Count")
    plt.title("Diagnostic Artifact Counts by Cut Type")
    plt.grid(axis="y", alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.savefig(output_file, dpi=200)
    plt.close()
    return True


def save_heatmap(
    matrix: pd.DataFrame,
    output_file: Path,
    *,
    title: str,
    colorbar_label: str,
    cmap: str,
) -> bool:
    """Save a zone-period heatmap from a pivoted dataframe."""
    if matrix.empty:
        return False

    numeric = matrix.sort_index().sort_index(axis=1)
    if numeric.empty:
        return False

    values = numeric.to_numpy(dtype=float)
    plt.figure(figsize=(max(6, 0.7 * numeric.shape[1] + 2), max(4, 0.45 * numeric.shape[0] + 2)))
    image = plt.imshow(values, aspect="auto", cmap=cmap)
    plt.colorbar(image, label=colorbar_label)
    plt.xticks(np.arange(numeric.shape[1]), [str(column) for column in numeric.columns], rotation=45, ha="right")
    plt.yticks(np.arange(numeric.shape[0]), [str(index) for index in numeric.index])
    plt.xlabel("Period")
    plt.ylabel("Zone")
    plt.title(title)
    plt.tight_layout()
    plt.savefig(output_file, dpi=200)
    plt.close()
    return True


def save_final_price_heatmaps(
    final_prices: pd.DataFrame,
    cut_types: tuple[CutTypes, ...],
    plots_dir: Path,
) -> list[str]:
    """Save one final-MCP heatmap per cut type."""
    output_files: list[str] = []
    if final_prices.empty:
        return output_files

    for cut_type in cut_types:
        subset = final_prices.loc[final_prices["cut_type"] == cut_type.name, ["zone", "period", "price"]]
        if subset.empty:
            continue

        heatmap = subset.pivot(index="zone", columns="period", values="price")
        output_file = plots_dir / f"final_price_heatmap_{sanitize_filename(cut_type.name)}.png"
        created = save_heatmap(
            heatmap,
            output_file,
            title=f"Final MCP Heatmap: {cut_type.name}",
            colorbar_label="Price",
            cmap="viridis",
        )
        if created:
            output_files.append(str(output_file))

    return output_files


def save_pairwise_price_difference_heatmaps(pairwise_detail: pd.DataFrame, plots_dir: Path) -> list[str]:
    """Save one zone-period heatmap per pairwise cut-type price comparison."""
    output_files: list[str] = []
    if pairwise_detail.empty:
        return output_files

    grouped = pairwise_detail.groupby(["cut_type_left", "cut_type_right"], dropna=False)
    for (left_name, right_name), frame in grouped:
        heatmap = frame.pivot(index="zone", columns="period", values="price_diff")
        output_file = plots_dir / (
            f"price_diff_heatmap_{sanitize_filename(left_name)}_vs_{sanitize_filename(right_name)}.png"
        )
        created = save_heatmap(
            heatmap,
            output_file,
            title=f"Final MCP Difference Heatmap: {right_name} - {left_name}",
            colorbar_label="Price Difference",
            cmap="coolwarm",
        )
        if created:
            output_files.append(str(output_file))

    return output_files


def generate_plots(
    summary: pd.DataFrame,
    final_prices: pd.DataFrame,
    cut_types: tuple[CutTypes, ...],
    output_dir: Path,
) -> dict[str, Any]:
    """Generate all available comparison plots and return their paths."""
    plots_dir = create_plots_dir(output_dir)
    plot_paths: dict[str, Any] = {}

    runtime_plot = plots_dir / "runtime_by_cut_type.png"
    if save_metric_bar_chart(
        summary,
        "elapsed_seconds",
        runtime_plot,
        title="Runtime by Cut Type",
        ylabel="Elapsed Seconds",
    ):
        plot_paths["runtime_by_cut_type"] = str(runtime_plot)

    iterations_plot = plots_dir / "iterations_by_cut_type.png"
    if save_metric_bar_chart(
        summary,
        "iteration",
        iterations_plot,
        title="Iterations by Cut Type",
        ylabel="Iterations",
    ):
        plot_paths["iterations_by_cut_type"] = str(iterations_plot)

    welfare_plot = plots_dir / "welfare_by_cut_type.png"
    welfare_metric = "corrected_welfare" if "corrected_welfare" in summary.columns and summary["corrected_welfare"].notna().any() else "best_objective"
    if save_metric_bar_chart(
        summary,
        welfare_metric,
        welfare_plot,
        title=f"{welfare_metric.replace('_', ' ').title()} by Cut Type",
        ylabel=welfare_metric.replace("_", " ").title(),
    ):
        plot_paths["welfare_by_cut_type"] = str(welfare_plot)

    final_heatmaps = save_final_price_heatmaps(final_prices, cut_types, plots_dir)
    if final_heatmaps:
        plot_paths["final_price_heatmaps"] = final_heatmaps

    return plot_paths


def main() -> None:
    """Run the selected cut-type comparison and write evaluation artifacts."""
    output_dir = create_output_dir(DATASET, NETWORK_MODEL)
    summary_rows = []
    price_tables = []
    selected_runs: dict[str, dict[str, Any]] = {}

    for index, cut_type in enumerate(CUT_TYPES, start=1):
        print(f"[{index}/{len(CUT_TYPES)}] Running cut type {cut_type.name} ({cut_type.value})...")
        try:
            run_dir, source = ensure_run_for_cut_type(DATASET, cut_type, dict(CONFIG_OVERRIDES))
            metadata = load_json(run_dir / "run.json")
            evaluation_metrics = parse_evaluation_metrics(run_dir)
            final_prices = build_final_price_table(cut_type, evaluation_metrics)

            summary_rows.append(
                summarize_run(
                    DATASET,
                    cut_type,
                    source,
                    run_dir,
                    metadata,
                    evaluation_metrics,
                    final_prices,
                )
            )
            if not final_prices.empty:
                price_tables.append(final_prices)

            selected_runs[cut_type.name] = {
                "source": source,
                "run_dir": str(run_dir),
                "run_id": metadata.get("run_id"),
                "status": metadata.get("status"),
                "found_solution": metadata.get("found_solution"),
                "error": None,
            }
        except Exception as exc:  # noqa: BLE001
            summary_rows.append(
                {
                    "dataset": DATASET.name,
                    "scenario_name": DATASET.value.title,
                    "cut_type": cut_type.name,
                    "cut_type_label": cut_type.value,
                    "source": "computed",
                    "status": "failed",
                    "network_model": str(CONFIG_OVERRIDES.get("network_model", NETWORK_MODEL)).upper(),
                    "found_solution": False,
                    "iteration": None,
                    "iterations_from_evaluation": None,
                    "best_objective": None,
                    "final_welfare_from_evaluation": None,
                    "corrected_welfare": None,
                    "elapsed_seconds": None,
                    "time_passed_seconds": None,
                    "model_status": None,
                    "run_id": None,
                    "created_at_utc": None,
                    "ended_at_utc": None,
                    "final_price_count": 0,
                    "final_price_min": None,
                    "final_price_mean": None,
                    "final_price_max": None,
                    "stored_price_row_count": 0,
                    "stored_mcp_row_count": 0,
                    "pab_file_count": 0,
                    "block_inm_threshold_file_count": 0,
                    "complex_mic_file_count": 0,
                    "complex_mic_inm_threshold_file_count": 0,
                    "scalable_mic_file_count": 0,
                    "scalable_mic_inm_threshold_file_count": 0,
                    "run_dir": None,
                    "error": str(exc),
                }
            )
            selected_runs[cut_type.name] = {
                "source": "computed",
                "run_dir": None,
                "run_id": None,
                "status": "failed",
                "found_solution": False,
                "error": str(exc),
            }
            print(f"Failed: {cut_type.name} | {exc}")

    summary = round_numeric_columns(pd.DataFrame(summary_rows))
    final_prices = (
        round_numeric_columns(pd.concat(price_tables, ignore_index=True))
        if price_tables
        else pd.DataFrame(columns=["cut_type", "cut_type_label", "zone", "period", "price"])
    )
    pivoted_prices = round_numeric_columns(pivot_prices_by_zone_period(final_prices, CUT_TYPES))
    plot_paths = generate_plots(summary, final_prices, CUT_TYPES, output_dir)

    summary.to_csv(output_dir / "summary_by_cut_type.csv", index=False)
    final_prices.to_csv(output_dir / "final_prices_long.csv", index=False)
    pivoted_prices.to_csv(output_dir / "final_prices_by_zone_period.csv", index=False)

    metadata = {
        "dataset": DATASET.name,
        "network_model": NETWORK_MODEL,
        "cut_types": [cut_type.name for cut_type in CUT_TYPES],
        "cut_type_labels": [cut_type.value for cut_type in CUT_TYPES],
        "config_overrides": CONFIG_OVERRIDES,
        "reuse_existing_runs": REUSE_EXISTING_RUNS,
        "reuse_warning": (
            "Matching uses dataset, cut type, and network model only. Fresh runs are safer when other "
            "Euphemia overrides matter."
        ),
        "evaluation_root": str(output_dir),
        "selected_runs": selected_runs,
        "plots": plot_paths,
    }
    with open(output_dir / "metadata.json", "w", encoding="utf-8") as handle:
        json.dump(metadata, handle, indent=2)

    print()
    print("=== Cut-Type Summary ===")
    display_columns = [
        "cut_type",
        "source",
        "status",
        "found_solution",
        "iteration",
        "best_objective",
        "corrected_welfare",
        "elapsed_seconds",
        "final_price_count",
    ]
    print(summary.loc[:, [column for column in display_columns if column in summary.columns]].to_string(index=False))
    if plot_paths:
        print()
        print("Generated plots:")
        for name, value in plot_paths.items():
            if isinstance(value, list):
                for path in value:
                    print(f"- {name}: {path}")
            else:
                print(f"- {name}: {value}")
    print()
    print(f"Outputs written to: {output_dir}")


if __name__ == "__main__":
    main()

