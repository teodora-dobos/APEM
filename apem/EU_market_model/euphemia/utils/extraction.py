from typing import Any

import pandas as pd


def extract_from_buyers(df_buyers: pd.DataFrame, column: str, buyer: int, period: int, bid=None):
    return df_buyers[(df_buyers['buyer'] == buyer) & (df_buyers['period'] == period)][
        column + ("" if bid is None else str(bid))].iloc[0]


def extract_from_sellers(df_sellers: pd.DataFrame, column: str, seller: int, period: int, bid=None):
    return df_sellers[(df_sellers['seller'] == seller) & (df_sellers['period'] == period)][
        column + ("" if bid is None else str(bid))].iloc[0]


def get(df: pd.DataFrame, column: str, order_id: int) -> Any:
    return df.loc[df['id'] == order_id, column].values[0]


def parse_step_order_ids(raw_string: str, reference_df: pd.DataFrame) -> list:
    raw_ids = [s.strip() for s in raw_string.split(',') if s.strip()]
    id_dtype = reference_df['id'].dtype

    if pd.api.types.is_integer_dtype(id_dtype):
        return [int(s) for s in raw_ids]
    elif pd.api.types.is_string_dtype(id_dtype):
        return raw_ids
    else:
        raise TypeError(f"Unsupported dtype for 'id': {id_dtype}")
