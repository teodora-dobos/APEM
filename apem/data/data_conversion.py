import os
from collections import defaultdict
from typing import Tuple, List

import pandas as pd
import hashlib
import json
import numpy as np

from apem.data.parsing.scenario import Scenario
from apem.utils.paths import RAW_DATA_DIR, ensure_dir


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
        Generate block orders to encode price-inelastic demand.
        Create a block order for each buyer and set the volume for period t to the price-inelastic demand for period t.
        Set MAR to 1 and the limit price to a very large value which guarantees that the block will always be accepted.
        """
        info = defaultdict(dict)

        df_dict_records = self.df_buyers.to_dict(orient='records')
        for bid in df_dict_records:
            info[bid['buyer']][bid['period']] = -bid['inelastic_dem']
            info[bid['buyer']]['id'] = 'b' + str(bid['buyer'])

        df = pd.DataFrame.from_dict(info, orient='index').reset_index(drop=True)
        df = df.rename(columns={i: f'q{i}' for i in self.periods})
        df['block_type'] = 'normal'
        df['code_prm'] = pd.NA
        df['MAR'] = 1
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
            for t in self.periods:
                buyer_info = info[(info['buyer'] == b) & (info['period'] == t)]
                if len(buyer_info) == 0:
                    continue

                for i in self.blocks_buyers:
                    order = {'id': 'b' + str(b) + 't' + str(t) + 'l' + str(i),
                             't': t,
                             'p': buyer_info[f'val{i}'].values[0],
                             'q': -buyer_info[f'size{i}'].values[0]
                             }
                    data.append(order)
                    count += 1

        df_step_orders = pd.DataFrame(data)
        print(df_step_orders)
        return df_step_orders

    def generate_no_min_uptime_bids(self) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Generate scalable complex orders and associated sub-orders to encode the bids of the sellers that fulfill
        the following criteria:
            - minimum uptime = 0
            - minimum production level > 0
            - no-load cost = 0
        Assume cost1 is the smallest marginal cost.
        Create a scalable complex order for each seller.
        For all periods t, set MAP_t to the minimum production level in period t.
        Create associated step orders based on the supply curves.
        """
        sellers = self.df_sellers[(self.df_sellers['min_uptime'].isin([0, 1])) & (self.df_sellers['min_prod'] > 0) &
                                  (self.df_sellers['no_load_cost'] == 0)]['seller'].unique().tolist()
        scalable_orders, scalable_step_orders, step_orders = [], [], []
        for s in sellers:
            suborders_ids = []
            scalable_id = 's' + str(s) + 'MAP'

            for t in self.periods:
                id_step_min_prod = 's' + str(s) + 'min_prod_t' + f'{t}'
                seller_info = self.df_sellers[(self.df_sellers['seller'] == s) & (self.df_sellers['period'] == t)]

                # check if s submitted bids for the current period
                min_prod_t = seller_info['min_prod'].values[0] if not seller_info['min_prod'].empty else 0
                if min_prod_t == 0:
                    continue

                scalable_step_order_min = {'id': id_step_min_prod,
                                           'scalable_order_id': scalable_id,
                                           't': t,
                                           'p': seller_info['cost1'].values[0],
                                           'q': min_prod_t
                                           }
                suborders_ids.append(id_step_min_prod)
                scalable_step_orders.append(scalable_step_order_min)

                for block in self.blocks_sellers:
                    id_step_block = 's' + str(s) + 't' + f'{t}' + 'l' + f'{block}'
                    q = seller_info[f'size{block}'].values[0]

                    if block == 1:
                        q = seller_info[f'size{block}'].values[0] - min_prod_t

                    if q == 0:
                        continue

                    scalable_step_order_block = {'id': id_step_block,
                                                 'scalable_order_id': scalable_id,
                                                 't': t,
                                                 'p': seller_info[f'cost{block}'].values[0],
                                                 'q': q
                                                 }

                    suborders_ids.append(id_step_block)
                    scalable_step_orders.append(scalable_step_order_block)

            scalable_order = {'id': scalable_id,
                              'step_orders': suborders_ids,
                              'fixed_term': 0,
                              'condition': 'MIC',
                              'load_gradient': pd.NA,
                              **{f'MAP{t}': self.df_sellers[
                                  (self.df_sellers['seller'] == s) & (self.df_sellers['period'] == t)][
                                  'min_prod'].values[0] if not
                              self.df_sellers[(self.df_sellers['seller'] == s) & (self.df_sellers['period'] == t)][
                                  'min_prod'].empty else 0
                                 for t in self.periods}
                              }
            scalable_orders.append(scalable_order)

        df_scalable_orders = pd.DataFrame(scalable_orders)
        df_scalable_step_orders = pd.DataFrame(scalable_step_orders)

        return df_scalable_orders, df_scalable_step_orders

    def generate_min_uptime_bids(self, reduce_linked_blocks: bool) -> pd.DataFrame:
        """
        Generate block orders to encode the bids of the sellers that fulfill the following criteria:
            - minimum uptime > 1
            - minimum production level > 0
            - no-load cost >= 0
        Assume cost1 is the smallest marginal cost.
        """
        sellers = self.df_sellers[(self.df_sellers['min_uptime'] > 1) & (self.df_sellers['min_prod'] > 0)]['seller'].unique().tolist()
        min_uptime_values = self.df_sellers[self.df_sellers['min_uptime'] > 1]['min_uptime'].unique().tolist()

        # retrieve patterns that encode in which periods a seller is committed
        patterns = {}
        for val in min_uptime_values:
            file_path = RAW_DATA_DIR / "euphemia" / "patterns" / f"{val}.txt"
            patterns_val = []

            try:
                with open(file_path, 'r') as file:
                    for line in file:
                        row = list(map(int, line.strip().split()))
                        patterns_val.append(row)
                patterns[val] = patterns_val
            except FileNotFoundError:
                print(f"Error: The file '{file_path}' does not exist. Call generate_write_patterns().")

        print("Pattern retrieval finished")
        block_bids = []
        for s in sellers:
            sellers_general_info = self.df_sellers[self.df_sellers['seller'] == s]
            min_uptime = sellers_general_info['min_uptime'].values[0]
            min_cost = sellers_general_info['cost1'].values[0]
            exclusive_id = f's{s}exclusive'
            count = 1
            seen_time_commitments = set()

            for pattern in patterns[min_uptime]:
                # create a vector in which the value at index i is 1 if the pattern indicates that the seller is
                # committed in period i + 1 and 0 otherwise
                time_commitment = []
                for value in pattern:
                    if value != 1:
                        time_commitment.extend([1] * value)
                    else:
                        time_commitment.append(0)

                if sum(time_commitment) == 0:
                    continue

                # Check if pattern was already added as block order
                tc_tuple = tuple(time_commitment)
                if tc_tuple in seen_time_commitments:
                    continue  # already processed this time pattern
                seen_time_commitments.add(tc_tuple)

                # Support for orders with no-load cost > 0
                active_hours = sum(time_commitment)  # k
                min_prod = sellers_general_info['min_prod'].values[0]
                no_load = sellers_general_info['no_load_cost'].values[0]
                min_cost = sellers_general_info['cost1'].values[0]

                pattern_price = min_cost  # c_min,s
                if no_load > 0 and active_hours * min_prod > 0:
                    pattern_price += no_load / (active_hours * min_prod)

                bid_p = {
                    'id': f's{s}pattern{count}',
                    'block_type': 'exclusive',
                    'code_prm': exclusive_id,
                    'p': pattern_price,
                    **{
                        f'q{k}': (
                            self.df_sellers[
                                (self.df_sellers['seller'] == s) & (self.df_sellers['period'] == k)
                                ]['min_prod'].iloc[0]
                            if not self.df_sellers[
                                (self.df_sellers['seller'] == s) & (self.df_sellers['period'] == k)
                                ]['min_prod'].empty and time_commitment[k - 1] == 1
                            else 0
                        )
                        for k in self.periods
                    },
                    'MAR': 1
                }

                has_positive_q = any(value > 0 for key, value in bid_p.items() if key.startswith('q'))

                if has_positive_q:
                    block_bids.append(bid_p)
                else:
                    continue

                print(f"Exclusive blocks finished - Seller {s} - Pattern {pattern}")

                self.add_linked_block_orders(time_commitment, s, count, block_bids, reduce_orders=reduce_linked_blocks)

                count += 1

        df_block_orders = pd.DataFrame(block_bids)
        print(df_block_orders)
        return df_block_orders

    def generate_patterns(self, min_uptime: int) -> List[List[int]]:
        """
        Generate all possible patterns that encode in which periods a seller with minimum uptime min_uptime is committed.
        """
        T = len(self.periods)
        M = [1] + list(range(min_uptime, T + 1))

        dp = [[] for _ in range(T + 1)]
        dp[0] = [[]]

        for i in range(1, T + 1):  # dp[i]: all compositions of the segment i using lengths from M
            for m in M:
                if i >= m:
                    for combination in dp[i - m]:
                        dp[i].append(combination + [m])

        return dp[T]

    def generate_contiguous_patterns(self, min_uptime: int) -> List[List[int]]:
        """
        Generate all possible patterns that encode in which periods a seller with minimum uptime min_uptime is committed
        given there is only one start and one stop of the production unit.
        """
        T = len(self.periods)
        patterns: List[List[int]] = []

        for start_off in range(0, T - min_uptime + 1):  # 1s before ON period
            for on_len in range(min_uptime, T - start_off + 1):  # length of ON period
                end_off = T - start_off - on_len  # 1s after ON period

                pattern = [1] * start_off
                pattern += [on_len]
                pattern += [1] * end_off

                patterns.append(pattern)

        return patterns

    def add_linked_block_orders(self, time_commitment, s, count, block_bids, reduce_orders: bool):
        # --- reduce orders by putting all time periods in one linked block instead of multiple linked blocks with each one q != 0 ---
        if reduce_orders:
            for block in self.blocks_sellers:
                id_block = f's{s}pattern{count}l{block}'
                q_dict = {f'q{k}': 0 for k in self.periods}
                p_block = None

                # Fill right q for each period for this price step
                for t in self.periods:
                    if time_commitment[t - 1] == 0:
                        continue

                    seller_info = self.df_sellers[
                        (self.df_sellers['seller'] == s) & (self.df_sellers['period'] == t)
                        ]

                    q = seller_info[f'size{block}'].values[0]
                    if block == 1:
                        q -= seller_info['min_prod'].values[0]

                    if q == 0:
                        continue

                    q_dict[f'q{t}'] = q
                    p_block = p_block or seller_info[f'cost{block}'].values[0]

                # Create only one order per price step if there is a q != 0 for at least one period
                if any(q_dict.values()):
                    bid_p = {
                        'id': id_block,
                        'block_type': 'linked',
                        'code_prm': f's{s}pattern{count}',
                        'p': p_block,
                        **q_dict,
                        'MAR': 0
                    }
                    block_bids.append(bid_p)

        # --- Add one linked block order for each active period and price step ---
        else:
            for t in self.periods:
                if time_commitment[t - 1] == 0:
                    continue

                seller_info = self.df_sellers[(self.df_sellers['seller'] == s) & (self.df_sellers['period'] == t)]

                for block in self.blocks_sellers:
                    id_block_t = f's{s}pattern{count}t{t}l{block}'
                    q = seller_info[f'size{block}'].values[0]

                    if block == 1:
                        q = seller_info[f'size{block}'].values[0] - seller_info['min_prod'].values[0]

                    if q == 0:
                        continue

                    bid_p = {'id': id_block_t,
                             'block_type': 'linked',
                             'code_prm': f's{s}pattern{count}',
                             'p': seller_info[f'cost{block}'].values[0],
                             **{f'q{k}': q if k == t else 0 for k in self.periods},
                             'MAR': 0
                             }

                    block_bids.append(bid_p)


    def generate_write_patterns(self, use_contiguous_patterns: bool) -> None:
        """
        Generate and write all patterns in .txt files.
        """
        min_uptimes = range(2, 25)
        path = RAW_DATA_DIR / "euphemia" / "patterns"
        ensure_dir(path)
        for min_uptime in min_uptimes:
            file_name = path / f'{min_uptime}.txt'
            patterns = self.generate_contiguous_patterns(min_uptime) if use_contiguous_patterns else self.generate_patterns(min_uptime)
            with open(file_name, 'w') as f:
                for p in patterns:
                    row = ' '.join(map(str, p))
                    f.write(row + '\n')

    """
    Generate a stable hash for a *single* block
    
    The hash must uniquely identify a block by the attributes that
    are relevant for Euphemia's optimisation: block type, the 24‑hour
    quantity vector, price and MAR.  Seller/buyer IDs are *not* part
    of the hash because they do not influence the market clearing.
    We round numerical values to avoid hash instability due to tiny
    floating‑point noise.
    """
    def block_signature(self, row: pd.Series) -> str:
        qty_cols = [c for c in row.index if c.startswith("q")]
        tup = (
            row["block_type"],
            tuple(round(float(row[c]), 6) for c in qty_cols),  # quantity vector
            round(float(row["p"]), 4),  # price in €/MWh
            round(float(row["MAR"]), 4),  # minimum acceptance ratio
        )
        # Short but collision‑resistant fingerprint (SHA‑1 over JSON dump)
        return hashlib.sha1(json.dumps(tup).encode()).hexdigest()

    """
    Lossless aggregation of *identical* linked‑block chains
    
    A linked chain is a rooted tree: one exclusive parent order plus
    zero or more linked children.  Two chains are considered identical
    (and thus mergeable) if every node (block) in both trees has an
    identical signature and the tree topology is the same.

    After merging we:
      • sum the quantities of identical blocks,
      • adjust MAR of the parent (MAR=1/n),
      • concatenate the original IDs so that we can still trace them,
      • update the children so their `code_prm` points to the *new*
        parent ID.
    """
    def compress_linked(self, df: pd.DataFrame) -> pd.DataFrame:
        qty_cols = [c for c in df.columns if c.startswith("q")]

        # 1) Determine the parent ID for every row:
        #    – exclusive blocks reference themselves,
        #    – linked blocks reference the column `code_prm`.
        df["parent_id"] = np.where(
            df["block_type"] == "exclusive", df["id"], df["code_prm"]
        )

        # 2) Build a mapping  Parent‑ID → [child‑IDs]  (only linked rows)
        children_map = (
            df[df["block_type"] == "linked"].groupby("parent_id")["id"].apply(list).to_dict()
        )

        # 3) Build the per‑block signature dict  {order_id: signature}
        sig_series = df.apply(self.block_signature, axis=1)
        blk_sig = dict(zip(df["id"], sig_series))

        def chain_sig(chain: str):
            """Recursively compute the signature of the entire chain below."""
            return (
                blk_sig[chain],
                tuple(sorted(chain_sig(c) for c in children_map.get(chain, [])))
            )

        # All roots = exclusive blocks (one per chain)
        roots = df.loc[df["block_type"] == "exclusive", "id"].tolist()
        chain_sigs = {r: chain_sig(r) for r in roots}

        # 4) Group roots whose *full chain* signatures are identical
        buckets: dict[tuple, list[str]] = defaultdict(list)
        for rid, sig in chain_sigs.items():
            buckets[sig].append(rid)

        merged_rows: list[pd.Series] = []
        for root_ids in buckets.values():
            # Collect every order ID in this chain family (roots + children)
            all_ids = root_ids + sum([children_map.get(r, []) for r in root_ids], [])
            sub = df[df["id"].isin(all_ids)]

            # ---- Merge the root (exclusive) blocks ---------------------
            p_rows = sub[sub["block_type"] == "exclusive"]
            parent = p_rows.iloc[0].copy()
            parent[qty_cols] = p_rows[qty_cols].sum()
            parent["MAR"] = (
                1 / len(p_rows)
                if (p_rows["MAR"] == 1).all()
                else (p_rows["MAR"] * p_rows[qty_cols].sum(axis=1)).sum()
                     / p_rows[qty_cols].sum().sum()
            )
            parent["id"] = "+".join(p_rows["id"])
            parent_new_id = parent["id"]  # remember for children
            merged_rows.append(parent)

            # ---- Merge the children (group by identical qty+price+MAR) ---
            linked_rows = sub[sub["block_type"] == "linked"]
            for (_qty_price_mar, child_grp) in linked_rows.groupby(qty_cols + ["p", "MAR"]):
                kid = child_grp.iloc[0].copy()
                kid[qty_cols] = child_grp[qty_cols].sum()
                kid["id"] = "+".join(child_grp["id"])
                kid["code_prm"] = parent_new_id  # update parent reference
                merged_rows.append(kid)

        # Drop helper column before returning
        return pd.DataFrame(merged_rows).drop(columns="parent_id")

    def set_block_bids(self) -> None:
        pass

    def set_step_orders(self) -> None:
        pass
