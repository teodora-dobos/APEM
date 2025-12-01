from apem.EU_market_model.euphemia.utils.paths import DATA_DIR

import datetime as dt

from OMIEData.DataImport.omie_marginalprice_importer import OMIEMarginalPriceFileImporter

dateIni = dt.datetime(2025, 3, 18)
dateEnd = dt.datetime(2025, 3, 18)

# This can take time, it is downloading the files from the website..
df = OMIEMarginalPriceFileImporter(date_ini=dateIni, date_end=dateEnd).read_to_dataframe(verbose=True)
df.sort_values(by='DATE', axis=0, inplace=True)
print(df)
df.to_csv(DATA_DIR / 'omie/raw_data/prices.csv', index=False)