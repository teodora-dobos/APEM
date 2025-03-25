def extract_from_buyers(df_buyers, column, buyer, period, bid=None):
    return df_buyers[(df_buyers['buyer'] == buyer) & (df_buyers['period'] == period)][
        column + ("" if bid is None else str(bid))].iloc[0]


def extract_from_sellers(df_sellers, column, seller, period, bid=None):
    return df_sellers[(df_sellers['seller'] == seller) & (df_sellers['period'] == period)][
        column + ("" if bid is None else str(bid))].iloc[0]
