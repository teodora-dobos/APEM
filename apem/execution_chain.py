import logging
import os
from datetime import datetime, timezone
from typing import Optional, Union
from uuid import uuid4

from apem.order_book_based_model.euphemia.enums.cut_types import CutTypes
from apem.order_book_based_model.euphemia.enums.datasets import OrderBookBased_Datasets
from apem.order_book_based_model.euphemia.runner import solve_euphemia
from apem.unit_based_model.allocation.algorithms.nodal_clearing.dcopf import DCOPF
from apem.unit_based_model.allocation.algorithms.nodal_clearing.nodal_fbmc_included import NodalFBMC
from apem.unit_based_model.allocation.algorithms.zonal_clearing.zonal_fbmc_included import Zonal_FBMC
from apem.unit_based_model.allocation.algorithms.zonal_clearing.zonal_ntc_aggregated import Zonal_NTC_aggregated
from apem.unit_based_model.allocation.algorithms.zonal_clearing.zonal_ntc_multiedge import Zonal_NTC_multiedge
from apem.unit_based_model.allocation.allocation import SellersAllocation, Allocation
from apem.unit_based_model.solver_configuration import SolverConfiguration
from apem.unit_based_model.error import Error
from apem.unit_based_model.data.parsing.scenario import Scenario
from apem.unit_based_model.pricing.analysis.price_analysis import PriceAnalysis
from apem.unit_based_model.pricing.analysis.pricing import Pricing
from apem.config_loader import ConfigLoader
from apem.core import MarketModels
from apem.unit_based_model.enums import PowerFlowModels, PricingAlgorithms, RedispatchAlgorithms, UnitBased_Datasets
from apem.unit_based_model.allocation.power_flow_model import PowerFlowModel

logger = logging.getLogger(__name__)
if not logger.handlers:
    logging.basicConfig(level=logging.INFO, format="%(message)s")


def _announce_results_path(results_root: Optional[str]) -> None:
    """Print the run output directory to the console."""
    if not results_root:
        return
    logger.info("Results written to: %s", os.path.abspath(results_root))


def _new_run_id() -> str:
    """Create a unique run id with UTC timestamp and random suffix."""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{timestamp}_{uuid4().hex[:8]}"


def _retrieve_data(dataset: UnitBased_Datasets) -> Scenario:
    """Load and parse a unit-based dataset into a Scenario object."""
    return dataset.value.parse_data()


def _create_configuration() -> SolverConfiguration:
    """Create a SolverConfiguration instance using the current configuration."""
    config = ConfigLoader().get_unit_based_solver_congiruation()
    return SolverConfiguration(
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
        slack_penalty=config.get("slack_penalty", 1e15),
    )


def _zonal_part(power_flow_model: PowerFlowModel) -> str:
    """Encodes zonal configuration (and influencing params) into the result path."""
    if isinstance(power_flow_model, Zonal_FBMC):
        base_case = getattr(power_flow_model, "base_case_type", "")
        suffix = f"{power_flow_model.zonal_configuration}"
        if base_case:
            suffix += f"_{base_case}"
        return f"{suffix}/"
    if isinstance(power_flow_model, (Zonal_NTC_aggregated, Zonal_NTC_multiedge)):
        factor = getattr(power_flow_model, "factor", None)
        factor_str = f"_f{factor}" if factor is not None else ""
        return f"{power_flow_model.zonal_configuration}{factor_str}/"
    return ""


