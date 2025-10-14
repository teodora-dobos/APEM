import json
import pytest
from apem.config_loader import ConfigLoader


@pytest.fixture
def valid_config(tmp_path):
    """Create a temporary valid config.json file."""
    data = {
        "_available_zonal_configurations": ["zonal_DE4-refined"],
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
        "solver_configuration": {
            "MIP_gap": 1e-4,
            "optimality_tol": 1e-6,
            "time_limit": 3600
        },
        "zonal_configuration": {"type": "zonal_DE4-refined", "factor": 0.8}
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
    cfg["scenario"]["power_flow_model"]["type"] = "Zonal_NTC"
    loader_file = valid_config.parent / "zonal.json"
    loader_file.write_text(json.dumps(cfg))

    loader = ConfigLoader(str(loader_file))
    pf_model = loader.get_power_flow_model()
    assert pf_model.__class__.__name__ == "Zonal_NTC"
