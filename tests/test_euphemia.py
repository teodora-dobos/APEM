from types import SimpleNamespace
from unittest.mock import patch

import gurobipy as gp
import pandas as pd
import pytest

from apem.order_book_based_model.euphemia.data.conversion.data_conversion import DataConversion
from apem.order_book_based_model.euphemia.data.parsing.parse_eu import (
    ParseOrderBook,
    parse_fb_constraints,
    parse_fb_ptdf,
    transform_step_orders,
)
from apem.order_book_based_model.euphemia.enums.cut_types import CutTypes
from apem.order_book_based_model.euphemia.enums.datasets import OrderBookBased_Datasets
from apem.order_book_based_model.euphemia.euphemia_config import EuphemiaConfig
from apem.order_book_based_model.euphemia.master_problem.master_problem import MasterProblem
from apem.order_book_based_model.euphemia.pricing.price_determination_subproblem import PriceSubproblem
from apem.order_book_based_model.euphemia.runner import solve_euphemia


def _dummy_conversion(periods=(1, 2, 3, 4)):
    scenario = SimpleNamespace(
        df_buyers=pd.DataFrame(),
        df_sellers=pd.DataFrame(),
        periods=list(periods),
        blocks_buyers=[1],
        blocks_sellers=[1],
    )
    return DataConversion(scenario)


def _base_pricing_master(network_model: str) -> SimpleNamespace:
    return SimpleNamespace(
        M=10**6,
        current_alloc_solution={},
        epsilon=1e-4,
        zonal_pricing_enabled=True,
        zones=["Z1", "Z2"],
        periods=[1],
        price_lower_bound=-500,
        price_upper_bound=4000,
        network_constraints_enabled=True,
        network_model=network_model,
        atc_index=[],
        atc_cap={},
        f_atc={},
        fb_index=[],
        fb_lb={},
        fb_ram={},
        fb_ptdf_map={},
        net_position={},
    )


def test_apply_overrides_updates_known_fields(monkeypatch):
    """Known euphemia overrides should be applied to config attributes."""
    monkeypatch.setattr(EuphemiaConfig, "set_dataset", lambda self, dataset: None)
    config = EuphemiaConfig()

    overrides = {
        "max_iterations": 7,
        "reinsertion_max_iterations": 3,
        "max_prb_reinsertion_attempts": 5,
        "output_flag": 1,
        "time_limit": 120,
        "mip_gap": 1e-5,
    }
    config.apply_overrides(overrides)

    assert config.max_iterations == 7
    assert config.reinsertion_max_iterations == 3
    assert config.max_prb_reinsertion_attempts == 5
    assert config.output_flag == 1
    assert config.time_limit == 120
    assert config.mip_gap == 1e-5


def test_apply_overrides_rejects_unknown_keys(monkeypatch):
    """Unknown Euphemia override fields should raise a clear error."""
    monkeypatch.setattr(EuphemiaConfig, "set_dataset", lambda self, dataset: None)
    config = EuphemiaConfig()

    with pytest.raises(ValueError, match="Invalid Euphemia configuration key"):
        config.apply_overrides({"does_not_exist": 123})


def test_apply_overrides_normalizes_network_model_to_uppercase(monkeypatch):
    """network_model should be accepted case-insensitively and normalized."""
    monkeypatch.setattr(EuphemiaConfig, "set_dataset", lambda self, dataset: None)
    config = EuphemiaConfig()

    config.apply_overrides({"network_model": "fbmc"})

    assert config.network_model == "FBMC"


def test_apply_overrides_rejects_invalid_network_model(monkeypatch):
    """network_model must be ATC or FBMC."""
    monkeypatch.setattr(EuphemiaConfig, "set_dataset", lambda self, dataset: None)
    config = EuphemiaConfig()

    with pytest.raises(ValueError, match="network_model must be 'ATC' or 'FBMC'"):
        config.apply_overrides({"network_model": "invalid"})


def test_set_dataset_updates_dataset_name_and_scenario():
    """set_dataset should persist enum-name and parsed scenario object."""
    parsed_scenario = {"name": "dummy-scenario"}
    dataset = SimpleNamespace(
        name="DUMMY",
        value=SimpleNamespace(parse_data=lambda: parsed_scenario),
    )

    # Bypass __init__ to test set_dataset in isolation.
    config = object.__new__(EuphemiaConfig)
    config.set_dataset(dataset)

    assert config.dataset == "DUMMY"
    assert config.scenario == parsed_scenario


