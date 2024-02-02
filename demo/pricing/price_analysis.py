class PriceAnalysis:

    def __init__(self, pricing, allocation, market_data):
        self.pricing = pricing
        self.allocation = allocation
        self.market_data = market_data

    def compute_mwps(self, allocation, df_buyers, df_sellers, periods, blocks_buyers, blocks_sellers, mwps_file):
        f = open(mwps_file, 'w+')
        buyers = df_buyers['buyer'].unique().tolist()
        sellers = df_sellers['seller'].unique().tolist()
        mwps_buyers, mwps_sellers = 0, 0

        for b in buyers:
            mwp_b = -sum(
                df_buyers[(df_buyers['buyer'] == b) & (df_buyers['period'] == t)]['val' + str(l)].iloc[0] *
                allocation.x_btl[f'x_btl[{b, t, l}]']
                for t in periods for l in range(1, blocks_buyers + 1)
            ) + sum(
                self.pricing.node_prices[
                    df_buyers[(df_buyers['buyer'] == b) & (df_buyers['period'] == t)]['node'].iloc[0], t] *
                allocation.x_btl[f'x_btl[{b, t, l}]']
                for t in periods for l in range(1, blocks_buyers + 1)
            )

            if mwp_b > 0:
                f.write(f"Buyer b = {b} has MWPs = {mwp_b}\n")
                mwps_buyers += mwp_b

        for s in sellers:
            mwp_s = -sum(
                self.pricing.node_prices[
                    df_sellers[(df_sellers['seller'] == s) & (df_sellers['period'] == t)]['node'].iloc[
                        0], t] * allocation.y_st[f'y_st[{s, t}]'] for t in periods
            ) + sum(df_sellers[(df_sellers['seller'] == s) & (df_sellers['period'] == t)][
                        'cost' + str(l)].iloc[0] * allocation.y_stl[f'y_stl[{s, t, l}]']
                    for t in periods for l in range(1, blocks_sellers + 1)
                    ) + \
                    sum(df_sellers[(df_sellers['seller'] == s) & (df_sellers['period'] == t)][
                            'no_load_cost'].iloc[0] * allocation.u_st[f'u_st[{s, t}]']
                        for t in periods
                        )
            if mwp_s > 0:
                f.write(f"Seller s = {s} has MWPs = {mwp_s}\n")
                mwps_sellers += mwp_s

        mwps = mwps_buyers + mwps_sellers
        f.write(f"Total MWPs = {mwps}")
        f.close()

        return mwps
