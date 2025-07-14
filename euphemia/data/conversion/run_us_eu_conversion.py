import pandas as pd

from apem.data.parsing.parse_data import ParseData
from apem.data.parsing.parse_ieee_rts import ParseIEEERTS

from euphemia.data.conversion.data_conversion import DataConversion
from euphemia.utils.paths import CONVERTED_DATASET_PATH_MAP


def run_us_eu_conversion(us_data: ParseData,
                         generate_uptime_patterns: bool = True,
                         reduce_linked_blocks: bool = True,
                         use_contiguous_patterns: bool = True,
                         compress_identical_blocks: bool = True):
   """
   Run the conversion and compression of a US dataset to EU bidding language

   - us_data: the dataset that should be used
   - generate_uptime_patterns: whether to generate commitment patterns
      for units with minimum uptime constraints or not. Patterns are saved so only necessary for the inital run
   - reduce_linked_blocks: whether to merge linked blocks over several time periods connected to one exclusive block to only one linked block
      to model additional capacity
   - use_contiguous_patterns: restrict patterns to those with one contiguous on/off period
   - compress_identical_blocks: comprise identical block orders from the same generator types in one order
   """

   # Convert US market data
   print("Loading US market data...")
   data = us_data().parse_data()
   conversion = DataConversion(data)
   print("Converting demand data...")
   block_orders_buyers = conversion.compute_buyers_inelastic_bids()
   step_orders = conversion.compute_buyers_elastic_bids()
   print("Converting no min uptime and no no-load cost demand data...")
   scalable_complex_orders, scalable_step_orders = conversion.generate_zero_no_load_cost_bids()
   if generate_uptime_patterns:
      print("Generating patterns for min uptime demand data...")
      conversion.generate_write_patterns(use_contiguous_patterns=use_contiguous_patterns)
   print("Converting min uptime or no-load cost demand data...")
   block_orders_sellers = conversion.generate_positive_no_load_cost_bids(reduce_linked_blocks=reduce_linked_blocks)

   # Load empty datasets for data not filled
   cols = ['id', 'step_orders', 'fixed_term', 'variable_term', 'condition', 'load_gradient']
   complex_orders = pd.DataFrame(columns=cols)
   cols = ['id', 'complex_order_id', 't', 'p', 'q']
   complex_step_orders = pd.DataFrame(columns=cols)
   cols = ['id', 't', 'p0', 'p1', 'q']
   piecewise_linear_orders = pd.DataFrame(columns=cols)



   # compress identical block orders
   if compress_identical_blocks:
      block_orders_sellers = DataConversion.compress_blocks(conversion, block_orders_sellers)

   # merge block orders
   block_orders = pd.concat([block_orders_buyers, block_orders_sellers], ignore_index=True)

   print(f"Size of block orders: {len(block_orders)}")

   periods = data.periods
   periods_df = pd.DataFrame({'period': periods})

   # If emtpy datasets after conversion, replace with empty datasets
   if step_orders.empty:
      cols = ['id', 't', 'p', 'q']
      step_orders = pd.DataFrame(columns=cols)
   if block_orders.empty:
      cols = ['id', 't', 'p'] + [f'q{t}' for t in periods]
      block_orders = pd.DataFrame(columns=cols)
   if scalable_complex_orders.empty:
      cols = ['id','step_orders','fixed_term','condition','load_gradient'] + [f'MAP{t}' for t in periods]
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
      save_df(df, us_data, name)



def save_df(df, us_data: ParseData, name: str):
   output_dir = CONVERTED_DATASET_PATH_MAP[us_data]
   output_dir.mkdir(parents=True, exist_ok=True)
   filepath = output_dir / f"{name}.csv"
   df.to_csv(filepath, index=False)
   print(f"saved: {filepath}")


if __name__ == '__main__':
   run_us_eu_conversion(ParseIEEERTS,
                        generate_uptime_patterns=True,
                        use_contiguous_patterns=True,
                        reduce_linked_blocks=True,
                        compress_identical_blocks=True)