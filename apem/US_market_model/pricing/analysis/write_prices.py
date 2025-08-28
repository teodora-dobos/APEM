import pandas as pd


def write_prices(file_prices, pricing, scenario) -> None:
    """
    Creates a CSV with columns: node, period, and price.
    """
    p_vt = pricing.node_prices
    network = scenario.network
    nodes = network.nodes
    periods = scenario.periods

    data = []
    for v in nodes:
        for t in periods:
            data.append({"node": v, "period": t, "price": round(p_vt[v, t], 2)})

    df = pd.DataFrame(data, columns=["node", "period", "price"])
    df.to_csv(file_prices, index=False)


def write_prices_failure(file_prices, name, status) -> None:
    """
    Creates a CSV with an error message.
    """
    df = pd.DataFrame([{"error_message": f'{name} pricing error with code {status}'}])
    df.to_csv(file_prices, index=False)
