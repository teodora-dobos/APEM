import pandas as pd

from apem.order_book_based_model.euphemia.utils.paths import DATA_DIR


def convert_omie_to_step_orders(input_path: str, output_path: str, days: list[str] = None):
    """
    Converts an OMIE-style supply/demand CSV file to the Euphemia-compatible step order format.

    Parameters:
    - input_path: Path to the OMIE CSV file
    - output_path: Path to save the converted step order CSV file
    - days: Optional list of dates (as 'dd/mm/yyyy') to filter the data
    """
    # Read the OMIE file (assuming comma separator)
    df = pd.read_csv(input_path, sep=",")

    # Clean column names
    df.columns = df.columns.str.strip()

    # Optional: filter by specific days
    if days is not None:
        df['DATE'] = df['DATE'].str.strip()
        df = df[df['DATE'].isin(days)]

    # Select and rename relevant columns
    converted = df[['HOUR', 'PRICE', 'ENERGY', 'OFFER_TYPE']].copy()
    converted.rename(columns={'HOUR': 't', 'PRICE': 'p', 'ENERGY': 'q'}, inplace=True)

    # Apply quantity sign: positive for sales ('C'), negative for buys ('D')
    converted['q'] = converted.apply(lambda row: row['q'] if row['OFFER_TYPE'] == 'C' else -row['q'], axis=1)

    # Drop OFFER_TYPE and add order ID
    converted.drop(columns='OFFER_TYPE', inplace=True)
    converted.reset_index(drop=True, inplace=True)
    converted.insert(0, 'id', converted.index + 1)

    # Save to CSV
    converted.to_csv(output_path, index=False)
    print(f"Converted file saved to: {output_path}")


def main() -> None:
    convert_omie_to_step_orders(
        DATA_DIR / "omie/raw_data/supply_demand_curves.csv",
        DATA_DIR / "omie/step_orders.csv",
        days=None,
    )


if __name__ == "__main__":
    main()

