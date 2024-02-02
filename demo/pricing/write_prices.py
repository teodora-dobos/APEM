def write_prices(p_vt, gamma_vwt, file_prices, nodes, network, periods):
    file = open(file_prices, 'w+')
    file.write("Format: p[node, period]\n")
    for v in nodes:
        for t in periods:
            file.write(f'p[{v},{t}] = {round(p_vt[v, t].X, 2)}\n')
    for v in nodes:
        for w in list(network.neighbors(v)):
            for t in periods:
                file.write(f'gamma[{v}, {w}, {t}] = {round(gamma_vwt[v, w, t].X, 2)}\n')
    file.close()