def _write_run_metadata(dataset: UnitBased_Datasets, scenario: Scenario, power_flow_model: PowerFlowModel,
                        pricing_algorithm: Optional[PricingAlgorithms], redispatch_algorithm: Optional[RedispatchAlgorithms],
                        zonal_part: str, run_root: str, run_id: str) -> None:
    """Persist a quick summary of the run configuration alongside results."""
    base_dir = run_root
    os.makedirs(base_dir, exist_ok=True)
    meta_path = os.path.join(base_dir, "run_config.txt")
    with open(meta_path, "w") as f:
        f.write(f"run_id={run_id}\n")
        f.write(f"created_at_utc={datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')}\n")
        f.write(f"dataset={dataset.name}\n")
        f.write(f"power_flow_model={power_flow_model}\n")
        if zonal_part:
            f.write(f"zonal_path={zonal_part.rstrip('/')}\n")
        if isinstance(power_flow_model, Zonal_FBMC):
            f.write(f"base_case={getattr(power_flow_model, 'base_case_type', '')}\n")
        if isinstance(power_flow_model, (Zonal_NTC_aggregated, Zonal_NTC_multiedge)):
            f.write(f"factor={getattr(power_flow_model, 'factor', '')}\n")
        if pricing_algorithm is not None:
            f.write(f"pricing_algorithm={pricing_algorithm.name}\n")
        if redispatch_algorithm is not None:
            f.write(f"redispatch_algorithm={redispatch_algorithm.name}\n")


def _solve_unit_based_allocation_problem(
    scenario: Scenario,
    power_flow_model: PowerFlowModel,
    configuration: SolverConfiguration,
    run_root: str,
    u_fixed: Optional[dict] = None,
):
    if configuration.verbosity:
        extra = ""
        if isinstance(power_flow_model, Zonal_FBMC):
            extra = f" base_case={getattr(power_flow_model, 'base_case_type', '')}"
        if isinstance(power_flow_model, (Zonal_NTC_aggregated, Zonal_NTC_multiedge)):
            extra = f" factor={getattr(power_flow_model, 'factor', '')}"
        logger.info("allocation start dataset=%s model=%s%s", scenario, power_flow_model, extra)

    zonal_part = _zonal_part(power_flow_model)
    base_path = f"{run_root}/{power_flow_model}"
    path = base_path + "/" + zonal_part + "allocation_results"
    os.makedirs(path, exist_ok=True)

    return power_flow_model.solve(
        scenario,
        configuration,
        results_file=path + f"/{power_flow_model}.csv",
        stats_file=path + f"/{power_flow_model}_stats.txt",
        u_fixed=u_fixed,
    )


def _solve_unit_based_redispatch_problem(
    scenario: Scenario,
    power_flow_model: PowerFlowModel,
    redispatch_algorithm: RedispatchAlgorithms,
    nodal_scenario: Scenario,
    zonal_allocation: SellersAllocation,
    configuration: SolverConfiguration,
    redispatch_constraint_units: bool,
    redispatch_threshold: float,
    run_root: str,
) -> Union[Allocation, Error]:
    if configuration.verbosity:
        logger.info("redispatch start algo=%s model=%s dataset=%s", redispatch_algorithm, power_flow_model, scenario)
    redispatch_algorithm = redispatch_algorithm.value

    zonal_part = _zonal_part(power_flow_model)
    base_path = f"{run_root}/{power_flow_model}"
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


def _solve_unit_based_pricing_problem(
    scenario: Scenario,
    allocation: Allocation,
    pricing_algorithm: PricingAlgorithms,
    power_flow_model: PowerFlowModel,
    configuration: SolverConfiguration,
    run_root: str,
    prices=None,
) -> Pricing:
    if configuration.verbosity:
        logger.info("pricing start algo=%s model=%s dataset=%s", pricing_algorithm, power_flow_model, scenario)

    pricing_algorithm = pricing_algorithm.value

    zonal_part = _zonal_part(power_flow_model)
    path = f"{run_root}/{power_flow_model}/{zonal_part}{pricing_algorithm}_results"
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
    configuration: SolverConfiguration,
    pf_model_value,
    base_scenario: Optional[Scenario] = None,
    results_root: Optional[str] = None,
) -> PriceAnalysis:
    """Run post-pricing analysis and write stats/plot data to the run folder.

    This validates that pricing succeeded, builds a ``PriceAnalysis`` object,
    computes all configured analysis outputs, and returns the populated
    analysis instance.
    """
    if isinstance(pricing, Error) or getattr(pricing, "status", 0) != 1:
        raise RuntimeError(
            f"Cannot analyse results because pricing failed with status {getattr(pricing, 'status', 'unknown')}."
        )

    path = results_root or f"results/unit_based_model/{scenario}_results"
    os.makedirs(path, exist_ok=True)

    analysis = PriceAnalysis(scenario, allocation, pricing, configuration, base_scenario)
    analysis.compute_all_stats_and_plot_data(path, pf_model_value)
    return analysis


