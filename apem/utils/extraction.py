import pandas as pd

def preprocess_as_dict(df: pd.DataFrame, index_cols: list, column: str, bid_block: int = None) -> dict:
    """
    Convert a specified column (optionally suffixed by 'bid_block') of a DataFrame into a dictionary with a given index.

    Parameters:
        df (pd.DataFrame): the input DataFrame
        index_cols (list): columns to use as the dictionary key (tuple if multiple)
        column (str): base name of the column to convert
        bid_block (int, optional): optional suffix to append to the column name

    Returns:
        dict: dictionary representation of the column values keyed by index_cols
    """
    column_name = column + ("" if bid_block is None else str(bid_block))
    
    return df.set_index(index_cols)[column_name].to_dict()