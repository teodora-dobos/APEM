"""Plotting helpers for evaluation outputs such as prices, lost opportunity costs, welfare, and redispatch metrics."""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Sequence

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def plot_average_prices_by_period(
    prices: pd.DataFrame,
    output_file: str | Path,
    algorithm_order: Sequence[str] | None = None,
    statistic_fn: Callable[[np.ndarray], float] = np.mean,
) -> None:
    """
    Plot one aggregated price statistic by period for each algorithm.

    :param prices: price table containing at least ``period``, ``algorithm``,
                   and ``price``
    :param output_file: output image path
    :param algorithm_order: optional plotting order for algorithms
    :param statistic_fn: aggregation function applied to price values
                         (for example ``np.mean`` or ``np.median``)
    :return: ``None``
    """
    statistic_label = _statistic_label(statistic_fn)
    aggregated_prices = _aggregate_prices(prices, ["period", "algorithm"], statistic_fn).pivot(
        index="period",
        columns="algorithm",
        values="price",
    ).sort_index()

    plt.figure(figsize=(10, 6))
    for algorithm_name in _resolve_algorithm_order(aggregated_prices.columns, algorithm_order):
        plt.plot(aggregated_prices.index, aggregated_prices[algorithm_name], marker="o", label=algorithm_name)

    plt.xlabel("Period")
    plt.ylabel(f"{statistic_label} Price")
    plt.title(f"{statistic_label} Prices by Period and Algorithm")
    plt.xticks(aggregated_prices.index.tolist())
    plt.grid(True)
    plt.legend()
    plt.tight_layout()
    plt.savefig(output_file, dpi=200)
    plt.close()