def solve_unit_based_allocation_only(
    dataset: UnitBased_Datasets,
    power_flow_model: PowerFlowModel,
) -> str:
    """Compute only the allocation stage and return the run root for welfare-style analyses."""
    scenario = _retrieve_data(dataset)
    configuration = _create_configuration()
    run_id = _new_run_id()
    run_root = f"results/unit_based_model/{scenario}_results/{run_id}"
    zonal_part = _zonal_part(power_flow_model)
    _write_run_metadata(
        dataset,
        scenario,
        power_flow_model,
        pricing_algorithm=None,
        redispatch_algorithm=None,
        zonal_part=zonal_part,
        run_root=run_root,
        run_id=run_id,
    )

    if isinstance(power_flow_model, DCOPF):
        allocation = _solve_unit_based_allocation_problem(
            scenario,
            power_flow_model,
            configuration,
            run_root=run_root,
        )
        if isinstance(allocation, Error):
            raise RuntimeError(f"{power_flow_model} allocation failed with status {allocation.status}.")
        return run_root

    if dataset not in [UnitBased_Datasets.PyPSAEurLarge, UnitBased_Datasets.PyPSAEurSmall]:
        raise ValueError(
            f"The dataset {dataset.name} cannot be used in combination with the power flow model "
            f"{power_flow_model}. Zonal prices can only be computed for the PyPSA datasets."
        )

    zonal_scenario, allocation = _solve_unit_based_allocation_problem(
        scenario,
        power_flow_model,
        configuration,
        run_root=run_root,
    )
    if isinstance(allocation, Error):
        raise RuntimeError(f"{power_flow_model} allocation failed with status {allocation.status}.")
    return run_root


def solve_unit_based_allocation_and_redispatch_only(
    dataset: UnitBased_Datasets,
    power_flow_model: PowerFlowModel,
    redispatch_algorithm: RedispatchAlgorithms = RedispatchAlgorithms.MinCostRD,
    redispatch_constraint_units: bool = False,
    redispatch_threshold: float = 0,
) -> str:
    """Compute allocation plus redispatch only and return the run root for redispatch analyses."""
    scenario = _retrieve_data(dataset)
    configuration = _create_configuration()
    run_id = _new_run_id()
    run_root = f"results/unit_based_model/{scenario}_results/{run_id}"
    zonal_part = _zonal_part(power_flow_model)
    _write_run_metadata(
        dataset,
        scenario,
        power_flow_model,
        pricing_algorithm=None,
        redispatch_algorithm=redispatch_algorithm,
        zonal_part=zonal_part,
        run_root=run_root,
        run_id=run_id,
    )

    if isinstance(power_flow_model, DCOPF):
        raise ValueError("Redispatch requires a zonal power-flow model.")

    if dataset not in [UnitBased_Datasets.PyPSAEurLarge, UnitBased_Datasets.PyPSAEurSmall]:
        raise ValueError(
            f"The dataset {dataset.name} cannot be used in combination with the power flow model "
            f"{power_flow_model}. Zonal redispatch can only be computed for the PyPSA datasets."
        )

    zonal_scenario, allocation = _solve_unit_based_allocation_problem(
        scenario,
        power_flow_model,
        configuration,
        run_root=run_root,
    )
    if isinstance(allocation, Error):
        raise RuntimeError(f"{power_flow_model} allocation failed with status {allocation.status}.")

    redispatch_result = _solve_unit_based_redispatch_problem(
        zonal_scenario,
        power_flow_model,
        redispatch_algorithm=redispatch_algorithm,
        nodal_scenario=scenario,
        configuration=configuration,
        zonal_allocation=allocation.SellersAllocation,
        redispatch_constraint_units=redispatch_constraint_units,
        redispatch_threshold=redispatch_threshold,
        run_root=run_root,
    )
    if isinstance(redispatch_result, Error):
        raise RuntimeError(
            f"{power_flow_model} redispatch failed with status {redispatch_result.status}."
        )
    return run_root


