from typing import Any

import pandas as pd


def get(df: pd.DataFrame, column: str, order_id: int) -> Any:
    """Return the value of ``column`` for the row with identifier ``id == order_id``."""

    return df.loc[df['id'] == order_id, column].values[0]


def parse_step_order_ids(raw_string: str, reference_df: pd.DataFrame) -> list:
    """Parse comma-separated step-order ids preserving the reference dtype semantics."""

    raw_ids = [s.strip() for s in raw_string.split(',') if s.strip()]
    id_dtype = reference_df['id'].dtype

    if pd.api.types.is_integer_dtype(id_dtype):
        return [int(s) for s in raw_ids]
    elif pd.api.types.is_string_dtype(id_dtype):
        return raw_ids
    else:
        raise TypeError(f"Unsupported dtype for 'id': {id_dtype}")
