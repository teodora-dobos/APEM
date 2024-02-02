from demo.data.parse_ieee_rts import parse_ieee_rts_data


def parse_data(dataset):
    if dataset == 'IEEE_RTS':
        return parse_ieee_rts_data()