def solve_unit_based_scenario(
    dataset: UnitBased_Datasets,
    power_flow_model: PowerFlowModel,
    pricing_algorithm: PricingAlgorithms,
    redispatch_algorithm: RedispatchAlgorithms = RedispatchAlgorithms.MinCostRD,
    redispatch_constraint_units: bool = False,
    redispatch_threshold: float = 0,
) -> PriceAnalysis:
    """Run allocation and pricing for one unit-based scenario."""
    scenario = _retrieve_data(dataset)
    configuration = _create_configuration()
    run_id = _new_run_id()
    run_root = f"results/unit_based_model/{scenario}_results/{run_id}"
    zonal_part = _zonal_part(power_flow_model)
    _write_run_metadata(
        dataset,
        scenario,
        power_flow_model,
        pricing_algorithm,
        redispatch_algorithm,
        zonal_part,
        run_root=run_root,
        run_id=run_id,
    )

    if isinstance(power_flow_model, DCOPF):
        allocation = _solve_unit_based_allocation_problem(
            scenario, power_flow_model, configuration, run_root=run_root
        )
        if isinstance(allocation, Error):
            raise RuntimeError(f"{power_flow_model} allocation failed with status {allocation.status}.")
        pricing = _solve_unit_based_pricing_problem(
            scenario,
            allocation,
            pricing_algorithm,
            power_flow_model,
            configuration,
            run_root=run_root,
        )
        if isinstance(pricing, Error) or getattr(pricing, "status", 0) != 1:
            raise RuntimeError(f"{power_flow_model} pricing failed with status {getattr(pricing, 'status', 'unknown')}.")
        analysis = PriceAnalysis(scenario, allocation, pricing, configuration)
        analysis.results_root = run_root
        return analysis

    if dataset not in [UnitBased_Datasets.PyPSAEurLarge, UnitBased_Datasets.PyPSAEurSmall]:
        raise ValueError(
            f"The dataset {dataset.name} cannot be used in combination with the power flow model "
            f"{power_flow_model}. Zonal prices can only be computed for the PyPSA datasets."
        )

    zonal_scenario, allocation = _solve_unit_based_allocation_problem(
        scenario,
        power_flow_model,
        configuration,
        run_root=run_root,
    )
    if isinstance(allocation, Error):
        raise RuntimeError(f"{power_flow_model} allocation failed with status {allocation.status}.")

    redispatch_result = _solve_unit_based_redispatch_problem(
        zonal_scenario,
        power_flow_model,
        redispatch_algorithm=redispatch_algorithm,
        nodal_scenario=scenario,
        configuration=configuration,
        zonal_allocation=allocation.SellersAllocation,
        redispatch_constraint_units=redispatch_constraint_units,
        redispatch_threshold=redispatch_threshold,
        run_root=run_root,
    )
    if isinstance(redispatch_result, Error):
        raise RuntimeError(
            f"{power_flow_model} redispatch failed with status {redispatch_result.status}."
        )

    pricing = _solve_unit_based_pricing_problem(
        zonal_scenario,
        allocation,
        pricing_algorithm,
        power_flow_model,
        configuration,
        run_root=run_root,
    )
    if isinstance(pricing, Error) or getattr(pricing, "status", 0) != 1:
        raise RuntimeError(f"{power_flow_model} pricing failed with status {getattr(pricing, 'status', 'unknown')}.")
    analysis = PriceAnalysis(zonal_scenario, allocation, pricing, configuration, scenario)
    analysis.results_root = run_root
    return analysis


