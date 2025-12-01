from apem.EU_market_model.euphemia.utils.paths import DATA_DIR

import datetime as dt
from OMIEData.DataImport.omie_supply_demand_curve_importer import OMIESupplyDemandCurvesImporter
import pandas as pd

dateIni = dt.datetime(2025, 3, 25)
dateEnd = dt.datetime(2025, 3, 25)

# Initialize empty list to store all dataframes
all_data = []

# Loop through all hours (1-24)
for hour in range(1, 25):
    print(f"Fetching data for hour {hour}...")
    
    # This can take time, it is downloading the files from the website..
    df = OMIESupplyDemandCurvesImporter(date_ini=dateIni, date_end=dateEnd, hour=hour).read_to_dataframe(verbose=True)
    
    if not df.empty:
        all_data.append(df)
        print(f"Successfully fetched data for hour {hour}")
    else:
        print(f"No data available for hour {hour}")

# Combine all dataframes
if all_data:
    combined_df = pd.concat(all_data, ignore_index=True)
    combined_df.sort_values(by=['DATE', 'HOUR'], axis=0, inplace=True)
    print(f"Total data shape: {combined_df.shape}")
    print(combined_df.head())
    
    # Save to CSV
    output_path = DATA_DIR / 'omie/raw_data/supply_demand.csv'
    combined_df.to_csv(output_path, index=False)
    print(f"Data saved to {output_path}")
else:
    print("No data was fetched for any hour")