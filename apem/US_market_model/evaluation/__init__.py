"""Generic evaluation utilities for the US market model."""

from apem.US_market_model.evaluation.lost_opp_cost_analysis import (
    load_lost_opp_cost_table,
    validate_lost_opp_cost_table,
)
from apem.US_market_model.evaluation.price_analysis import (
    compare_price_algorithms,
    round_numeric_columns,
    summarize_prices,
    validate_price_table,
)
from apem.US_market_model.evaluation.redispatch_analysis import (
    load_redispatch_metric_file,
    validate_redispatch_table,
)
from apem.US_market_model.evaluation.welfare_analysis import (
    load_welfare_table,
    validate_welfare_table,
)
from apem.US_market_model.evaluation.plotting import (
    plot_average_prices_by_node,
    plot_average_prices_by_period,
    plot_lost_opp_cost_by_component,
    plot_price_boxplot_by_node,
    plot_price_boxplot_by_period,
    plot_redispatch_metric_by_algorithm,
    plot_redispatch_metric_by_power_flow_model,
    plot_total_welfare_by_power_flow_model,
    plot_value_by_period_and_power_flow_model,
    plot_value_by_power_flow_model,
    plot_welfare_by_period,
    statistic_name,
)
from apem.US_market_model.evaluation.run_lookup import (
    ensure_lost_opp_cost_run_for_configuration,
    ensure_redispatch_run_for_configuration,
    ensure_run_for_configuration,
    ensure_welfare_run_for_configuration,
    find_latest_matching_lost_opp_cost_run,
    find_latest_matching_redispatch_run,
    find_latest_matching_run,
    find_latest_matching_welfare_run,
    load_lost_opp_costs_from_run,
    load_prices_from_run,
    load_redispatch_metrics_from_run,
    load_welfare_from_run,
    normalize_run_dir,
    parse_run_config,
)

__all__ = [
    "compare_price_algorithms",
    "ensure_lost_opp_cost_run_for_configuration",
    "ensure_redispatch_run_for_configuration",
    "ensure_run_for_configuration",
    "ensure_welfare_run_for_configuration",
    "find_latest_matching_lost_opp_cost_run",
    "find_latest_matching_redispatch_run",
    "find_latest_matching_run",
    "find_latest_matching_welfare_run",
    "load_lost_opp_costs_from_run",
    "load_lost_opp_cost_table",
    "load_prices_from_run",
    "load_redispatch_metric_file",
    "load_redispatch_metrics_from_run",
    "load_welfare_from_run",
    "load_welfare_table",
    "normalize_run_dir",
    "parse_run_config",
    "plot_average_prices_by_node",
    "plot_average_prices_by_period",
    "plot_lost_opp_cost_by_component",
    "plot_price_boxplot_by_node",
    "plot_price_boxplot_by_period",
    "plot_redispatch_metric_by_algorithm",
    "plot_redispatch_metric_by_power_flow_model",
    "plot_total_welfare_by_power_flow_model",
    "plot_value_by_period_and_power_flow_model",
    "plot_value_by_power_flow_model",
    "plot_welfare_by_period",
    "round_numeric_columns",
    "statistic_name",
    "summarize_prices",
    "validate_lost_opp_cost_table",
    "validate_price_table",
    "validate_redispatch_table",
    "validate_welfare_table",
]