@patch("apem.order_book_based_model.euphemia.runner.MasterProblem")
@patch("apem.order_book_based_model.euphemia.runner.EuphemiaConfig")
def test_solve_euphemia_wires_config_and_runs(config_cls, master_problem_cls):
    """solve_euphemia should apply overrides, set dataset/cut type, and run master problem."""
    config = config_cls.return_value
    euphemia = master_problem_cls.return_value
    overrides = {"max_iterations": 11, "output_flag": 1}

    solve_euphemia(OrderBookBased_Datasets.GME, CutTypes.PB, overrides)

    config.apply_overrides.assert_called_once_with(overrides)
    config.set_dataset.assert_called_once_with(OrderBookBased_Datasets.GME)
    assert config.cutting_strategy == CutTypes.PB
    master_problem_cls.assert_called_once_with(config)
    euphemia.run.assert_called_once_with()


@patch("apem.order_book_based_model.euphemia.runner.MasterProblem")
@patch("apem.order_book_based_model.euphemia.runner.EuphemiaConfig")
def test_solve_euphemia_none_overrides_defaults_to_empty_dict(config_cls, master_problem_cls):
    """Passing None overrides should call apply_overrides with an empty dict."""
    config = config_cls.return_value

    solve_euphemia(OrderBookBased_Datasets.OMIE, CutTypes.CB, None)

    config.apply_overrides.assert_called_once_with({})
    config.set_dataset.assert_called_once_with(OrderBookBased_Datasets.OMIE)


def test_transform_step_orders_sell_side_increments_are_computed_per_period():
    orders = pd.DataFrame(
        [
            {"id": "s1", "t": 1, "p": 10, "q": 10},
            {"id": "s2", "t": 1, "p": 20, "q": 25},
            {"id": "s3", "t": 1, "p": 30, "q": 40},
            {"id": "s4", "t": 2, "p": 15, "q": 8},
        ]
    )

    transformed = transform_step_orders(orders, periods=[1, 2], sell=True)

    assert transformed["id"].tolist() == ["s1", "s2", "s3", "s4"]
    assert transformed["q"].tolist() == [10, 15, 15, 8]


def test_transform_step_orders_buy_side_keeps_last_level_for_period():
    orders = pd.DataFrame(
        [
            {"id": "b1", "t": 1, "p": 100, "q": -10},
            {"id": "b2", "t": 1, "p": 90, "q": -30},
            {"id": "b3", "t": 1, "p": 80, "q": -60},
        ]
    )

    transformed = transform_step_orders(orders, periods=[1], sell=False)

    # Current implementation explicitly sets last segment to previous level.
    assert transformed["q"].tolist()[-1] == -60


def test_transform_step_orders_filters_by_scalable_order_id():
    orders = pd.DataFrame(
        [
            {"id": "x1", "scalable_order_id": "A", "t": 1, "p": 10, "q": 5},
            {"id": "x2", "scalable_order_id": "A", "t": 1, "p": 20, "q": 9},
            {"id": "y1", "scalable_order_id": "B", "t": 1, "p": 30, "q": 11},
        ]
    )

    transformed = transform_step_orders(
        orders,
        periods=[1],
        sell=True,
        order_id="A",
        scalable=True,
    )

    assert transformed["id"].tolist() == ["x1", "x2"]
    assert transformed["scalable_order_id"].tolist() == ["A", "A"]


def test_parse_fb_constraints_accepts_aliases_and_optional_lb(tmp_path):
    fb_constraints = tmp_path / "fb_constraints.csv"
    fb_constraints.write_text(
        "constraint_id,period,capacity,min_ram\n"
        "CNEC_1,1,123.5,-80\n",
        encoding="utf-8",
    )

    parsed = parse_fb_constraints(tmp_path)

    assert parsed.columns.tolist() == ["cnec_id", "t", "ram", "lb"]
    assert parsed.iloc[0].to_dict() == {"cnec_id": "CNEC_1", "t": 1, "ram": 123.5, "lb": -80.0}


def test_parse_fb_constraints_missing_file_returns_empty_dataframe(tmp_path):
    parsed = parse_fb_constraints(tmp_path)

    assert parsed.empty
    assert parsed.columns.tolist() == ["cnec_id", "t", "ram"]


def test_parse_fb_ptdf_accepts_aliases(tmp_path):
    fb_ptdf = tmp_path / "fb_ptdf.csv"
    fb_ptdf.write_text(
        "constraint_id,time,bidding_zone,factor\n"
        "CNEC_1,2,Z9,0.25\n",
        encoding="utf-8",
    )

    parsed = parse_fb_ptdf(tmp_path)

    assert parsed.columns.tolist() == ["cnec_id", "t", "zone", "ptdf"]
    assert parsed.iloc[0].to_dict() == {"cnec_id": "CNEC_1", "t": 2, "zone": "Z9", "ptdf": 0.25}


