import pytest
import pandas as pd
import networkx as nx
from unittest.mock import MagicMock, patch

from apem.US_market_model.allocation.algorithms.zonal_clearing.zonal_NTC import Zonal_NTC
from apem.US_market_model.data.parsing.scenario import Scenario


@pytest.fixture
def base_scenario(tmp_path):
    """Minimal nodal scenario."""

    class DummyScenario(Scenario):
        pass

    # two nodes with lat/lon and one connecting edge
    G = nx.Graph()
    G.add_node("n1")
    G.add_node("n2")
    G.add_edge("n1", "n2", F_max=100.0, B=5.0)

    df_sellers = pd.DataFrame({
        "seller": [1, 2],
        "node": ["n1", "n2"],
        "period": [1, 1]
    })
    df_buyers = pd.DataFrame({
        "buyer": [10, 11],
        "node": ["n1", "n2"],
        "period": [1, 1]
    })

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
        r_star="n1"
    )


def test_str_repr():
    ntc = Zonal_NTC("zonal_DE3", 0.8)
    assert str(ntc) == "Zonal_NTC"
    assert ntc.zonal_configuration == "zonal_DE3"
    assert pytest.approx(ntc.factor) == 0.8


@patch("apem.US_market_model.allocation.algorithms.zonal_clearing.zonal_NTC.node_zone_mapper")
@patch("apem.US_market_model.allocation.algorithms.zonal_clearing.zonal_NTC.os.makedirs")
@patch("apem.US_market_model.allocation.algorithms.zonal_clearing.zonal_NTC.pd.DataFrame.to_csv")
def test_create_zonal_scenario(mock_to_csv, mock_makedirs, mock_mapper, base_scenario):
    """Check zonal scenario is created and network aggregated correctly."""
    # Make both nodes map to distinct zones
    mock_mapper.side_effect = lambda config, lat, lon: "Z1" if lat < 50.5 else "Z2"

    ntc = Zonal_NTC("zonal_DE3", factor=0.5)
    zonal_scenario = ntc.create_zonal_scenario_NTC(base_scenario)

    # verify folder creation + CSV output called
    mock_makedirs.assert_called()
    mock_to_csv.assert_called()

    # verify we now have 2 zones and 1 edge aggregated
    assert sorted(zonal_scenario.network.nodes) == ["Z1", "Z2"]
    assert ("Z1", "Z2") in zonal_scenario.network.edges
    data = zonal_scenario.network["Z1"]["Z2"]
    assert data["F_max"] == pytest.approx(100.0 * 0.5)
    assert data["B"] == 5.0

    # ensure scenario name and structure preserved
    assert zonal_scenario.name == base_scenario.name
    assert "Z1" in zonal_scenario.nodes_agents and "Z2" in zonal_scenario.nodes_agents


@patch("apem.US_market_model.allocation.algorithms.zonal_clearing.zonal_NTC.node_zone_mapper")
@patch("apem.US_market_model.allocation.algorithms.zonal_clearing.zonal_NTC.os.makedirs")
@patch("apem.US_market_model.allocation.algorithms.zonal_clearing.zonal_NTC.pd.DataFrame.to_csv")
def test_create_zonal_scenario_single_zone(mock_to_csv, mock_makedirs, mock_mapper, base_scenario):
    """Case where all nodes map to the same zone (no edges)."""
    mock_mapper.return_value = "Z1"

    ntc = Zonal_NTC("zonal_DE1", factor=0.9)
    zonal_scenario = ntc.create_zonal_scenario_NTC(base_scenario)

    assert list(zonal_scenario.network.nodes) == ["Z1"]
    assert len(zonal_scenario.network.edges) == 0
    assert "Z1" in zonal_scenario.nodes_agents
    mock_to_csv.assert_called()


@patch("apem.US_market_model.allocation.algorithms.zonal_clearing.zonal_NTC.DCOPF")
@patch.object(Zonal_NTC, "create_zonal_scenario_NTC")
def test_solve_calls_dcopf(mock_create, mock_dcopf, base_scenario):
    """Ensure Zonal_NTC.solve delegates to DCOPF.solve."""
    mock_zonal = MagicMock()
    mock_create.return_value = mock_zonal

    mock_dcopf_instance = MagicMock()
    mock_alloc = MagicMock()
    mock_dcopf_instance.solve.return_value = mock_alloc
    mock_dcopf.return_value = mock_dcopf_instance

    cfg = MagicMock()
    ntc = Zonal_NTC()
    zonal_scenario, result = ntc.solve(base_scenario, cfg, results_file="r.csv")

    mock_create.assert_called_once_with(base_scenario=base_scenario)
    mock_dcopf_instance.solve.assert_called_once()
    assert zonal_scenario is mock_zonal
    assert result is mock_alloc
