from apem.data.parsing.parse_arpa import ParseARPA
from apem.data.parsing.parse_ieee_rts import ParseIEEERTS
import pandas as pd

from apem.data.parsing.parse_pjm import ParsePJM
from apem.data.parsing.parse_pypsa_eur_large import ParsePyPSAEurLarge

from apem.data.data_conversion import DataConversion
from apem.data.parsing.parse_pypsa_eur_small import ParsePyPSAEurSmall
from euphemia.utils.paths import RAW_DATA_DIR
from euphemia.data.parsing.zonal_scenario import ZonalScenario
from euphemia.euphemia import Euphemia

path = RAW_DATA_DIR / "templates"


def run_us_eu_conversion():
   # Convert US market data
   print("Loading US market data...")
   data = ParsePJM().parse_data()
   conversion = DataConversion(data)
   print("Converting demand data...")
   block_orders_buyers = conversion.compute_buyers_inelastic_bids()
   step_orders = conversion.compute_buyers_elastic_bids()
   print("Converting no min uptime demand data...")
   scalable_complex_orders, scalable_step_orders = conversion.generate_no_min_uptime_bids()
   print("Generating patterns for min uptime demand data...")
   conversion.generate_write_patterns()
   print("Converting min uptime demand data...")
   block_orders_sellers = conversion.generate_min_uptime_bids()

   # Load empty datasets
   complex_orders = pd.read_csv(path / 'complex_orders_template.csv')
   complex_step_orders = pd.read_csv(path / 'complex_step_orders_template.csv')
   piecewise_linear_orders = pd.read_csv(path / 'piecewise_linear_orders_template.csv')

   #merge block orders
   block_orders = pd.concat([block_orders_buyers, block_orders_sellers], ignore_index=True)

   periods = data.periods
   scenario = ZonalScenario('ConvertedData', periods, step_orders, block_orders, complex_orders, complex_step_orders,
                            scalable_complex_orders, scalable_step_orders, piecewise_linear_orders)

   print("Conversion finished, Starting solving...")
   model = Euphemia(scenario)
   model.solve()


def reset_id_column(df):
   if 'id' in df.columns:
      df = df.drop('id', axis=1)
   df.insert(0, 'id', range(1, len(df) + 1))
   return df


if __name__ == '__main__':
   run_us_eu_conversion()