def test_parse_order_book_adds_zones_from_fb_ptdf(tmp_path):
    (tmp_path / "periods.csv").write_text("period\n1\n", encoding="utf-8")
    (tmp_path / "zones.csv").write_text("zone\nZ1\n", encoding="utf-8")
    (tmp_path / "step_orders.csv").write_text("id,t,p,q,zone\n1,1,10,1,Z1\n", encoding="utf-8")
    (tmp_path / "block_orders.csv").write_text("id,block_type,code_prm,p,q1,MAR,zone\n", encoding="utf-8")
    (tmp_path / "complex_orders.csv").write_text(
        "id,step_orders,fixed_term,variable_term,condition,load_gradient\n", encoding="utf-8"
    )
    (tmp_path / "complex_step_orders.csv").write_text("id,complex_order_id,t,p,q,zone\n", encoding="utf-8")
    (tmp_path / "scalable_complex_orders.csv").write_text(
        "id,step_orders,fixed_term,condition,load_gradient,MAP1\n", encoding="utf-8"
    )
    (tmp_path / "scalable_step_orders.csv").write_text("id,scalable_order_id,t,p,q,zone\n", encoding="utf-8")
    (tmp_path / "piecewise_linear_orders.csv").write_text("id,t,p0,p1,q,zone\n", encoding="utf-8")
    (tmp_path / "fb_constraints.csv").write_text("cnec_id,t,ram\nC1,1,100\n", encoding="utf-8")
    (tmp_path / "fb_ptdf.csv").write_text(
        "cnec_id,t,zone,ptdf\n"
        "C1,1,Z1,1.0\n"
        "C1,1,Z9,-1.0\n",
        encoding="utf-8",
    )

    scenario = ParseOrderBook(tmp_path, "tmp").parse_data()

    assert scenario.zones == ["Z1", "Z9"]
    assert list(scenario.fb_constraints.columns) == ["cnec_id", "t", "ram"]
    assert list(scenario.fb_ptdf.columns) == ["cnec_id", "t", "zone", "ptdf"]


def test_block_signature_ignores_identifier_fields():
    conv = _dummy_conversion(periods=(1, 2))

    row_a = pd.Series(
        {
            "id": "r1",
            "block_type": "linked",
            "q1": 1.23456789,
            "q2": 5,
            "p": 42.00001,
            "MAR": 0,
        }
    )
    row_b = pd.Series(
        {
            "id": "r2",
            "block_type": "linked",
            "q1": 1.23456789,
            "q2": 5,
            "p": 42.00001,
            "MAR": 0,
        }
    )

    assert conv.block_signature(row_a) == conv.block_signature(row_b)


def test_compress_blocks_merges_identical_chains_and_updates_parent_reference():
    conv = _dummy_conversion(periods=(1, 2))

    df = pd.DataFrame(
        [
            {"id": "e1", "block_type": "exclusive", "code_prm": "grp", "p": 50, "q1": 10, "q2": 0, "MAR": 1},
            {"id": "l1", "block_type": "linked", "code_prm": "e1", "p": 60, "q1": 0, "q2": 4, "MAR": 0},
            {"id": "e2", "block_type": "exclusive", "code_prm": "grp", "p": 50, "q1": 10, "q2": 0, "MAR": 1},
            {"id": "l2", "block_type": "linked", "code_prm": "e2", "p": 60, "q1": 0, "q2": 4, "MAR": 0},
        ]
    )

    compressed = conv.compress_blocks(df)

    assert len(compressed) == 2

    parent = compressed[compressed["block_type"] == "exclusive"].iloc[0]
    child = compressed[compressed["block_type"] == "linked"].iloc[0]

    assert parent["q1"] == 20
    assert parent["q2"] == 0
    assert parent["MAR"] == 1
    assert "+" in parent["id"]

    assert child["q1"] == 0
    assert child["q2"] == 8
    assert child["code_prm"] == parent["id"]


def test_generate_contiguous_patterns_properties():
    conv = _dummy_conversion(periods=(1, 2, 3, 4))

    patterns = conv.generate_contiguous_patterns(min_uptime=2)

    # For T=4 and min_uptime=2 there are 6 contiguous patterns.
    assert len(patterns) == 6
    # Every pattern encodes all periods.
    assert all(sum(pattern) == 4 for pattern in patterns)
    # There is exactly one contiguous ON segment (>1) per pattern.
    assert all(sum(1 for v in pattern if v > 1) == 1 for pattern in patterns)


