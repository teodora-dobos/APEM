import json
from typing import Dict, Any

from apem.allocation.algorithms.nodal_clearing.dcopf import DCOPF
from apem.allocation.algorithms.zonal_clearing.zonal_NTC import Zonal_NTC
from apem.enums import Datasets, MarketModels, PricingAlgorithms, RedispatchAlgorithms


class ConfigLoader:
    def __init__(self, config_path: str = "config.json"):
        self.config_path = config_path
        self.raw_config = self._load_raw_config()
        self._validate_config()
        self.config = self._filter_documentation_fields()

    def _load_raw_config(self) -> Dict[str, Any]:
        with open(self.config_path, 'r') as f:
            return json.load(f)

    def _filter_documentation_fields(self) -> Dict[str, Any]:
        """Remove documentation fields (those starting with _) from the config."""
        return {k: v for k, v in self.raw_config.items() if not k.startswith('_')}

    def _validate_config(self):
        # Validate dataset
        if self.raw_config['scenario']['dataset'] not in [d.name for d in Datasets]:
            raise ValueError(f"Invalid dataset: {self.raw_config['scenario']['dataset']}")

        # Validate market model
        if self.raw_config['scenario']['market_model'] not in ["US_model", "EU_model"]:
            raise ValueError(f"Invalid market model: {self.raw_config['scenario']['market_model']}")

        # Validate power flow model
        if self.raw_config['scenario']['power_flow_model']['type'] not in ["DCOPF", "Zonal_NTC"]:
            raise ValueError(f"Invalid power flow model: {self.raw_config['scenario']['power_flow_model']['type']}")

        # Validate pricing algorithm
        if self.raw_config['scenario']['pricing_algorithm'] not in [p.name for p in PricingAlgorithms]:
            raise ValueError(f"Invalid pricing algorithm: {self.raw_config['scenario']['pricing_algorithm']}")

        # Validate redispatch algorithm
        if self.raw_config['scenario']['redispatch_algorithm'] not in [r.name for r in RedispatchAlgorithms]:
            raise ValueError(f"Invalid redispatch algorithm: {self.raw_config['scenario']['redispatch_algorithm']}")

        # Validate zonal configuration if using Zonal_NTC
        if self.raw_config['scenario']['power_flow_model']['type'] == "Zonal_NTC":
            zonal_config = self.raw_config['zonal_configuration']
            if zonal_config['type'] not in self.raw_config['_available_zonal_configurations']:
                raise ValueError(f"Invalid zonal configuration type: {zonal_config['type']}")
            if not 0 <= zonal_config['factor'] <= 1:
                raise ValueError(f"Invalid zonal factor: {zonal_config['factor']}. Must be between 0 and 1.")

    def get_dataset(self) -> Datasets:
        return Datasets[self.config['scenario']['dataset']]

    def get_market_model(self) -> MarketModels:
        return MarketModels[self.config['scenario']['market_model']]

    def get_power_flow_model(self):
        model_type = self.config['scenario']['power_flow_model']['type']
        if model_type == "Zonal_NTC":
            zonal_config = self.config['zonal_configuration']
            return Zonal_NTC(zonal_configuration=zonal_config['type'], factor=zonal_config['factor'])
        return DCOPF()

    def get_pricing_algorithm(self) -> PricingAlgorithms:
        return PricingAlgorithms[self.config['scenario']['pricing_algorithm']]

    def get_redispatch_algorithm(self) -> RedispatchAlgorithms:
        return RedispatchAlgorithms[self.config['scenario']['redispatch_algorithm']]

    def get_solver_configuration(self) -> Dict[str, Any]:
        return self.config['solver_configuration'] 