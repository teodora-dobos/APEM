def write_prices(file_prices, pricing, scenario):
    if pricing.status == 1:
        p_vt = pricing.node_prices
        gamma_vwt = pricing.line_congestion_prices
        network = scenario.network
        nodes = network.nodes
        periods = scenario.periods

        file = open(file_prices, 'w+')
        file.write("Format: p[node, period]\n")
        for v in nodes:
            for t in periods:
                file.write(f'p[{v},{t}] = {round(p_vt[v, t], 2)}\n')
        for v in nodes:
            for w in list(network.neighbors(v)):
                for t in periods:
                    file.write(f'gamma[{v}, {w}, {t}] = {round(gamma_vwt[v, w, t], 2)}\n')
        file.close()


def write_prices_failure(file_prices, name, status):
    file = open(file_prices, 'w+')
    file.write(f'{name} pricing error with code {status}')
    file.close()