def test_price_subproblem_add_atc_coupling_builds_active_set_constraints():
    master = _base_pricing_master(network_model="ATC")
    var_model = gp.Model()
    var_model.setParam("OutputFlag", 0)
    flow_var = var_model.addVar(name="f_atc[Z1,Z2,1]")
    var_model.update()

    master.atc_index = [("Z1", "Z2", 1)]
    master.atc_cap = {("Z1", "Z2", 1): 100.0}
    master.f_atc = {("Z1", "Z2", 1): flow_var}
    master.current_alloc_solution = {flow_var.VarName: [40.0]}

    pricing = PriceSubproblem(master)
    pricing.pricing_model.setParam("OutputFlag", 0)
    pricing.add_atc_price_consistency_constraints()
    pricing.pricing_model.update()

    names = {c.ConstrName for c in pricing.pricing_model.getConstrs()}
    assert "atc_price_Z1_Z2_1_0_eq1" in names
    assert "atc_price_Z1_Z2_1_0_eq2" in names


def test_price_subproblem_add_atc_coupling_is_noop_in_fbmc_mode():
    master = _base_pricing_master(network_model="FBMC")
    var_model = gp.Model()
    var_model.setParam("OutputFlag", 0)
    flow_var = var_model.addVar(name="f_atc[Z1,Z2,1]")
    var_model.update()

    master.atc_index = [("Z1", "Z2", 1)]
    master.atc_cap = {("Z1", "Z2", 1): 100.0}
    master.f_atc = {("Z1", "Z2", 1): flow_var}
    master.current_alloc_solution = {flow_var.VarName: [0.0]}

    pricing = PriceSubproblem(master)
    pricing.pricing_model.setParam("OutputFlag", 0)
    pricing.add_atc_price_consistency_constraints()
    pricing.pricing_model.update()

    assert pricing.pricing_model.NumConstrs == 0


def test_price_subproblem_add_fbmc_coupling_builds_stationarity_and_dual_fixing():
    master = _base_pricing_master(network_model="FBMC")
    var_model = gp.Model()
    var_model.setParam("OutputFlag", 0)
    np_z1 = var_model.addVar(name="net_position[Z1,1]")
    np_z2 = var_model.addVar(name="net_position[Z2,1]")
    var_model.update()

    master.net_position = {("Z1", 1): np_z1, ("Z2", 1): np_z2}
    master.current_alloc_solution = {np_z1.VarName: [10.0], np_z2.VarName: [-10.0]}
    master.fb_index = [("C1", 1)]
    master.fb_ram = {("C1", 1): 100.0}
    master.fb_lb = {("C1", 1): -100.0}
    master.fb_ptdf_map = {("C1", 1, "Z1"): 1.0, ("C1", 1, "Z2"): 0.0}

    pricing = PriceSubproblem(master)
    pricing.pricing_model.setParam("OutputFlag", 0)
    pricing.add_fbmc_price_consistency_constraints()
    pricing.pricing_model.update()

    constr_names = {c.ConstrName for c in pricing.pricing_model.getConstrs()}
    assert "fbmc_mcp_stationarity_Z1_1" in constr_names
    assert "fbmc_mcp_stationarity_Z2_1" in constr_names
    assert "fbmc_mu_up_zero_if_nonbinding_C1_1" in constr_names
    assert "fbmc_mu_lo_zero_if_nonbinding_C1_1" in constr_names

    var_names = {v.VarName for v in pricing.pricing_model.getVars()}
    assert "fbmc_lambda[1]" in var_names
    assert "fbmc_mu_up[C1,1]" in var_names
    assert "fbmc_mu_lo[C1,1]" in var_names


def test_price_subproblem_add_fbmc_coupling_is_noop_in_atc_mode():
    master = _base_pricing_master(network_model="ATC")
    master.fb_index = [("C1", 1)]
    master.fb_ram = {("C1", 1): 100.0}
    master.fb_ptdf_map = {("C1", 1, "Z1"): 1.0, ("C1", 1, "Z2"): -1.0}

    pricing = PriceSubproblem(master)
    pricing.pricing_model.setParam("OutputFlag", 0)
    pricing.add_fbmc_price_consistency_constraints()
    pricing.pricing_model.update()

    assert pricing.pricing_model.NumConstrs == 0
    assert all(not v.VarName.startswith("fbmc_") for v in pricing.pricing_model.getVars())


def test_resolve_zone_strips_quote_characters():
    master = object.__new__(MasterProblem)
    master.default_zone = "Z1"

    assert MasterProblem.resolve_zone(master, " 'Z2' ") == "Z2"
    assert MasterProblem.resolve_zone(master, '"Z3"') == "Z3"
    assert MasterProblem.resolve_zone(master, None) == "Z1"

