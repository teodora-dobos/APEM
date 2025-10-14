import pytest
from unittest.mock import MagicMock, patch
import pandas as pd
import networkx as nx
from collections import defaultdict

from apem.US_market_model.allocation.algorithms.nodal_clearing.dcopf import DCOPF
from apem.US_market_model.allocation.error import Error


# ---------- Minimal, valid scenario ----------
@pytest.fixture
def dummy_scenario():
    class DummyScenario:
        pass

    s = DummyScenario()

    # one period
    s.periods = [1]

    # tiny buyers table
    s.blocks_buyers = [1]
    s.df_buyers = pd.DataFrame(
        {
            "buyer": [1],
            "period": [1],
            "inelastic_dem": [0.0],
            "max_dem": [10.0],
            "val": [1.0],
            "size": [10.0],
        }
    )

    # tiny sellers table
    s.blocks_sellers = [1]
    s.df_sellers = pd.DataFrame(
        {
            "seller": [1],
            "period": [1],
            "no_load_cost": [0.0],
            "min_prod": [0.0],
            "max_prod": [10.0],
            "min_uptime": [1],
            "cost": [0.5],
            "size": [10.0],
        }
    )

    # 2-bus network with attributes B and F_max
    G = nx.Graph()
    G.add_node("n1")
    G.add_node("n2")
    G.add_edge("n1", "n2", B=1.0, F_max=100.0)
    s.network = G
    s.nodes_agents = {
        "n1": {"buyers": [1], "sellers": []},
        "n2": {"buyers": [], "sellers": [1]},
    }
    s.r_star = "n1"
    return s


@pytest.fixture
def dummy_config():
    class DummyConfig:
        relaxation = False

        def apply_to_model(self, model):
            pass

    return DummyConfig()


def test_dcopf_str():
    assert str(DCOPF()) == "DCOPF"


def test_compare_zonal_vs_final_allocation(tmp_path):
    z_alloc = MagicMock()
    f_alloc = MagicMock()
    z_alloc.u_st = {(1, 1): 1}
    f_alloc.u_st = {(1, 1): 0}
    z_alloc.y_st = {(1, 1): 2}
    f_alloc.y_st = {(1, 1): 3}
    z_alloc.y_stl = {(1, 1, 1): 1.0}
    f_alloc.y_stl = {(1, 1, 1): 1.5}

    dcopf = DCOPF()
    out = tmp_path / "compare.csv"
    dcopf.compare_zonal_vs_final_allocation(z_alloc, f_alloc, str(out))
    assert out.exists()
    txt = out.read_text()
    assert "u_st" in txt and "diff" in txt


def test_compute_redispatch_costs(tmp_path):
    z_alloc = MagicMock()
    f_alloc = MagicMock()
    z_alloc.y_stl = {(1, 1, 1): 1}
    f_alloc.y_stl = {(1, 1, 1): 2}
    z_alloc.u_st = {(1, 1): 1}
    f_alloc.u_st = {(1, 1): 2}

    dcopf = DCOPF()
    file = tmp_path / "costs.txt"
    dcopf.compute_redispatch_costs(
        z_alloc, f_alloc,
        seller_cost_dict={1: {(1, 1): 10}},
        seller_no_load_cost_dict={(1, 1): 5},
        periods=[1], blocks_sellers=[1], sellers=[1],
        file=str(file)
    )
    assert "Redispatch costs" in file.read_text()


def test_compute_redispatch_volumes(tmp_path):
    z_alloc = MagicMock()
    f_alloc = MagicMock()
    z_alloc.y_stl = {(1, 1, 1): 1}
    f_alloc.y_stl = {(1, 1, 1): 4}

    dcopf = DCOPF()
    file = tmp_path / "vols.txt"
    dcopf.compute_redispatch_volumes(
        z_alloc, f_alloc,
        periods=[1], blocks_sellers=[1], sellers=[1],
        file=str(file)
    )
    assert "Redispatch volumes" in file.read_text()


def test_add_redispatch_constraints_objective_minabsvol(dummy_scenario):
    model = MagicMock()
    # Return zero-by-default containers for any addVars(...) call
    model.addVars.side_effect = lambda *a, **kw: defaultdict(float)
    model.addConstrs.side_effect = lambda *a, **kw: None
    model.setObjective.side_effect = lambda *a, **kw: None

    zonal_alloc = MagicMock()
    zonal_alloc.y_stl = {(1, 1, 1): 0.0}

    # Provide abs_slack as real numbers for all (node, period) pairs used in quicksum
    abs_slack = {("n1", 1): 0.0, ("n2", 1): 0.0}

    dcopf = DCOPF()
    updated = dcopf.add_redispatch_constraints_objective(
        redispatch_type="MinAbsVolRD",
        model=model,
        scenario=dummy_scenario,
        y_stl={}, u_st={}, abs_slack=abs_slack,
        seller_cost_dict={}, seller_no_load_cost_dict={},
        zonal_allocation=zonal_alloc
    )
    assert updated is model


@patch("apem.US_market_model.allocation.algorithms.nodal_clearing.dcopf.gp.Model")
@patch("apem.US_market_model.allocation.algorithms.nodal_clearing.dcopf.GRB")
@patch("apem.US_market_model.allocation.algorithms.nodal_clearing.dcopf.preprocess_as_dict")
def test_solve_returns_error(mock_preproc, GRB, MockModel, dummy_scenario, dummy_config):
    from collections import defaultdict

    # Every preprocess dict access returns 0.0 by default
    mock_preproc.side_effect = lambda *a, **kw: defaultdict(float)

    # Mock Gurobi model: accept all calls; return zeros for any addVars access
    mock_model = MagicMock()
    mock_model.addConstr.side_effect = lambda *a, **kw: None
    mock_model.addConstrs.side_effect = lambda *a, **kw: None
    mock_model.addVars.side_effect = lambda *a, **kw: defaultdict(float)
    mock_model.setObjective.side_effect = lambda *a, **kw: None
    mock_model.optimize.side_effect = lambda *a, **kw: None
    mock_model.Status = 3  # infeasible
    MockModel.return_value = mock_model

    # Minimal constants used
    GRB.INFEASIBLE = 3
    GRB.BINARY = "BINARY"
    GRB.INFINITY = float("inf")

    dcopf = DCOPF()
    res = dcopf.solve(dummy_scenario, dummy_config)
    assert isinstance(res, Error)
