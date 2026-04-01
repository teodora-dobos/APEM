import json
from numbers import Integral, Real
from typing import Any, Dict

from apem.order_book_based_model.euphemia.enums.cut_types import CutTypes
from apem.unit_based_model.allocation.algorithms.nodal_clearing.dcopf import DCOPF
from apem.unit_based_model.allocation.algorithms.zonal_clearing.zonal_fbmc_included import Zonal_FBMC
from apem.unit_based_model.allocation.algorithms.zonal_clearing.zonal_ntc_multiedge import Zonal_NTC_multiedge
from apem.unit_based_model.allocation.algorithms.zonal_clearing.zonal_ntc_aggregated import Zonal_NTC_aggregated
from apem.order_book_based_model.euphemia.enums.datasets import OrderBookBased_Datasets
from apem.core import MarketModels
from apem.unit_based_model.enums import FBMCBaseCases, PricingAlgorithms, RedispatchAlgorithms, UnitBased_Datasets


class ConfigLoader:
    def __init__(self, config_path: str = "config.json"):
        self.config_path = config_path
        self.raw_config = self._normalize_config_format(self._load_raw_config())
        self._validate_config()
        self.config = self._filter_documentation_fields()

    def _load_raw_config(self) -> Dict[str, Any]:
        with open(self.config_path, "r", encoding="utf-8-sig") as f:
            return json.load(f)

    def _normalize_config_format(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        """
        Accept model-scoped config format with canonical keys
        ('run', 'unit_based_model', 'order_book_based_model').
        """
        if "run" not in raw:
            raise ValueError(
                "Invalid config format: expected model-scoped format "
                "with a top-level 'run' section."
            )
        return self._normalize_model_scoped_config(raw)

    def _normalize_model_scoped_config(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        run_cfg = raw.get("run", {})
        unit_cfg = raw.get("unit_based_model", {})
        order_book_cfg = raw.get("order_book_based_model", {})

        if not isinstance(run_cfg, dict):
            raise ValueError("Invalid run: expected an object.")
        if unit_cfg is None:
            unit_cfg = {}
        if order_book_cfg is None:
            order_book_cfg = {}
        if not isinstance(unit_cfg, dict):
            raise ValueError("Invalid unit_based_model: expected an object.")
        if not isinstance(order_book_cfg, dict):
            raise ValueError("Invalid order_book_based_model: expected an object.")

        redispatch_cfg = unit_cfg.get("redispatch", {})
        if redispatch_cfg is None:
            redispatch_cfg = {}
        if not isinstance(redispatch_cfg, dict):
            raise ValueError("Invalid unit_based_model.redispatch: expected an object.")

        unit_solver_cfg = unit_cfg.get("solver_configuration")
        market_model = run_cfg.get("market_model", "unit_based_model")

        normalized = {
            "verbosity": run_cfg.get("verbosity", raw.get("verbosity", True)),
            "scenario": {
                "market_model": market_model,
                "unit_based_dataset": unit_cfg.get("dataset", "IEEE_RTS"),
                "order_book_based_dataset": order_book_cfg.get("dataset", "GENERATED_SMALL"),
                "power_flow_model": unit_cfg.get("power_flow_model", {"type": "DCOPF"}),
                "cut_type": order_book_cfg.get("cut_type", CutTypes.PB.value),
                "pricing_algorithm": unit_cfg.get("pricing_algorithm", "IP"),
                "redispatch_algorithm": redispatch_cfg.get("algorithm", "MinCostRD"),
                "redispatch_constraint_units": redispatch_cfg.get("constraint_units", False),
                "redispatch_threshold": redispatch_cfg.get("threshold", 0.0),
                "alpha": redispatch_cfg.get("alpha", 0.0),
            },
            "euphemia_configuration": order_book_cfg.get("euphemia_configuration", raw.get("euphemia_configuration", {})),
            "zonal_configuration": unit_cfg.get(
                "zonal_configuration",
                raw.get("zonal_configuration", {"type": "zonal_DE2-s", "factor": 0.8, "base_case": "BC4"}),
            ),
        }

        if unit_solver_cfg is not None:
            normalized["unit_based_solver_configuration"] = unit_solver_cfg

        # Preserve optional documentation/helper fields.
        for key, value in raw.items():
            if key.startswith("_"):
                normalized[key] = value

        return normalized

    def _filter_documentation_fields(self) -> Dict[str, Any]:
        """Remove documentation fields (those starting with _) from the config."""
        return {k: v for k, v in self.raw_config.items() if not k.startswith("_")}

    def _validate_config(self):
        # Validate datasets
        if self.raw_config["scenario"]["unit_based_dataset"] not in [d.name for d in UnitBased_Datasets]:
            raise ValueError(f"Invalid unit_based_dataset: {self.raw_config['scenario']['unit_based_dataset']}")
        if self.raw_config["scenario"]["order_book_based_dataset"] not in [d.name for d in OrderBookBased_Datasets]:
            raise ValueError(
                f"Invalid order_book_based_dataset: {self.raw_config['scenario']['order_book_based_dataset']}"
            )

        # Validate market model
        if self.raw_config["scenario"]["market_model"] not in ["unit_based_model", "order_book_based_model"]:
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

        self._validate_unit_based_solver_configuration()
        self._validate_euphemia_configuration()

    def _validate_unit_based_solver_configuration(self) -> None:
        if self.raw_config["scenario"]["market_model"] != "unit_based_model":
            return

        if "unit_based_solver_configuration" not in self.raw_config:
            raise ValueError(
                "Missing solver configuration: provide 'unit_based_model.solver_configuration'."
            )

        if not isinstance(self.raw_config["unit_based_solver_configuration"], dict):
            raise ValueError("Invalid unit_based_solver_configuration: expected an object.")

        cfg = self.raw_config["unit_based_solver_configuration"]
        if "slack_penalty" in cfg:
            if not self._is_number(cfg["slack_penalty"]):
                raise ValueError("Invalid unit_based_solver_configuration.slack_penalty: must be numeric.")
            if cfg["slack_penalty"] <= 0:
                raise ValueError("Invalid unit_based_solver_configuration.slack_penalty: must be > 0.")

    @staticmethod
    def _is_number(value: Any) -> bool:
        return isinstance(value, Real) and not isinstance(value, bool)

    @staticmethod
    def _is_int(value: Any) -> bool:
        return isinstance(value, Integral) and not isinstance(value, bool)

    def _validate_euphemia_configuration(self) -> None:
        cfg = self.raw_config.get("euphemia_configuration", {})
        if cfg is None:
            return
        if not isinstance(cfg, dict):
            raise ValueError("Invalid euphemia_configuration: expected an object.")

        allowed = {
            "disable_reinsertion",
            "calculate_corrected_welfare",
            "price_lower_bound",
            "price_upper_bound",
            "beta_MIC",
            "delta_load_gradient",
            "delta_PAB",
            "epsilon",
            "max_iterations",
            "reinsertion_max_iterations",
            "max_prb_reinsertion_attempts",
            "big_m",
            "network_model",
            "lazy_constraints",
            "output_flag",
            "time_limit",
            "mip_gap",
            "threads",
            "seed",
        }

        unknown = sorted(set(cfg) - allowed)
        if unknown:
            raise ValueError(f"Invalid euphemia_configuration key(s): {', '.join(unknown)}")

        bool_fields = {"disable_reinsertion", "calculate_corrected_welfare"}
        int_fields = {
            "max_iterations",
            "reinsertion_max_iterations",
            "max_prb_reinsertion_attempts",
            "threads",
            "seed",
            "output_flag",
            "lazy_constraints",
        }
        number_fields = {"price_lower_bound", "price_upper_bound", "beta_MIC", "delta_load_gradient", "delta_PAB", "epsilon", "big_m", "time_limit", "mip_gap"}

        for field in bool_fields:
            if field in cfg and not isinstance(cfg[field], bool):
                raise ValueError(f"Invalid euphemia_configuration.{field}: must be boolean.")
        for field in int_fields:
            if field in cfg and cfg[field] is not None and not self._is_int(cfg[field]):
                raise ValueError(f"Invalid euphemia_configuration.{field}: must be integer.")
        for field in number_fields:
            if field in cfg and not self._is_number(cfg[field]):
                raise ValueError(f"Invalid euphemia_configuration.{field}: must be numeric.")

        if "network_model" in cfg:
            if not isinstance(cfg["network_model"], str):
                raise ValueError("Invalid euphemia_configuration.network_model: must be a string.")
            network_model = cfg["network_model"].upper()
            if network_model not in {"ATC", "FBMC"}:
                raise ValueError("Invalid euphemia_configuration.network_model: must be 'ATC' or 'FBMC'.")
            cfg["network_model"] = network_model

        if "beta_MIC" in cfg and not 0 <= cfg["beta_MIC"] <= 1:
            raise ValueError("Invalid euphemia_configuration.beta_MIC: must be in [0, 1].")
        if "delta_load_gradient" in cfg and cfg["delta_load_gradient"] < 0:
            raise ValueError("Invalid euphemia_configuration.delta_load_gradient: must be >= 0.")
        if "delta_PAB" in cfg and cfg["delta_PAB"] < 0:
            raise ValueError("Invalid euphemia_configuration.delta_PAB: must be >= 0.")
        if "epsilon" in cfg and cfg["epsilon"] <= 0:
            raise ValueError("Invalid euphemia_configuration.epsilon: must be > 0.")
        if "max_iterations" in cfg and cfg["max_iterations"] <= 0:
            raise ValueError("Invalid euphemia_configuration.max_iterations: must be > 0.")
        if "reinsertion_max_iterations" in cfg and cfg["reinsertion_max_iterations"] <= 0:
            raise ValueError("Invalid euphemia_configuration.reinsertion_max_iterations: must be > 0.")
        if (
            "max_prb_reinsertion_attempts" in cfg
            and cfg["max_prb_reinsertion_attempts"] is not None
            and cfg["max_prb_reinsertion_attempts"] <= 0
        ):
            raise ValueError("Invalid euphemia_configuration.max_prb_reinsertion_attempts: must be > 0 or null.")
        if "big_m" in cfg and cfg["big_m"] <= 0:
            raise ValueError("Invalid euphemia_configuration.big_m: must be > 0.")
        if "threads" in cfg and cfg["threads"] < 0:
            raise ValueError("Invalid euphemia_configuration.threads: must be >= 0.")
        if "seed" in cfg and cfg["seed"] < 0:
            raise ValueError("Invalid euphemia_configuration.seed: must be >= 0.")
        if "time_limit" in cfg and cfg["time_limit"] <= 0:
            raise ValueError("Invalid euphemia_configuration.time_limit: must be > 0.")
        if "mip_gap" in cfg and cfg["mip_gap"] < 0:
            raise ValueError("Invalid euphemia_configuration.mip_gap: must be >= 0.")
        if "output_flag" in cfg and cfg["output_flag"] not in [0, 1]:
            raise ValueError("Invalid euphemia_configuration.output_flag: must be 0 or 1.")
        if "lazy_constraints" in cfg and cfg["lazy_constraints"] not in [0, 1]:
            raise ValueError("Invalid euphemia_configuration.lazy_constraints: must be 0 or 1.")

        price_lower = cfg.get("price_lower_bound", -500)
        price_upper = cfg.get("price_upper_bound", 4000)
        if price_lower >= price_upper:
            raise ValueError("Invalid euphemia_configuration: price_lower_bound must be < price_upper_bound.")

    def get_unit_based_dataset(self) -> UnitBased_Datasets:
        return UnitBased_Datasets[self.config["scenario"]["unit_based_dataset"]]

    def get_order_book_based_dataset(self) -> OrderBookBased_Datasets:
        return OrderBookBased_Datasets[self.config["scenario"]["order_book_based_dataset"]]

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
            return Zonal_FBMC(zonal_configuration=zonal_config["type"], base_case_type=base_case)
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

    def get_unit_based_solver_congiruation(self) -> Dict[str, Any]:
        if "unit_based_solver_configuration" in self.config:
            return self.config["unit_based_solver_configuration"]

        raise ValueError("Missing unit-based solver configuration.")

    def get_euphemia_configuration(self) -> Dict[str, Any]:
        return self.config.get("euphemia_configuration", {})


