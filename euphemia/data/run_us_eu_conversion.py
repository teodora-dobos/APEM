from apem.data.data_conversion import DataConversion
from apem.data.parsing.parse_ieee_rts import ParseIEEERTS

from apem.data.parsing.parse_pypsa_eur_large import ParsePyPSAEurLarge

from apem.data.data_conversion import DataConversion
from euphemia.data.parsing.zonal_scenario import ZonalScenario


def run_us_eu_conversion():
   # data = ParsePyPSAEurLarge().parse_data()
   data = ParseIEEERTS().parse_data()
   print(data)
   conversion = DataConversion(data)
   block_orders = conversion.compute_buyers_inelastic_bids()
   step_orders = conversion.compute_buyers_elastic_bids()
   conversion.generate_write_patterns()
   scalable_complex_orders, scalable_complex__step_orders = conversion.generate_no_min_uptime_bids()

   print(f"Sell min uptime: {conversion.generate_min_uptime_bids()}")
   scenario = ZonalScenario('ConvertedData', )

if __name__ == '__main__':
   run_us_eu_conversion()