def plot_average_prices_by_node(
    prices: pd.DataFrame,
    output_file: str | Path,
    algorithm_order: Sequence[str] | None = None,
    statistic_fn: Callable[[np.ndarray], float] = np.mean,
) -> None:
    """
    Plot one aggregated price statistic by node for each algorithm.

    :param prices: price table containing at least ``node``, ``algorithm``,
                   and ``price``
    :param output_file: output image path
    :param algorithm_order: optional plotting order for algorithms
    :param statistic_fn: aggregation function applied to price values
    :return: ``None``
    """
    statistic_label = _statistic_label(statistic_fn)
    aggregated_prices = _aggregate_prices(prices, ["node", "algorithm"], statistic_fn).pivot(
        index="node",
        columns="algorithm",
        values="price",
    )

    sort_reference = next(iter(_resolve_algorithm_order(aggregated_prices.columns, algorithm_order)), None)
    if sort_reference is not None:
        aggregated_prices = aggregated_prices.sort_values(by=sort_reference)

    aggregated_prices = aggregated_prices.reset_index()
    x_positions = range(len(aggregated_prices))

    plt.figure(figsize=(14, 7))
    for algorithm_name in _resolve_algorithm_order(aggregated_prices.columns, algorithm_order):
        if algorithm_name == "node":
            continue
        plt.plot(
            x_positions,
            aggregated_prices[algorithm_name],
            marker="o",
            markersize=2,
            linewidth=1,
            label=algorithm_name,
        )

    tick_step = max(1, len(aggregated_prices) // 20)
    tick_positions = list(range(0, len(aggregated_prices), tick_step))
    tick_labels = aggregated_prices.loc[tick_positions, "node"].astype(str).tolist()

    plt.xlabel("Node")
    plt.ylabel(f"{statistic_label} Price")
    plt.title(f"{statistic_label} Prices by Node and Algorithm")
    plt.xticks(tick_positions, tick_labels, rotation=45, ha="right")
    plt.grid(True)
    plt.legend()
    plt.tight_layout()
    plt.savefig(output_file, dpi=200)
    plt.close()


def plot_price_boxplot_by_period(
    prices: pd.DataFrame,
    output_file: str | Path,
    algorithm_order: Sequence[str] | None = None,
    statistic_fn: Callable[[np.ndarray], float] = np.mean,
) -> None:
    """
    Create a boxplot across algorithms using one aggregated value per period.

    :param prices: price table containing ``period``, ``algorithm``, ``price``
    :param output_file: output image path
    :param algorithm_order: optional plotting order for algorithms
    :param statistic_fn: aggregation function applied within each period
    :return: ``None``
    """
    aggregated_prices = _aggregate_prices(prices, ["period", "algorithm"], statistic_fn).pivot(
        index="period",
        columns="algorithm",
        values="price",
    )
    _plot_algorithm_boxplot(
        aggregated_prices,
        output_file,
        algorithm_order=algorithm_order,
        title=f"Boxplot of {_statistic_label(statistic_fn)} Prices by Period and Algorithm",
        ylabel=f"{_statistic_label(statistic_fn)} Price",
    )


def plot_price_boxplot_by_node(
    prices: pd.DataFrame,
    output_file: str | Path,
    algorithm_order: Sequence[str] | None = None,
    statistic_fn: Callable[[np.ndarray], float] = np.mean,
) -> None:
    """
    Create a boxplot across algorithms using one aggregated value per node.

    :param prices: price table containing ``node``, ``algorithm``, ``price``
    :param output_file: output image path
    :param algorithm_order: optional plotting order for algorithms
    :param statistic_fn: aggregation function applied within each node
    :return: ``None``
    """
    aggregated_prices = _aggregate_prices(prices, ["node", "algorithm"], statistic_fn).pivot(
        index="node",
        columns="algorithm",
        values="price",
    )
    _plot_algorithm_boxplot(
        aggregated_prices,
        output_file,
        algorithm_order=algorithm_order,
        title=f"Boxplot of {_statistic_label(statistic_fn)} Prices by Node and Algorithm",
        ylabel=f"{_statistic_label(statistic_fn)} Price",
    )


def plot_lost_opp_cost_by_component(
    lost_opp_costs: pd.DataFrame,
    output_file: str | Path,
    *,
    lost_opp_cost_type: str,
    algorithm_order: Sequence[str] | None = None,
) -> None:
    """
    Plot one lost-opportunity-cost type across components for each algorithm.

    :param lost_opp_costs: table containing at least ``lost_opp_cost``,
                           ``component``, ``algorithm``, ``value``
    :param output_file: output image path
    :param lost_opp_cost_type: selected type to plot (for example ``glocs``)
    :param algorithm_order: optional plotting order for algorithms
    :return: ``None``
    :raises ValueError: if filtered data is empty or duplicates exist per
                        component and algorithm
    """
    filtered = lost_opp_costs.loc[
        lost_opp_costs["lost_opp_cost"].astype(str).str.lower() == str(lost_opp_cost_type).lower()
    ].copy()
    if filtered.empty:
        raise ValueError(f"No rows found for lost_opp_cost '{lost_opp_cost_type}'.")

    duplicates = filtered.duplicated(subset=["component", "algorithm"], keep=False)
    if duplicates.any():
        duplicate_rows = filtered.loc[duplicates, ["component", "algorithm"]]
        preview = duplicate_rows.head(5).to_dict(orient="records")
        raise ValueError(
            "Found duplicate lost opportunity cost rows for the same component and algorithm. "
            f"Examples: {preview}"
        )

    plotted = filtered.pivot(index="component", columns="algorithm", values="value")

    component_order = ["buyers", "sellers", "network", "total"]
    available_components = [component for component in component_order if component in plotted.index]
    remaining_components = [component for component in plotted.index if component not in component_order]
    plotted = plotted.loc[available_components + remaining_components]

    ordered_algorithms = _resolve_algorithm_order(plotted.columns, algorithm_order)
    x_positions = np.arange(len(plotted.index))
    width = 0.8 / max(len(ordered_algorithms), 1)

    plt.figure(figsize=(10, 6))
    for index, algorithm_name in enumerate(ordered_algorithms):
        offsets = x_positions + (index - (len(ordered_algorithms) - 1) / 2) * width
        plt.bar(offsets, plotted[algorithm_name], width=width, label=algorithm_name)

    plt.xlabel("Component")
    plt.ylabel("Lost Opportunity Cost")
    plt.title(f"{lost_opp_cost_type.upper()} by Component and Algorithm")
    plt.xticks(x_positions, [str(component).title() for component in plotted.index])
    plt.grid(True, axis="y")
    plt.legend()
    plt.tight_layout()
    plt.savefig(output_file, dpi=200)
    plt.close()


def plot_welfare_by_period(
    welfare_table: pd.DataFrame,
    output_file: str | Path,
    power_flow_model_order: Sequence[str] | None = None,
) -> None:
    """
    Plot period welfare trajectories for each power-flow model.

    :param welfare_table: welfare table containing ``welfare_scope``, ``period``,
                          ``power_flow_model``, and ``welfare``
    :param output_file: output image path
    :param power_flow_model_order: optional plotting order for models
    :return: ``None``
    :raises ValueError: if no period-level welfare rows are found
    """
    period_welfare = welfare_table.loc[welfare_table["welfare_scope"] == "period"].copy()
    if period_welfare.empty:
        raise ValueError("No period welfare rows found.")

    period_welfare = period_welfare.pivot(
        index="period",
        columns="power_flow_model",
        values="welfare",
    ).sort_index()

    plt.figure(figsize=(10, 6))
    for model_name in _resolve_algorithm_order(period_welfare.columns, power_flow_model_order):
        plt.plot(period_welfare.index, period_welfare[model_name], marker="o", label=model_name)

    plt.xlabel("Period")
    plt.ylabel("Welfare")
    plt.title("Welfare by Period and Power-Flow Model")
    plt.xticks(period_welfare.index.tolist())
    plt.grid(True)
    plt.legend()
    plt.tight_layout()
    plt.savefig(output_file, dpi=200)
    plt.close()


def plot_total_welfare_by_power_flow_model(
    welfare_table: pd.DataFrame,
    output_file: str | Path,
    power_flow_model_order: Sequence[str] | None = None,
) -> None:
    """
    Plot total welfare for each power-flow model as a bar chart.

    :param welfare_table: welfare table containing ``welfare_scope``,
                          ``power_flow_model``, and ``welfare``
    :param output_file: output image path
    :param power_flow_model_order: optional plotting order for models
    :return: ``None``
    :raises ValueError: if no total rows exist or duplicates exist per model
    """
    total_welfare = welfare_table.loc[welfare_table["welfare_scope"] == "total"].copy()
    if total_welfare.empty:
        raise ValueError("No total welfare rows found.")

    duplicates = total_welfare.duplicated(subset=["power_flow_model"], keep=False)
    if duplicates.any():
        duplicate_rows = total_welfare.loc[duplicates, ["power_flow_model"]]
        preview = duplicate_rows.head(5).to_dict(orient="records")
        raise ValueError(f"Found duplicate total welfare rows per power-flow model. Examples: {preview}")

    totals = total_welfare.set_index("power_flow_model")["welfare"]
    ordered_models = _resolve_algorithm_order(totals.index.tolist(), power_flow_model_order)

    plt.figure(figsize=(10, 6))
    plt.bar(ordered_models, totals.loc[ordered_models])
    plt.xlabel("Power-Flow Model")
    plt.ylabel("Total Welfare")
    plt.title("Total Welfare by Power-Flow Model")
    plt.xticks(rotation=20, ha="right")
    plt.grid(True, axis="y")
    plt.tight_layout()
    plt.savefig(output_file, dpi=200)
    plt.close()


def plot_value_by_period_and_power_flow_model(
    table: pd.DataFrame,
    output_file: str | Path,
    *,
    period_column: str,
    model_column: str,
    value_column: str,
    ylabel: str,
    title: str,
    power_flow_model_order: Sequence[str] | None = None,
) -> None:
    """
    Plot a generic value by period for each power-flow model.

    :param table: input table
    :param output_file: output image path
    :param period_column: column name used as x-axis period
    :param model_column: column name used for model grouping
    :param value_column: numeric value column to plot
    :param ylabel: y-axis label
    :param title: chart title
    :param power_flow_model_order: optional plotting order for models
    :return: ``None``
    :raises ValueError: if required columns are missing
    """
    if period_column not in table.columns:
        raise ValueError(f"Input table must contain the period column '{period_column}'.")
    if model_column not in table.columns:
        raise ValueError(f"Input table must contain the model column '{model_column}'.")
    if value_column not in table.columns:
        raise ValueError(f"Input table must contain the value column '{value_column}'.")

    plotted = table.pivot(
        index=period_column,
        columns=model_column,
        values=value_column,
    ).sort_index()

    plt.figure(figsize=(10, 6))
    for model_name in _resolve_algorithm_order(plotted.columns, power_flow_model_order):
        plt.plot(plotted.index, plotted[model_name], marker="o", label=model_name)

    plt.xlabel("Period")
    plt.ylabel(ylabel)
    plt.title(title)
    plt.xticks(plotted.index.tolist())
    plt.grid(True)
    plt.legend()
    plt.tight_layout()
    plt.savefig(output_file, dpi=200)
    plt.close()


def plot_redispatch_metric_by_algorithm(
    redispatch_table: pd.DataFrame,
    output_file: str | Path,
    *,
    metric: str,
    redispatch_algorithm_order: Sequence[str] | None = None,
) -> None:
    """
    Plot one redispatch metric as a bar chart across redispatch algorithms.

    :param redispatch_table: redispatch table containing ``metric``,
                             ``redispatch_algorithm``, and ``value``
    :param output_file: output image path
    :param metric: selected metric label (for example ``costs``)
    :param redispatch_algorithm_order: optional plotting order for algorithms
    :return: ``None``
    :raises ValueError: if filtered data is empty or duplicates exist per
                        redispatch algorithm
    """
    filtered = redispatch_table.loc[redispatch_table["metric"] == metric].copy()
    if filtered.empty:
        raise ValueError(f"No rows found for redispatch metric '{metric}'.")

    duplicates = filtered.duplicated(subset=["redispatch_algorithm"], keep=False)
    if duplicates.any():
        duplicate_rows = filtered.loc[duplicates, ["redispatch_algorithm"]]
        preview = duplicate_rows.head(5).to_dict(orient="records")
        raise ValueError(f"Found duplicate redispatch metric rows per algorithm. Examples: {preview}")

    values = filtered.set_index("redispatch_algorithm")["value"]
    ordered_algorithms = _resolve_algorithm_order(values.index.tolist(), redispatch_algorithm_order)

    plt.figure(figsize=(10, 6))
    plt.bar(ordered_algorithms, values.loc[ordered_algorithms])
    plt.xlabel("Redispatch Algorithm")
    plt.ylabel(metric.title())
    plt.title(f"Redispatch {metric.title()} by Algorithm")
    plt.xticks(rotation=20, ha="right")
    plt.grid(True, axis="y")
    plt.tight_layout()
    plt.savefig(output_file, dpi=200)
    plt.close()


def plot_redispatch_metric_by_power_flow_model(
    redispatch_table: pd.DataFrame,
    output_file: str | Path,
    *,
    metric: str,
    power_flow_model_order: Sequence[str] | None = None,
) -> None:
    """
    Plot one redispatch metric as a bar chart across power-flow models.

    :param redispatch_table: redispatch table containing ``metric``,
                             ``power_flow_model``, and ``value``
    :param output_file: output image path
    :param metric: selected metric label (for example ``costs``)
    :param power_flow_model_order: optional plotting order for models
    :return: ``None``
    :raises ValueError: if filtered data is empty or duplicates exist per
                        power-flow model
    """
    filtered = redispatch_table.loc[redispatch_table["metric"] == metric].copy()
    if filtered.empty:
        raise ValueError(f"No rows found for redispatch metric '{metric}'.")

    duplicates = filtered.duplicated(subset=["power_flow_model"], keep=False)
    if duplicates.any():
        duplicate_rows = filtered.loc[duplicates, ["power_flow_model"]]
        preview = duplicate_rows.head(5).to_dict(orient="records")
        raise ValueError(f"Found duplicate redispatch metric rows per power-flow model. Examples: {preview}")

    values = filtered.set_index("power_flow_model")["value"]
    ordered_models = _resolve_algorithm_order(values.index.tolist(), power_flow_model_order)

    plt.figure(figsize=(10, 6))
    plt.bar(ordered_models, values.loc[ordered_models])
    plt.xlabel("Power-Flow Model")
    plt.ylabel(metric.title())
    plt.title(f"Redispatch {metric.title()} by Power-Flow Model")
    plt.xticks(rotation=20, ha="right")
    plt.grid(True, axis="y")
    plt.tight_layout()
    plt.savefig(output_file, dpi=200)
    plt.close()


def plot_value_by_power_flow_model(
    table: pd.DataFrame,
    output_file: str | Path,
    *,
    value_column: str,
    ylabel: str,
    title: str,
    power_flow_model_order: Sequence[str] | None = None,
) -> None:
    """
    Plot one value column as a bar chart across power-flow models.

    :param table: input table containing ``power_flow_model`` and one value
                  column
    :param output_file: output image path
    :param value_column: column name to plot on the y-axis
    :param ylabel: y-axis label
    :param title: chart title
    :param power_flow_model_order: optional plotting order for models
    :return: ``None``
    :raises ValueError: if required columns are missing or duplicates exist per
                        power-flow model
    """
    if "power_flow_model" not in table.columns:
        raise ValueError("Input table must contain a 'power_flow_model' column.")
    if value_column not in table.columns:
        raise ValueError(f"Input table must contain the value column '{value_column}'.")

    duplicates = table.duplicated(subset=["power_flow_model"], keep=False)
    if duplicates.any():
        duplicate_rows = table.loc[duplicates, ["power_flow_model"]]
        preview = duplicate_rows.head(5).to_dict(orient="records")
        raise ValueError(f"Found duplicate value rows per power-flow model. Examples: {preview}")

    values = table.set_index("power_flow_model")[value_column]
    ordered_models = _resolve_algorithm_order(values.index.tolist(), power_flow_model_order)

    plt.figure(figsize=(10, 6))
    plt.bar(ordered_models, values.loc[ordered_models])
    plt.xlabel("Power-Flow Model")
    plt.ylabel(ylabel)
    plt.title(title)
    plt.xticks(rotation=20, ha="right")
    plt.grid(True, axis="y")
    plt.tight_layout()
    plt.savefig(output_file, dpi=200)
    plt.close()


def _aggregate_prices(
    prices: pd.DataFrame,
    group_columns: Sequence[str],
    statistic_fn: Callable[[np.ndarray], float],
) -> pd.DataFrame:
    aggregated = (
        prices.groupby(list(group_columns), dropna=False)["price"]
        .apply(lambda series: _apply_statistic(series, statistic_fn))
        .reset_index(name="price")
    )
    return aggregated




def _apply_statistic(series: pd.Series, statistic_fn: Callable[[np.ndarray], float]) -> float:
    values = series.dropna().to_numpy()
    if values.size == 0:
        return float("nan")
    return float(statistic_fn(values))


def _statistic_label(statistic_fn: Callable[[np.ndarray], float]) -> str:
    name = getattr(statistic_fn, "__name__", "statistic")
    labels = {
        "mean": "Mean",
        "average": "Mean",
        "std": "Std",
        "var": "Variance",
    }
    return labels.get(name.lower(), name.replace("_", " ").title())


def statistic_name(statistic_fn: Callable[[np.ndarray], float]) -> str:
    """
    Return a lowercase filename-safe name for the selected statistic function.

    :param statistic_fn: aggregation callable (for example ``np.mean``)
    :return: lowercase snake-case statistic label
    """
    return _statistic_label(statistic_fn).lower().replace(" ", "_")


def _resolve_algorithm_order(
    available_columns: Sequence[str],
    algorithm_order: Sequence[str] | None,
) -> list[str]:
    if algorithm_order is None:
        return [str(column) for column in available_columns if str(column) != "node"]
    return [algorithm for algorithm in algorithm_order if algorithm in available_columns]


def _plot_algorithm_boxplot(
    aggregated_prices: pd.DataFrame,
    output_file: str | Path,
    *,
    algorithm_order: Sequence[str] | None,
    title: str,
    ylabel: str,
) -> None:
    ordered_algorithms = _resolve_algorithm_order(aggregated_prices.columns, algorithm_order)
    data = [aggregated_prices[algorithm].dropna().to_numpy() for algorithm in ordered_algorithms]

    plt.figure(figsize=(10, 6))
    plt.boxplot(data, tick_labels=ordered_algorithms, patch_artist=True)
    plt.title(title)
    plt.ylabel(ylabel)
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(output_file, dpi=200)
    plt.close()
