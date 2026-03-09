import json
import pytest
from apem.config_loader import ConfigLoader


@pytest.fixture
def valid_config(tmp_path):
    """Create a temporary valid config.json file."""
    data = {
        "_available_zonal_configurations": ["zonal_DE4"],
        "scenario": {
            "market_model": "US_model",
            "US_dataset": "ARPA",
            "EU_dataset": "GME",
            "power_flow_model": {"type": "DCOPF"},
            "cut_type": "price based",
            "pricing_algorithm": "IP",
            "redispatch_algorithm": "MinCostRD",
            "redispatch_constraint_units": False,
            "redispatch_threshold": 0.001,
            "alpha": 0.5
        },
        "us_solver_configuration": {
            "MIP_gap": 1e-4,
            "optimality_tol": 1e-6,
            "time_limit": 3600
        },
        "zonal_configuration": {"type": "zonal_DE4", "factor": 0.8}
    }
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps(data))
    return config_file


def test_loads_valid_config(valid_config):
    loader = ConfigLoader(str(valid_config))
    assert isinstance(loader.config, dict)
    assert "scenario" in loader.config
    assert loader.get_alpha() == 0.5


def test_invalid_US_dataset(valid_config):
    cfg = json.loads(valid_config.read_text())
    cfg["scenario"]["US_dataset"] = "INVALID"
    bad_file = valid_config.parent / "bad.json"
    bad_file.write_text(json.dumps(cfg))

    with pytest.raises(ValueError, match="Invalid US_dataset"):
        ConfigLoader(str(bad_file))


def test_invalid_market_model(valid_config):
    cfg = json.loads(valid_config.read_text())
    cfg["scenario"]["market_model"] = "INVALID"
    bad_file = valid_config.parent / "bad2.json"
    bad_file.write_text(json.dumps(cfg))

    with pytest.raises(ValueError, match="Invalid market model"):
        ConfigLoader(str(bad_file))


def test_invalid_power_flow_model(valid_config):
    cfg = json.loads(valid_config.read_text())
    cfg["scenario"]["power_flow_model"]["type"] = "INVALID"
    bad_file = valid_config.parent / "bad3.json"
    bad_file.write_text(json.dumps(cfg))

    with pytest.raises(ValueError, match="Invalid power flow model"):
        ConfigLoader(str(bad_file))


def test_zonal_config_used_only_for_zonal(valid_config):
    cfg = json.loads(valid_config.read_text())
    cfg["scenario"]["power_flow_model"]["type"] = "Zonal_NTC_aggregated"
    loader_file = valid_config.parent / "zonal.json"
    loader_file.write_text(json.dumps(cfg))

    loader = ConfigLoader(str(loader_file))
    pf_model = loader.get_power_flow_model()
    assert pf_model.__class__.__name__ == "Zonal_NTC_aggregated"


def test_get_euphemia_configuration_defaults_to_empty(valid_config):
    loader = ConfigLoader(str(valid_config))
    assert loader.get_euphemia_configuration() == {}


def test_invalid_euphemia_configuration_key(valid_config):
    cfg = json.loads(valid_config.read_text())
    cfg["euphemia_configuration"] = {"not_a_real_key": 1}
    bad_file = valid_config.parent / "bad_euphemia_key.json"
    bad_file.write_text(json.dumps(cfg))

    with pytest.raises(ValueError, match="Invalid euphemia_configuration key"):
        ConfigLoader(str(bad_file))


def test_valid_euphemia_configuration(valid_config):
    cfg = json.loads(valid_config.read_text())
    cfg["euphemia_configuration"] = {
        "max_iterations": 25,
        "reinsertion_max_iterations": 5,
        "output_flag": 0,
        "lazy_constraints": 1,
        "beta_MIC": 0.2,
    }
    cfg_file = valid_config.parent / "good_euphemia.json"
    cfg_file.write_text(json.dumps(cfg))

    loader = ConfigLoader(str(cfg_file))
    euphemia_cfg = loader.get_euphemia_configuration()
    assert euphemia_cfg["max_iterations"] == 25
    assert euphemia_cfg["reinsertion_max_iterations"] == 5


def test_legacy_solver_configuration_key_supported_with_warning(valid_config):
    cfg = json.loads(valid_config.read_text())
    cfg["solver_configuration"] = cfg.pop("us_solver_configuration")
    cfg_file = valid_config.parent / "legacy_solver_key.json"
    cfg_file.write_text(json.dumps(cfg))

    loader = ConfigLoader(str(cfg_file))
    with pytest.warns(DeprecationWarning, match="solver_configuration"):
        us_solver_cfg = loader.get_us_solver_configuration()

    assert us_solver_cfg["time_limit"] == 3600


def test_solver_configuration_alias_method(valid_config):
    loader = ConfigLoader(str(valid_config))
    assert loader.get_solver_configuration() == loader.get_us_solver_configuration()
