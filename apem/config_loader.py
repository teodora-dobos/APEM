import json
from typing import Any, Dict

from apem.EU_market_model.euphemia.enums.cut_types import CutTypes
from apem.EU_market_model.euphemia.enums.datasets import EU_Datasets
from apem.US_market_model.allocation.algorithms.nodal_clearing.dcopf import DCOPF
from apem.US_market_model.allocation.algorithms.zonal_clearing.zonal_fbmc_included import ZonalFBMC
from apem.US_market_model.allocation.algorithms.zonal_clearing.zonal_NTC_independent import Zonal_NTC_multiedge
from apem.US_market_model.allocation.algorithms.zonal_clearing.zonal_NTC import Zonal_NTC_aggregated
from apem.enums import FBMCBaseCases, MarketModels, PricingAlgorithms, RedispatchAlgorithms, US_Datasets


class ConfigLoader:
    def __init__(self, config_path: str = "config.json"):
        self.config_path = config_path
        self.raw_config = self._load_raw_config()
        self._validate_config()
        self.config = self._filter_documentation_fields()

    def _load_raw_config(self) -> Dict[str, Any]:
        with open(self.config_path, "r") as f:
            return json.load(f)

    def _filter_documentation_fields(self) -> Dict[str, Any]:
        """Remove documentation fields (those starting with _) from the config."""
        return {k: v for k, v in self.raw_config.items() if not k.startswith("_")}

    def _validate_config(self):
        # Validate datasets
        if self.raw_config["scenario"]["US_dataset"] not in [d.name for d in US_Datasets]:
            raise ValueError(f"Invalid US_dataset: {self.raw_config['scenario']['US_dataset']}")
        if self.raw_config["scenario"]["EU_dataset"] not in [d.name for d in EU_Datasets]:
            raise ValueError(f"Invalid dataset: {self.raw_config['scenario']['EU_dataset']}")

        # Validate market model
        if self.raw_config["scenario"]["market_model"] not in ["US_model", "EU_model"]:
            raise ValueError(f"Invalid market model: {self.raw_config['scenario']['market_model']}")

        # Validate power flow model
        if self.raw_config["scenario"]["power_flow_model"]["type"] not in [
            "DCOPF",
            "Zonal_NTC_aggregated",
            "Zonal_NTC_multiedge",
            "Zonal_FBMC",
        ]:
            raise ValueError(
                f"Invalid power flow model: {self.raw_config['scenario']['power_flow_model']['type']}"
            )

        # Validate cut type
        if self.raw_config["scenario"]["cut_type"] not in [c.value for c in CutTypes]:
            raise ValueError(f"Invalid cut type: {self.raw_config['scenario']['cut_type']}")

        # Validate pricing algorithm
        if self.raw_config["scenario"]["pricing_algorithm"] not in [p.name for p in PricingAlgorithms]:
            raise ValueError(f"Invalid pricing algorithm: {self.raw_config['scenario']['pricing_algorithm']}")

        # Validate redispatch algorithm
        if self.raw_config["scenario"]["redispatch_algorithm"] not in [r.name for r in RedispatchAlgorithms]:
            raise ValueError(f"Invalid redispatch algorithm: {self.raw_config['scenario']['redispatch_algorithm']}")

        # Validate redispatch constraint units
        if self.raw_config["scenario"]["redispatch_constraint_units"] not in [True, False]:
            raise ValueError(
                f"Invalid redispatch constraint: {self.raw_config['scenario']['redispatch_constraint_units']}"
            )

        # Validate redispatch threshold
        if self.raw_config["scenario"]["redispatch_threshold"] < 0:
            raise ValueError(f"Invalid redispatch threshold: {self.raw_config['scenario']['redispatch_threshold']}")

        # Validate alpha for markup pricing
        if not 0 <= self.raw_config["scenario"]["alpha"] < 1:
            raise ValueError(f"Invalid alpha: {self.raw_config['scenario']['alpha']}")

        # Validate zonal configuration when a zonal model is selected
        pf_type = self.raw_config["scenario"]["power_flow_model"]["type"]
        if pf_type in ["Zonal_NTC_aggregated", "Zonal_NTC_multiedge", "Zonal_FBMC"]:
            zonal_config = self.raw_config["zonal_configuration"]
            available_configs = self.raw_config.get("_available_zonal_configurations", [])
            if available_configs and zonal_config["type"] not in available_configs:
                raise ValueError(f"Invalid zonal configuration type: {zonal_config['type']}")
            if pf_type == "Zonal_NTC_aggregated":
                if not 0 <= zonal_config["factor"] <= 1:
                    raise ValueError(f"Invalid zonal factor: {zonal_config['factor']}. Must be between 0 and 1.")
            if pf_type == "Zonal_NTC_multiedge":
                if not 0 <= zonal_config["factor"] <= 1:
                    raise ValueError(f"Invalid zonal factor: {zonal_config['factor']}. Must be between 0 and 1.")
            if pf_type == "Zonal_FBMC":
                available_base_cases = self.raw_config.get("_available_base_cases", ["BC1"])
                base_case = zonal_config.get("base_case", available_base_cases[0])
                self.raw_config["zonal_configuration"]["base_case"] = base_case
                if base_case not in [c.value for c in FBMCBaseCases]:
                    raise ValueError(f"Invalid FBMC base case: {base_case}.")

    def get_US_dataset(self) -> US_Datasets:
        return US_Datasets[self.config["scenario"]["US_dataset"]]

    def get_EU_dataset(self) -> EU_Datasets:
        return EU_Datasets[self.config["scenario"]["EU_dataset"]]

    def get_market_model(self) -> MarketModels:
        return MarketModels[self.config["scenario"]["market_model"]]

    def get_power_flow_model(self):
        model_type = self.config["scenario"]["power_flow_model"]["type"]
        if model_type == "Zonal_NTC_aggregated":
            zonal_config = self.config["zonal_configuration"]
            return Zonal_NTC_aggregated(zonal_configuration=zonal_config["type"], factor=zonal_config["factor"])
        if model_type == "Zonal_NTC_multiedge":
            zonal_config = self.config["zonal_configuration"]
            return Zonal_NTC_multiedge(zonal_configuration=zonal_config["type"], factor=zonal_config["factor"])
        if model_type == "Zonal_FBMC":
            zonal_config = self.config["zonal_configuration"]
            base_case = zonal_config["base_case"]
            if base_case not in [c.value for c in FBMCBaseCases]:
                raise ValueError(f"Invalid FBMC base case: {base_case}")
            return ZonalFBMC(zonal_configuration=zonal_config["type"], base_case_type=base_case)
        if model_type == "DCOPF":
            return DCOPF()
        raise ValueError(f"Invalid power flow model: {model_type}")

    def get_cut_type(self) -> CutTypes:
        return CutTypes(self.config["scenario"]["cut_type"])

    def get_pricing_algorithm(self) -> PricingAlgorithms:
        return PricingAlgorithms[self.config["scenario"]["pricing_algorithm"]]

    def get_redispatch_algorithm(self) -> RedispatchAlgorithms:
        return RedispatchAlgorithms[self.config["scenario"]["redispatch_algorithm"]]

    def get_redispatch_constraint_units(self) -> bool:
        return self.config["scenario"]["redispatch_constraint_units"]

    def get_redispatch_threshold(self) -> float:
        return self.config["scenario"]["redispatch_threshold"]

    def get_alpha(self) -> float:
        return self.config["scenario"]["alpha"]

    def get_solver_configuration(self) -> Dict[str, Any]:
        return self.config["solver_configuration"]
