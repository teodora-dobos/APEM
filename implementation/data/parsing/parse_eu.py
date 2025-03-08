from typing import Optional, List

import pandas as pd

from implementation.data.parsing.parse_data import ParseData
from implementation.data.parsing.zonal_scenario import ZonalScenario


def transform_step_orders(orders: pd.DataFrame, periods: List[int], sell: bool, order_id: Optional[int] = None,
                          scalable: Optional[bool] = None) -> pd.DataFrame:
    """
    Transform step orders such that q_i = (q_s+1 - q_s) if sell is True and q_i = (q_s - q_s+1) otherwise.
    """
    id_array, t_array, p_array, q_array, complex_id_array = [], [], [], [], []
    cond_q = orders['q'] > 0 if sell else orders['q'] < 0

    cond_order_id = True
    if order_id:
        cond_order_id = orders['scalable_order_id'] == order_id if scalable else orders['complex_order_id'] == order_id

    for t in periods:
        orders_t_df = orders[(orders['t'] == t) & cond_q & cond_order_id]
        orders_t_dict = orders_t_df.to_dict(orient='records')
        first = True
        previous = None
        for order in orders_t_dict:
            id_array.append(order['id'])
            t_array.append(order['t'])
            p_array.append(order['p'])

            if order_id:
                complex_id_array.append(order['scalable_order_id'] if scalable else order['complex_order_id'])

            if first:
                q_array.append(order['q'])
            else:
                q_array.append(order['q'] - previous if sell else previous - order['q'])

            previous = order['q']
            first = False

        if len(orders_t_df) > 0 and not sell:
            q_array[-1] = previous

    data = {'id': id_array, 't': t_array, 'p': p_array, 'q': q_array}
    if order_id:
        data['scalable_order_id' if scalable else 'complex_order_id'] = complex_id_array

    step_orders_transformed = pd.DataFrame(data)
    return step_orders_transformed


class ParseEU(ParseData):
    def parse_data(self, day=None) -> ZonalScenario:
        periods = [i for i in range(1, 25)]
        step_orders = pd.read_csv('../implementation/data/raw_data/european/step_orders.csv')
        block_orders = pd.read_csv('../implementation/data/raw_data/european/block_orders.csv')
        complex_orders = pd.read_csv('../implementation/data/raw_data/european/complex_orders.csv')
        complex_step_orders = pd.read_csv('../implementation/data/raw_data/european/complex_step_orders.csv')
        scalable_complex_orders = pd.read_csv('../implementation/data/raw_data/european/scalable_complex_orders.csv')
        scalable_step_orders = pd.read_csv('../implementation/data/raw_data/european/scalable_step_orders.csv')

        step_orders_transformed = pd.concat([transform_step_orders(step_orders, periods, sell=True),
                                             transform_step_orders(step_orders, periods, sell=False)],
                                            ignore_index=True)

        complex_ids = complex_orders['id'].tolist()
        complex_dfs = []
        for complex_id in complex_ids:
            complex_dfs.append(
                transform_step_orders(complex_step_orders, periods, sell=True, order_id=complex_id))
            complex_dfs.append(
                transform_step_orders(complex_step_orders, periods, sell=False, order_id=complex_id))

        complex_step_orders_transformed = pd.concat(complex_dfs)

        scalable_ids = scalable_complex_orders['id'].tolist()
        scalable_dfs = []
        for scalable_id in scalable_ids:
            scalable_dfs.append(
                transform_step_orders(scalable_step_orders, periods, sell=True, order_id=scalable_id, scalable=True))
            scalable_dfs.append(
                transform_step_orders(scalable_step_orders, periods, sell=False, order_id=scalable_id, scalable=True))

        scalable_complex_step_orders_transformed = pd.concat(scalable_dfs)

        return ZonalScenario('EUDataset', periods, step_orders_transformed, block_orders,
                             complex_orders, complex_step_orders_transformed,
                             scalable_complex_orders, scalable_complex_step_orders_transformed)
