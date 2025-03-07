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