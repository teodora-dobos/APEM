import pandas as pd
import networkx as nx
import pytest
from unittest.mock import MagicMock, patch

from apem.US_market_model.allocation.algorithms.zonal_clearing.zonal_NTC_independent import (
    Zonal_NTC_independent,
)
from apem.US_market_model.data.parsing.scenario import Scenario


@pytest.fixture
def base_scenario_with_parallel(tmp_path):
    """Minimal nodal scenario with two parallel cross-zonal lines."""

    class DummyScenario(Scenario):
        pass

    G = nx.MultiGraph()
    G.add_node("n1")
    G.add_node("n2")
    # two parallel edges between n1 and n2
    G.add_edge("n1", "n2", F_max=50.0, B=5.0)
    G.add_edge("n1", "n2", F_max=30.0, B=4.0)

    df_sellers = pd.DataFrame(
        {"seller": [1, 2], "node": ["n1", "n2"], "period": [1, 1]}
    )
    df_buyers = pd.DataFrame(
        {"buyer": [10, 11], "node": ["n1", "n2"], "period": [1, 1]}
    )

    nodes_agents = {
        "n1": {"latitude": 50.0, "longitude": 10.0},
        "n2": {"latitude": 51.0, "longitude": 11.0},
    }

    return Scenario(
        name="test_case",
        df_buyers=df_buyers,
        df_sellers=df_sellers,
        network=G,
        nodes_agents=nodes_agents,
        periods=[1],
        blocks_buyers=range(0, 0),
        blocks_sellers=range(0, 0),
        r_star="n1",
    )


@patch("apem.US_market_model.allocation.algorithms.zonal_clearing.zonal_NTC_independent.node_zone_mapper")
@patch("apem.US_market_model.allocation.algorithms.zonal_clearing.zonal_NTC_independent.os.makedirs")
@patch("apem.US_market_model.allocation.algorithms.zonal_clearing.zonal_NTC_independent.pd.DataFrame.to_csv")
def test_create_zonal_scenario_keeps_parallel_lines(mock_to_csv, mock_makedirs, mock_mapper, base_scenario_with_parallel):
    mock_mapper.side_effect = lambda config, lat, lon: "Z1" if lat < 50.5 else "Z2"

    ntc = Zonal_NTC_independent("zonal_DE3", factor=0.5)
    zonal_scenario = ntc.create_zonal_scenario_NTC(base_scenario_with_parallel)

    assert isinstance(zonal_scenario.network, nx.MultiGraph)
    assert zonal_scenario.network.number_of_edges() == 2
    # capacities scaled independently
    capacities = sorted([data["F_max"] for _, _, _, data in zonal_scenario.network.edges(keys=True, data=True)])
    assert capacities == [15.0, 25.0]
    susceptances = sorted([data["B"] for _, _, _, data in zonal_scenario.network.edges(keys=True, data=True)])
    assert susceptances == [4.0, 5.0]


@patch("apem.US_market_model.allocation.algorithms.zonal_clearing.zonal_NTC_independent.DCOPF")
@patch.object(Zonal_NTC_independent, "create_zonal_scenario_NTC")
def test_solve_uses_dcopf_with_multigraph(mock_create, mock_dcopf, base_scenario_with_parallel):
    mock_zonal = MagicMock()
    mock_create.return_value = mock_zonal

    mock_dcopf_instance = MagicMock()
    mock_alloc = MagicMock()
    mock_alloc.TransmissionNetworkAllocation.f_vwkt = {"edge": 1}
    mock_dcopf_instance.solve.return_value = mock_alloc
    mock_dcopf.return_value = mock_dcopf_instance

    cfg = MagicMock()
    ntc = Zonal_NTC_independent()
    zonal_scenario, result = ntc.solve(base_scenario_with_parallel, cfg, results_file="r.csv")

    mock_create.assert_called_once_with(base_scenario=base_scenario_with_parallel)
    mock_dcopf_instance.solve.assert_called_once()
    assert zonal_scenario is mock_zonal
    assert result is mock_alloc
