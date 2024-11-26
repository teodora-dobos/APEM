from collections import defaultdict
import pandas as pd

from src.data.parsing.scenario import Scenario


class DataConversion:
    """
    Convert bids following the US bidding language to bids expected in the Euphemia implementation.
    """

    def __init__(self, scenario: Scenario):
        self.df_buyers = scenario.df_buyers
        self.df_sellers = scenario.df_sellers
        self.periods = scenario.periods
        self.blocks_buyers = scenario.blocks_buyers
        self.blocks_sellers = scenario.blocks_sellers
        self.block_bids = None

    def compute_buyers_inelastic_bids(self) -> pd.DataFrame:
        """
        Generate block bids to encode inelastic demand.
        """
        info = defaultdict(dict)

        df_dict_records = self.df_buyers.to_dict(orient='records')
        count = 1
        for bid in df_dict_records:
            info[bid['buyer']][bid['period']] = -bid['inelastic_dem']
            info[bid['buyer']]['id'] = str(bid['buyer']) + str(count)
            count += 1

        df = pd.DataFrame.from_dict(info, orient='index').reset_index(drop=True)
        df = df.rename(columns={i: f'q{i}' for i in self.periods})
        df['block_type'] = 'normal'
        df['code_prm'] = pd.NA
        df['MAR'] = 1
        # set a large limit price such that the blocks are always accepted
        df['p'] = 10 ** 6

        columns = ['id', 'block_type', 'code_prm', 'p'] + [f'q{i}' for i in self.periods] + ['MAR']
        df = df[columns]
        return df

    def compute_buyers_elastic_bids(self) -> pd.DataFrame:
        """
        Generate step orders to encode price-elastic demand.
        """
        elastic_dem = [f'val{i}' for i in self.blocks_buyers] + [f'size{i}' for i in self.blocks_buyers]
        info = self.df_buyers[['buyer', 'period'] + elastic_dem]

        data = []
        buyers = self.df_buyers['buyer'].unique().tolist()
        for b in buyers:
            count = 1
            for i in self.blocks_buyers:
                buyer_info = info[info['buyer'] == b]

                order = {'id': str(b) + str(count),
                         't': buyer_info['period'].values[0] if not buyer_info.empty else None,
                         'p': buyer_info[f'val{i}'].values[0] if not buyer_info.empty else None,
                         'q': buyer_info[f'size{i}'].values[0] if not buyer_info.empty else None
                         }
                data.append(order)
                count += 1

        df = pd.DataFrame(data)
        return df

    def compute_sellers_bids(self):
        pass

    def set_block_bids(self) -> None:
        pass

    def set_step_orders(self) -> None:
        pass
