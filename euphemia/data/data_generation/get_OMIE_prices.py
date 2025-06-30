from euphemia.utils.paths import EUPHEMIA_ROOT

import datetime as dt
import matplotlib.pyplot as plt

from OMIEData.DataImport.omie_marginalprice_importer import OMIEMarginalPriceFileImporter
from OMIEData.Enums.all_enums import DataTypeInMarginalPriceFile

dateIni = dt.datetime(2025, 3, 18)
dateEnd = dt.datetime(2025, 3, 18)

# This can take time, it is downloading the files from the website..
df = OMIEMarginalPriceFileImporter(date_ini=dateIni, date_end=dateEnd).read_to_dataframe(verbose=True)
df.sort_values(by='DATE', axis=0, inplace=True)
print(df)
df.to_csv(EUPHEMIA_ROOT / 'data/raw_data/omie/prices.csv', index=False)