from apem.order_book_based_model.euphemia.utils.paths import DATA_DIR

import datetime as dt


def main() -> None:
    from OMIEData.DataImport.omie_marginalprice_importer import OMIEMarginalPriceFileImporter

    date_ini = dt.datetime(2025, 3, 18)
    date_end = dt.datetime(2025, 3, 18)

    # This can take time, it is downloading the files from the website..
    df = OMIEMarginalPriceFileImporter(date_ini=date_ini, date_end=date_end).read_to_dataframe(verbose=True)
    df.sort_values(by='DATE', axis=0, inplace=True)
    print(df)
    df.to_csv(DATA_DIR / 'omie/raw_data/prices.csv', index=False)


if __name__ == "__main__":
    main()

