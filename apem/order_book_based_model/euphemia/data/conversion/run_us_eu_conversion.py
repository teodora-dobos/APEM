import pandas as pd

from apem.unit_based_model.data.parsing.parse_data import ParseData
from apem.unit_based_model.data.parsing.parse_ieee_rts import ParseIEEERTS

from apem.order_book_based_model.euphemia.data.conversion.data_conversion import DataConversion
from apem.order_book_based_model.euphemia.utils.paths import CONVERTED_DATASET_PATH_MAP


def run_unit_based_to_order_based_conversion(
    unit_based_data: ParseData,
    generate_uptime_patterns: bool = True,
    reduce_linked_blocks: bool = True,
    use_contiguous_patterns: bool = True,
    compress_identical_blocks: bool = True,
 ) -> None:
    """
    Convert a unit-based dataset into order-book Euphemia CSV inputs.

    :param unit_based_data: Parser class for the source unit-based dataset.
    :param generate_uptime_patterns: Whether to generate and persist commitment
        patterns for units with minimum-uptime constraints.
    :param reduce_linked_blocks: Whether to merge linked child blocks across
        multiple active periods when they share the same price segment.
    :param use_contiguous_patterns: Whether to restrict commitment patterns to
        contiguous on/off trajectories.
    :param compress_identical_blocks: Whether to merge identical converted
        block-order chains before writing the output CSV files.
    """

    # Load the source unit-based scenario.
    print("Loading unit-based market data...")
    data = unit_based_data().parse_data()

    conversion = DataConversion(data)

    print("Converting demand-side data...")
    block_orders_buyers = conversion.compute_buyers_inelastic_bids()
    step_orders = conversion.compute_buyers_elastic_bids()

    print("Converting simple supply-side offers...")
    scalable_complex_orders, scalable_step_orders = conversion.generate_zero_no_load_cost_bids()
    if generate_uptime_patterns:
        print("Generating commitment patterns for supply-side conversion...")
        conversion.generate_write_patterns(use_contiguous_patterns=use_contiguous_patterns)
    print("Converting commitment-coupled supply-side offers...")
    block_orders_sellers = conversion.generate_positive_no_load_cost_bids(reduce_linked_blocks=reduce_linked_blocks)

    # Load empty datasets for data not filled
    cols = ['id', 'step_orders', 'fixed_term', 'variable_term', 'condition', 'load_gradient']
    complex_orders = pd.DataFrame(columns=cols)
    cols = ['id', 'complex_order_id', 't', 'p', 'q']
    complex_step_orders = pd.DataFrame(columns=cols)
    cols = ['id', 't', 'p0', 'p1', 'q']
    piecewise_linear_orders = pd.DataFrame(columns=cols)

    # Compress identical block orders
    if compress_identical_blocks:
        block_orders_sellers = DataConversion.compress_blocks(conversion, block_orders_sellers)

    # Merge block orders
    block_orders = pd.concat([block_orders_buyers, block_orders_sellers], ignore_index=True)

    print(f"Size of block orders: {len(block_orders)}")

    periods = data.periods
    periods_df = pd.DataFrame({'period': periods})

    # If empty datasets after conversion, replace with empty datasets
    if step_orders.empty:
        cols = ['id', 't', 'p', 'q']
        step_orders = pd.DataFrame(columns=cols)
    if block_orders.empty:
        cols = ['id', 't', 'p'] + [f'q{t}' for t in periods]
        block_orders = pd.DataFrame(columns=cols)
    if scalable_complex_orders.empty:
        cols = ['id', 'step_orders', 'fixed_term', 'condition', 'load_gradient'] + [f'MAP{t}' for t in periods]
        scalable_complex_orders = pd.DataFrame(columns=cols)
        cols = ['id', 'scalable_order_id', 't', 'p', 'q']
        scalable_step_orders = pd.DataFrame(columns=cols)

    # Save converted datasets
    dfs = {
        "periods": periods_df,
        "step_orders": step_orders,
        "block_orders": block_orders,
        "scalable_complex_orders": scalable_complex_orders,
        "scalable_step_orders": scalable_step_orders,
        "complex_orders": complex_orders,
        "complex_step_orders": complex_step_orders,
        "piecewise_linear_orders": piecewise_linear_orders,
    }
    for name, df in dfs.items():
        save_df(df, unit_based_data, name)


def save_df(df: pd.DataFrame, unit_based_data: ParseData, name: str) -> None:
    """Persist one converted dataframe into the mapped order-book dataset folder."""

    output_dir = CONVERTED_DATASET_PATH_MAP[unit_based_data]
    output_dir.mkdir(parents=True, exist_ok=True)
    filepath = output_dir / f"{name}.csv"
    df.to_csv(filepath, index=False)
    print(f"Saved: {filepath}")


if __name__ == '__main__':
    """
    Convert a unit-based dataset into order-book Euphemia inputs.
    """
    run_unit_based_to_order_based_conversion(
        ParseIEEERTS,
        generate_uptime_patterns=True,
        use_contiguous_patterns=True,
        reduce_linked_blocks=True,
        compress_identical_blocks=True,
    )