def solve_and_analyse_scenario(
    unit_based_dataset: UnitBased_Datasets,
    order_book_based_dataset: OrderBookBased_Datasets,
    market_model: MarketModels,
    power_flow_model: PowerFlowModel,
    cut_type: CutTypes,
    pricing_algorithm: PricingAlgorithms,
    redispatch_algorithm: RedispatchAlgorithms = RedispatchAlgorithms.MinCostRD,
    redispatch_constraint_units: bool = False,
    redispatch_threshold: float = 0,
    alpha: float = 0,
):
    """Run the selected market-model workflow and produce analysis outputs.

    For ``order_book_based_model``, this executes the Euphemia pipeline.
    For ``unit_based_model``, this runs allocation/pricing (and redispatch when
    applicable) and then computes analysis artifacts.
    """
    if market_model == MarketModels.order_book_based_model:
        euphemia_config = ConfigLoader().get_euphemia_configuration()
        results_root = solve_euphemia(order_book_based_dataset, cut_type, euphemia_config)
        _announce_results_path(results_root)
        return

    if market_model != MarketModels.unit_based_model:
        raise ValueError(f"Unsupported market model: {market_model}")

    if pricing_algorithm != PricingAlgorithms.Markup:
        price_analysis = solve_unit_based_scenario(
            unit_based_dataset,
            power_flow_model,
            pricing_algorithm,
            redispatch_algorithm,
            redispatch_constraint_units,
            redispatch_threshold,
        )
        is_pypsa_dataset = unit_based_dataset in [UnitBased_Datasets.PyPSAEurLarge, UnitBased_Datasets.PyPSAEurSmall]
        base_scenario = None

        if is_pypsa_dataset:
            is_dcopf_like = isinstance(power_flow_model, (DCOPF, NodalFBMC))
            scenario_to_analyse = price_analysis.scenario if is_dcopf_like else price_analysis.base_scenario
            base_scenario = None if is_dcopf_like else price_analysis.base_scenario
            zonal_config = _zonal_part(power_flow_model).rstrip("/") if isinstance(power_flow_model, (Zonal_NTC_aggregated, Zonal_NTC_multiedge, Zonal_FBMC)) else ""

            run_root = getattr(price_analysis, "results_root", None)
            scenario_to_analyse.analyse_scenario(results_root=run_root)  # analyse base scenario
            scenario_to_analyse.plot_network(power_flow_model, zonal_config, results_root=run_root)  # plot underlying network

        analysis = analyse_results(
            price_analysis.scenario,
            price_analysis.allocation,
            price_analysis.pricing,
            price_analysis.configuration,
            power_flow_model,
            base_scenario,
            results_root=getattr(price_analysis, "results_root", None),
        )
        _announce_results_path(getattr(price_analysis, "results_root", None))
        return analysis

    scenario = _retrieve_data(unit_based_dataset)
    configuration = _create_configuration()
    run_id = _new_run_id()
    run_root = f"results/unit_based_model/{scenario}_results/{run_id}"
    zonal_part = _zonal_part(power_flow_model)
    os.makedirs(run_root, exist_ok=True)
    _write_run_metadata(
        unit_based_dataset,
        scenario,
        power_flow_model,
        pricing_algorithm,
        redispatch_algorithm,
        zonal_part,
        run_root=run_root,
        run_id=run_id,
    )

    allowed_markup = {UnitBased_Datasets.IEEE_RTS, UnitBased_Datasets.PJM, UnitBased_Datasets.ARPA}
    if unit_based_dataset not in allowed_markup:
        raise ValueError(f"Markup pricing is only supported for datasets {', '.join([d.name for d in allowed_markup])}.")

    base_path = f"{run_root}/{power_flow_model}"
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
    price_analysis.results_root = run_root

    analysis = analyse_results(
        price_analysis.scenario,
        price_analysis.allocation,
        price_analysis.pricing,
        price_analysis.configuration,
        power_flow_model,
        results_root=run_root,
    )
    _announce_results_path(run_root)
    return analysis
