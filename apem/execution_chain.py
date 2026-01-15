import os
from typing import Optional, Union

from apem.EU_market_model.euphemia.enums.cut_types import CutTypes
from apem.EU_market_model.euphemia.enums.datasets import EU_Datasets
from apem.EU_market_model.euphemia.execution_chain import solve_euphemia
from apem.US_market_model.allocation.algorithms.nodal_clearing.dcopf import DCOPF
from apem.US_market_model.allocation.algorithms.nodal_clearing.nodal_fbmc_included import NodalFBMC
from apem.US_market_model.allocation.algorithms.zonal_clearing.zonal_fbmc_included import ZonalFBMC
from apem.US_market_model.allocation.algorithms.zonal_clearing.zonal_NTC import Zonal_NTC
from apem.US_market_model.allocation.allocation import SellersAllocation, Allocation
from apem.US_market_model.allocation.configuration import Configuration
from apem.US_market_model.allocation.error import Error
from apem.US_market_model.data.parsing.scenario import Scenario
from apem.US_market_model.pricing.analysis.price_analysis import PriceAnalysis
from apem.US_market_model.pricing.analysis.pricing import Pricing
from apem.config_loader import ConfigLoader
from apem.enums import MarketModels, PowerFlowModels, PricingAlgorithms, RedispatchAlgorithms, US_Datasets
from apem.US_market_model.allocation.power_flow_model import PowerFlowModel


def _retrieve_data(dataset: US_Datasets) -> Scenario:
    return dataset.value.parse_data()


def _create_configuration() -> Configuration:
    """Create a Configuration instance using the current configuration."""
    config = ConfigLoader().get_solver_configuration()
    return Configuration(
        MIP_gap=config.get("MIP_gap", 1e-4),
        optimality_tol=config.get("optimality_tol", 1e-6),
        time_limit=config.get("time_limit", 3600),
        work_limit=config.get("work_limit", 3600),
        threads=config.get("threads", 0),
        presparsify=config.get("presparsify", -1),
        strict_supply_demand_eq=config.get("strict_supply_demand_eq", True),
        relaxation=config.get("relaxation", False),
        output_flag=config.get("output_flag", 0),
        verbosity=config.get("verbosity", True),
    )


def _zonal_part(power_flow_model: PowerFlowModel) -> str:
    """Encodes zonal configuration (and influencing params) into the result path."""
    if isinstance(power_flow_model, ZonalFBMC):
        base_case = getattr(power_flow_model, "base_case_type", "")
        suffix = f"{power_flow_model.zonal_configuration}"
        if base_case:
            suffix += f"_{base_case}"
        return f"{suffix}/"
    if isinstance(power_flow_model, Zonal_NTC):
        factor = getattr(power_flow_model, "factor", None)
        factor_str = f"_f{factor}" if factor is not None else ""
        return f"{power_flow_model.zonal_configuration}{factor_str}/"
    return ""


def _write_run_metadata(dataset: US_Datasets, scenario: Scenario, power_flow_model: PowerFlowModel,
                        pricing_algorithm: PricingAlgorithms, redispatch_algorithm: RedispatchAlgorithms,
                        zonal_part: str) -> None:
    """Persist a quick summary of the run configuration alongside results."""
    base_dir = f"US_results/{scenario}_results"
    os.makedirs(base_dir, exist_ok=True)
    meta_path = os.path.join(base_dir, "run_config.txt")
    with open(meta_path, "w") as f:
        f.write(f"dataset={dataset.name}\n")
        f.write(f"power_flow_model={power_flow_model}\n")
        if zonal_part:
            f.write(f"zonal_path={zonal_part.rstrip('/')}\n")
        if isinstance(power_flow_model, ZonalFBMC):
            f.write(f"base_case={getattr(power_flow_model, 'base_case_type', '')}\n")
        if isinstance(power_flow_model, Zonal_NTC):
            f.write(f"factor={getattr(power_flow_model, 'factor', '')}\n")
        f.write(f"pricing_algorithm={pricing_algorithm.name}\n")
        f.write(f"redispatch_algorithm={redispatch_algorithm.name}\n")


