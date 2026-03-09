import json
from numbers import Integral, Real
from typing import Any, Dict

from apem.EU_market_model.euphemia.enums.cut_types import CutTypes
from apem.EU_market_model.euphemia.enums.datasets import EU_Datasets
from apem.US_market_model.allocation.algorithms.nodal_clearing.dcopf import DCOPF
from apem.US_market_model.allocation.algorithms.zonal_clearing.zonal_fbmc_included import ZonalFBMC
from apem.US_market_model.allocation.algorithms.zonal_clearing.zonal_ntc_multiedge import Zonal_NTC_multiedge
from apem.US_market_model.allocation.algorithms.zonal_clearing.zonal_ntc_aggregated import Zonal_NTC_aggregated
from apem.enums import FBMCBaseCases, MarketModels, PricingAlgorithms, RedispatchAlgorithms, US_Datasets


class ConfigLoader:
    def __init__(self, config_path: str = "config.json"):
        self.config_path = config_path
        self.raw_config = self._normalize_config_format(self._load_raw_config())
        self._validate_config()
        self.config = self._filter_documentation_fields()

    def _load_raw_config(self) -> Dict[str, Any]:
        with open(self.config_path, "r") as f:
            return json.load(f)

    def _normalize_config_format(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        """
        Accept only model-scoped config format ('run', 'us_model', 'eu_model').
        """
        if "run" not in raw:
            raise ValueError(
                "Invalid config format: expected model-scoped format "
                "with a top-level 'run' section."
            )
        return self._normalize_model_scoped_config(raw)

    def _normalize_model_scoped_config(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        run_cfg = raw.get("run", {})
        us_cfg = raw.get("us_model", {})
        eu_cfg = raw.get("eu_model", {})

        if not isinstance(run_cfg, dict):
            raise ValueError("Invalid run: expected an object.")
        if us_cfg is None:
            us_cfg = {}
        if eu_cfg is None:
            eu_cfg = {}
        if not isinstance(us_cfg, dict):
            raise ValueError("Invalid us_model: expected an object.")
        if not isinstance(eu_cfg, dict):
            raise ValueError("Invalid eu_model: expected an object.")

        redispatch_cfg = us_cfg.get("redispatch", {})
        if redispatch_cfg is None:
            redispatch_cfg = {}
        if not isinstance(redispatch_cfg, dict):
            raise ValueError("Invalid us_model.redispatch: expected an object.")

        us_solver_cfg = us_cfg.get("solver_configuration")

        normalized = {
            "verbosity": run_cfg.get("verbosity", raw.get("verbosity", True)),
            "scenario": {
                "market_model": run_cfg.get("market_model", "US_model"),
                "US_dataset": us_cfg.get("dataset", "IEEE_RTS"),
                "EU_dataset": eu_cfg.get("dataset", "GENERATED_SMALL"),
                "power_flow_model": us_cfg.get("power_flow_model", {"type": "DCOPF"}),
                "cut_type": eu_cfg.get("cut_type", CutTypes.PB.value),
                "pricing_algorithm": us_cfg.get("pricing_algorithm", "IP"),
                "redispatch_algorithm": redispatch_cfg.get("algorithm", "MinCostRD"),
                "redispatch_constraint_units": redispatch_cfg.get("constraint_units", False),
                "redispatch_threshold": redispatch_cfg.get("threshold", 0.0),
                "alpha": redispatch_cfg.get("alpha", 0.0),
            },
            "euphemia_configuration": eu_cfg.get("euphemia_configuration", raw.get("euphemia_configuration", {})),
            "zonal_configuration": us_cfg.get(
                "zonal_configuration",
                raw.get("zonal_configuration", {"type": "zonal_DE2-s", "factor": 0.8, "base_case": "BC4"}),
            ),
        }

        if us_solver_cfg is not None:
            normalized["us_solver_configuration"] = us_solver_cfg

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

        self._validate_us_solver_configuration()
        self._validate_euphemia_configuration()

    def _validate_us_solver_configuration(self) -> None:
        if self.raw_config["scenario"]["market_model"] != "US_model":
            return

        if "us_solver_configuration" not in self.raw_config:
            raise ValueError(
                "Missing solver configuration: provide 'us_model.solver_configuration'."
            )

        if not isinstance(self.raw_config["us_solver_configuration"], dict):
            raise ValueError("Invalid us_solver_configuration: expected an object.")

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
            "big_m",
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
        int_fields = {"max_iterations", "reinsertion_max_iterations", "threads", "seed", "output_flag", "lazy_constraints"}
        number_fields = {"price_lower_bound", "price_upper_bound", "beta_MIC", "delta_load_gradient", "delta_PAB", "epsilon", "big_m", "time_limit", "mip_gap"}

        for field in bool_fields:
            if field in cfg and not isinstance(cfg[field], bool):
                raise ValueError(f"Invalid euphemia_configuration.{field}: must be boolean.")
        for field in int_fields:
            if field in cfg and not self._is_int(cfg[field]):
                raise ValueError(f"Invalid euphemia_configuration.{field}: must be integer.")
        for field in number_fields:
            if field in cfg and not self._is_number(cfg[field]):
                raise ValueError(f"Invalid euphemia_configuration.{field}: must be numeric.")

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

    def get_us_solver_configuration(self) -> Dict[str, Any]:
        if "us_solver_configuration" in self.config:
            return self.config["us_solver_configuration"]

        raise ValueError("Missing US solver configuration.")

    def get_euphemia_configuration(self) -> Dict[str, Any]:
        return self.config.get("euphemia_configuration", {})
