import pytest
from unittest.mock import MagicMock, patch
import pandas as pd
import networkx as nx
from collections import defaultdict

from apem.unit_based_model.allocation.algorithms.nodal_clearing.dcopf import DCOPF
from apem.unit_based_model.allocation.error import Error


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
        slack_penalty = 1234.0

        def apply_to_model(self, model):
            pass

    return DummyConfig()


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


@patch("apem.unit_based_model.allocation.algorithms.nodal_clearing.dcopf.gp.quicksum")
def test_add_redispatch_constraints_objective_minabsvol_uses_slack_penalty(mock_quicksum, dummy_scenario):
    mock_quicksum.side_effect = lambda terms: sum(terms)
    model = MagicMock()
    model.addVars.side_effect = lambda *a, **kw: defaultdict(float)
    model.addConstrs.side_effect = lambda *a, **kw: None
    model.setObjective.side_effect = lambda *a, **kw: None

    zonal_alloc = MagicMock()
    zonal_alloc.y_stl = {(1, 1, 1): 0.0}

    abs_slack = {("n1", 1): 2.0, ("n2", 1): 3.0}
    slack_penalty = 7.0

    dcopf = DCOPF()
    updated = dcopf.add_redispatch_constraints_objective(
        redispatch_type="MinAbsVolRD",
        model=model,
        scenario=dummy_scenario,
        y_stl={}, u_st={}, abs_slack=abs_slack,
        seller_cost_dict={}, seller_no_load_cost_dict={},
        zonal_allocation=zonal_alloc,
        slack_penalty=slack_penalty,
    )
    assert updated is model
    set_obj_args = model.setObjective.call_args[0]
    assert set_obj_args[0] == pytest.approx(slack_penalty * (2.0 + 3.0))


@patch("apem.unit_based_model.allocation.algorithms.nodal_clearing.dcopf.gp.Model")
@patch("apem.unit_based_model.allocation.algorithms.nodal_clearing.dcopf.GRB")
@patch("apem.unit_based_model.allocation.algorithms.nodal_clearing.dcopf.preprocess_as_dict")
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


@patch("apem.unit_based_model.allocation.algorithms.nodal_clearing.dcopf.gp.Model")
@patch("apem.unit_based_model.allocation.algorithms.nodal_clearing.dcopf.GRB")
@patch("apem.unit_based_model.allocation.algorithms.nodal_clearing.dcopf.gp.quicksum")
@patch("apem.unit_based_model.allocation.algorithms.nodal_clearing.dcopf.preprocess_as_dict")
def test_solve_uses_configured_slack_penalty_in_objective(
    mock_preproc, mock_quicksum, GRB, MockModel, dummy_scenario, dummy_config
):
    mock_preproc.side_effect = lambda *a, **kw: defaultdict(float)
    mock_quicksum.side_effect = lambda terms: sum(terms)

    def _addvars(*args, **kwargs):
        name = kwargs.get("name", "")
        if name == "abs_slack_vt":
            return defaultdict(lambda: 1.0)
        return defaultdict(float)

    mock_model = MagicMock()
    mock_model.addConstr.side_effect = lambda *a, **kw: None
    mock_model.addConstrs.side_effect = lambda *a, **kw: None
    mock_model.addVars.side_effect = _addvars
    mock_model.setObjective.side_effect = lambda *a, **kw: None
    mock_model.optimize.side_effect = lambda *a, **kw: None
    mock_model.Status = 3
    MockModel.return_value = mock_model

    GRB.INFEASIBLE = 3
    GRB.BINARY = "BINARY"
    GRB.INFINITY = float("inf")
    GRB.MAXIMIZE = "MAXIMIZE"
    GRB.MINIMIZE = "MINIMIZE"

    dcopf = DCOPF()
    res = dcopf.solve(dummy_scenario, dummy_config)
    assert isinstance(res, Error)

    objective, sense = mock_model.setObjective.call_args[0]
    expected_penalty_term = -dummy_config.slack_penalty * len(dummy_scenario.network.nodes) * len(dummy_scenario.periods)
    assert objective == pytest.approx(expected_penalty_term)
    assert sense == GRB.MAXIMIZE


@patch("apem.unit_based_model.allocation.algorithms.nodal_clearing.dcopf.gp.Model")
@patch("apem.unit_based_model.allocation.algorithms.nodal_clearing.dcopf.GRB")
@patch("apem.unit_based_model.allocation.algorithms.nodal_clearing.dcopf.preprocess_as_dict")
def test_solve_error_writes_status_message_csv(mock_preproc, GRB, MockModel, dummy_scenario, dummy_config, tmp_path):
    mock_preproc.side_effect = lambda *a, **kw: defaultdict(float)

    mock_model = MagicMock()
    mock_model.addConstr.side_effect = lambda *a, **kw: None
    mock_model.addConstrs.side_effect = lambda *a, **kw: None
    mock_model.addVars.side_effect = lambda *a, **kw: defaultdict(float)
    mock_model.setObjective.side_effect = lambda *a, **kw: None
    mock_model.optimize.side_effect = lambda *a, **kw: None
    mock_model.Status = 3
    MockModel.return_value = mock_model

    GRB.INF_OR_UNBD = 4
    GRB.INFEASIBLE = 3
    GRB.UNBOUNDED = 5
    GRB.INTERRUPTED = 6
    GRB.BINARY = "BINARY"
    GRB.INFINITY = float("inf")

    out = tmp_path / "dcopf_error.csv"
    dcopf = DCOPF()
    res = dcopf.solve(dummy_scenario, dummy_config, results_file=str(out))

    assert isinstance(res, Error)
    assert out.exists()
    df = pd.read_csv(out)
    assert list(df.columns) == ["status", "message"]
    assert int(df.loc[0, "status"]) == GRB.INFEASIBLE
    assert "infeasible" in str(df.loc[0, "message"]).lower()