def _solve_US_allocation_problem(
    scenario: Scenario, power_flow_model: PowerFlowModel, configuration: Configuration, u_fixed: Optional[dict] = None
):
    if configuration.verbosity:
        print(f"Starting allocation problem for {scenario} using {power_flow_model}...")

    zonal_part = _zonal_part(power_flow_model)
    base_path = f"US_results/{scenario}_results/{power_flow_model}"
    path = base_path + "/" + zonal_part + "allocation_results"
    os.makedirs(path, exist_ok=True)

    return power_flow_model.solve(
        scenario,
        configuration,
        results_file=path + f"/{power_flow_model}.csv",
        stats_file=path + f"/{power_flow_model}_stats.txt",
        u_fixed=u_fixed,
    )


def _solve_US_redispatch_problem(
    scenario: Scenario,
    power_flow_model: PowerFlowModel,
    redispatch_algorithm: RedispatchAlgorithms,
    nodal_scenario: Scenario,
    zonal_allocation: SellersAllocation,
    configuration: Configuration,
    redispatch_constraint_units: bool,
    redispatch_threshold: float,
) -> Union[Allocation, Error]:
    if configuration.verbosity:
        print(f"Starting redispatch problem using {redispatch_algorithm}...")
    redispatch_algorithm = redispatch_algorithm.value

    zonal_part = _zonal_part(power_flow_model)
    base_path = f"US_results/{scenario}_results/{power_flow_model}"
    path = base_path + "/" + zonal_part + "allocation_results/redispatch"
    os.makedirs(path, exist_ok=True)

    return redispatch_algorithm.compute_redispatch(
        nodal_scenario,
        zonal_allocation,
        configuration,
        path,
        redispatch_constraint_units,
        redispatch_threshold,
    )


def _solve_US_pricing_problem(
    scenario: Scenario,
    allocation: Allocation,
    pricing_algorithm: PricingAlgorithms,
    power_flow_model: PowerFlowModel,
    configuration: Configuration,
    prices=None,
) -> Pricing:
    if configuration.verbosity:
        print(f"Starting pricing problem using {pricing_algorithm}...")

    pricing_algorithm = pricing_algorithm.value

    zonal_part = _zonal_part(power_flow_model)
    path = f"US_results/{scenario}_results/{power_flow_model}/{zonal_part}{pricing_algorithm}_results"
    os.makedirs(path, exist_ok=True)

    pricing = pricing_algorithm.compute_prices(
        allocation,
        scenario,
        configuration,
        file_prices=path + f"/{pricing_algorithm}_prices.csv",
        fixed_prices=prices,
    )
    return pricing


def analyse_results(
    scenario: Scenario,
    allocation: Allocation,
    pricing: Pricing,
    configuration: Configuration,
    pf_model_value,
    base_scenario: Optional[Scenario] = None,
) -> PriceAnalysis:
    """Performs several analyses."""
    path = f"US_results/{scenario}_results"
    os.makedirs(path, exist_ok=True)

    analysis = PriceAnalysis(scenario, allocation, pricing, configuration, base_scenario)
    analysis.compute_all_stats_and_plot_data(path, pf_model_value)
    return analysis


def solve_US_scenario(
    dataset: US_Datasets,
    power_flow_model: PowerFlowModel,
    pricing_algorithm: PricingAlgorithms,
    redispatch_algorithm: RedispatchAlgorithms = RedispatchAlgorithms.MinCostRD,
    redispatch_constraint_units: bool = False,
    redispatch_threshold: float = 0,
) -> PriceAnalysis:
    """Computes allocation and pricing for some scenario."""
    scenario = _retrieve_data(dataset)
    configuration = _create_configuration()
    zonal_part = _zonal_part(power_flow_model)
    _write_run_metadata(dataset, scenario, power_flow_model, pricing_algorithm, redispatch_algorithm, zonal_part)

    if isinstance(power_flow_model, DCOPF):
        allocation = _solve_US_allocation_problem(scenario, power_flow_model, configuration)
        if isinstance(allocation, Error):
            raise RuntimeError(f"{power_flow_model} allocation failed with status {allocation.status}.")
        pricing = _solve_US_pricing_problem(scenario, allocation, pricing_algorithm, power_flow_model, configuration)
        if isinstance(pricing, Error) or getattr(pricing, "status", 0) != 1:
            raise RuntimeError(f"{power_flow_model} pricing failed with status {getattr(pricing, 'status', 'unknown')}.")
        return PriceAnalysis(scenario, allocation, pricing, configuration)

    if dataset not in [US_Datasets.PyPSAEurLarge, US_Datasets.PyPSAEurSmall]:
        raise ValueError(
            f"The dataset {dataset.name} cannot be used in combination with the power flow model "
            f"{power_flow_model}. Zonal prices can only be computed for the PyPSA datasets."
        )

    zonal_scenario, allocation = _solve_US_allocation_problem(scenario, power_flow_model, configuration)

    _solve_US_redispatch_problem(
        zonal_scenario,
        power_flow_model,
        redispatch_algorithm=redispatch_algorithm,
        nodal_scenario=scenario,
        configuration=configuration,
        zonal_allocation=allocation.SellersAllocation,
        redispatch_constraint_units=redispatch_constraint_units,
        redispatch_threshold=redispatch_threshold,
    )

    pricing = _solve_US_pricing_problem(zonal_scenario, allocation, pricing_algorithm, power_flow_model, configuration)
    return PriceAnalysis(zonal_scenario, allocation, pricing, configuration, scenario)


def solve_and_analyse_scenario(
    US_dataset: US_Datasets,
    EU_dataset: EU_Datasets,
    market_model: MarketModels,
    power_flow_model: PowerFlowModel,
    cut_type: CutTypes,
    pricing_algorithm: PricingAlgorithms,
    redispatch_algorithm: RedispatchAlgorithms = RedispatchAlgorithms.MinCostRD,
    redispatch_constraint_units: bool = False,
    redispatch_threshold: float = 0,
    alpha: float = 0,
):
    """Computes allocation and pricing for some scenario and performs several analyses."""
    if market_model == MarketModels.EU_model:
        solve_euphemia(EU_dataset, cut_type)
        return

    if market_model != MarketModels.US_model:
        raise ValueError(f"Unsupported market model: {market_model}")

    if pricing_algorithm != PricingAlgorithms.Markup:
        price_analysis = solve_US_scenario(
            US_dataset,
            power_flow_model,
            pricing_algorithm,
            redispatch_algorithm,
            redispatch_constraint_units,
            redispatch_threshold,
        )
        is_pypsa_dataset = US_dataset in [US_Datasets.PyPSAEurLarge, US_Datasets.PyPSAEurSmall]
        base_scenario = None

        if is_pypsa_dataset:
            is_dcopf_like = isinstance(power_flow_model, (DCOPF, NodalFBMC))
            scenario_to_analyse = price_analysis.scenario if is_dcopf_like else price_analysis.base_scenario
            base_scenario = None if is_dcopf_like else price_analysis.base_scenario
            zonal_config = _zonal_part(power_flow_model).rstrip("/") if isinstance(power_flow_model, (Zonal_NTC, ZonalFBMC)) else ""

            scenario_to_analyse.analyse_scenario()  # analyse base scenario
            scenario_to_analyse.plot_network(power_flow_model, zonal_config)  # plot underlying network

        return analyse_results(
            price_analysis.scenario,
            price_analysis.allocation,
            price_analysis.pricing,
            price_analysis.configuration,
            power_flow_model,
            base_scenario,
        )

    scenario = _retrieve_data(US_dataset)
    configuration = _create_configuration()

    zonal_part = _zonal_part(power_flow_model)
    base_path = f"US_results/{scenario}_results/{power_flow_model}"
    path = base_path + "/" + zonal_part
    os.makedirs(path, exist_ok=True)

    allocation, pricing = pricing_algorithm.Markup.value.compute_prices(
        scenario,
        configuration,
        file_prices=path + f"/{pricing_algorithm.value}_results.csv",
        alpha=alpha,
    )
    price_analysis = PriceAnalysis(
        scenario=scenario,
        allocation=allocation,
        pricing=pricing,
        configuration=configuration,
        base_scenario=scenario,
    )

    analyse_results(
        price_analysis.scenario,
        price_analysis.allocation,
        price_analysis.pricing,
        price_analysis.configuration,
        power_flow_model,
    )
