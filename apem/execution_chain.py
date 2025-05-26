import os
from enum import Enum
from typing import Optional, Union, Dict, Any

from apem.allocation.algorithms.nodal_clearing.dcopf import DCOPF
from apem.allocation.algorithms.zonal_clearing.zonal_NTC import Zonal_NTC
from apem.allocation.allocation import SellersAllocation, Allocation
from apem.allocation.configuration import Configuration
from apem.allocation.error import Error
from apem.data.parsing.parse_arpa import ParseARPA
from apem.data.parsing.parse_ieee_rts import ParseIEEERTS
from apem.data.parsing.parse_pjm import ParsePJM
from apem.data.parsing.parse_pypsa_eur_large import ParsePyPSAEurLarge
from apem.data.parsing.parse_pypsa_eur_small import ParsePyPSAEurSmall
from apem.data.parsing.scenario import Scenario
from apem.pricing.algorithms.elmp import ELMP
from apem.pricing.algorithms.ip import IP
from apem.pricing.algorithms.join import Join
from apem.pricing.algorithms.min_mwp import MinMWP
from apem.pricing.analysis.price_analysis import PriceAnalysis
from apem.allocation.algorithms.zonal_clearing.redispatch.min_cost import MinCostRD
from apem.allocation.algorithms.zonal_clearing.redispatch.min_vol import MinVolRD
from apem.pricing.analysis.pricing import Pricing
from apem.config_loader import ConfigLoader
from apem.enums import Datasets, PricingAlgorithms, RedispatchAlgorithms, PowerFlowModels
from apem.allocation.power_flow_model import PowerFlowModel
from apem.config_loader import ConfigLoader
from apem.enums import Datasets, PricingAlgorithms, RedispatchAlgorithms, PowerFlowModels
from apem.allocation.power_flow_model import PowerFlowModel

def _retrieve_data(dataset: Datasets) -> Scenario:
    return dataset.value.parse_data()

def _create_configuration() -> Configuration:
    """Create a Configuration instance using the current configuration."""
    config = ConfigLoader().get_solver_configuration()
    return Configuration(
        MIP_gap=config.get('MIP_gap', 1e-4),
        optimality_tol=config.get('optimality_tol', 1e-6),
        time_limit=config.get('time_limit', 3600),
        work_limit=config.get('work_limit', 3600),
        threads=config.get('threads', 0),
        presparsify=config.get('presparsify', -1),
        strict_supply_demand_eq=config.get('strict_supply_demand_eq', True),
        relaxation=config.get('relaxation', False),
        output_flag=config.get('output_flag', 0),
        verbosity=config.get('verbosity', True)
    )



def _solve_allocation_problem(scenario: Scenario, power_flow_model: PowerFlowModel, configuration: Configuration,
                              u_fixed: Optional[dict] = None):
    if configuration.verbosity:
        print(f"Starting allocation problem for {scenario} using {power_flow_model}...")

    zonal_part = f"{power_flow_model.zonal_configuration}/" if isinstance(power_flow_model, Zonal_NTC) else ""
    base_path = f"results/{scenario}_results/{power_flow_model}"
    path = base_path + "/" + zonal_part + "allocation_results"
    os.makedirs(path, exist_ok=True)

    return power_flow_model.solve(scenario, configuration, results_file=path + f'/{power_flow_model}.csv',
                                  stats_file=path + f'/{power_flow_model}_stats.txt', u_fixed=u_fixed)


def _solve_redispatch_problem(scenario: Scenario, power_flow_model: PowerFlowModel,
                              redispatch_algorithm: RedispatchAlgorithms, nodal_scenario: Scenario,
                              zonal_allocation: SellersAllocation,
                              configuration: Configuration) -> Union[Allocation, Error]:
    if configuration.verbosity:
        print(f"Starting redispatch problem using {redispatch_algorithm}...")
    redispatch_algorithm = redispatch_algorithm.value

    zonal_part = f"{power_flow_model.zonal_configuration}/" if isinstance(power_flow_model, Zonal_NTC) else ""
    base_path = f"results/{scenario}_results/{power_flow_model}"
    path = base_path + "/" + zonal_part + "allocation_results/redispatch"
    os.makedirs(path, exist_ok=True)

    return redispatch_algorithm.compute_redispatch(nodal_scenario, zonal_allocation, configuration, path)


def _solve_pricing_problem(scenario: Scenario, allocation: Allocation, pricing_algorithm: PricingAlgorithms,
                           power_flow_model: PowerFlowModel, configuration: Configuration, prices=None) -> Pricing:
    if configuration.verbosity:
        print(f"Starting pricing problem using {pricing_algorithm}...")

    pricing_algorithm = pricing_algorithm.value

    zonal_part = f"{power_flow_model.zonal_configuration}/" if isinstance(power_flow_model, Zonal_NTC) else ""
    path = f"results/{scenario}_results/{power_flow_model}/{zonal_part}{pricing_algorithm}_results"
    os.makedirs(path, exist_ok=True)

    pricing = pricing_algorithm.compute_prices(allocation, scenario, configuration,
                                               file_prices=path + f"/{pricing_algorithm}_prices.csv",
                                               fixed_prices=prices)
    return pricing


def analyse_results(scenario: Scenario, allocation: Allocation, pricing: Pricing, configuration: Configuration, pf_model_value, 
                    base_scenario: Optional[Scenario] = None) -> PriceAnalysis:
    """Performs several analyses.
    
    Args:
        scenario (Scenario): dataset for which the price analysis is to be performed
        allocation (Allocation): precomputed allocation
        pricing (Pricing): precomputed pricing
        pf_model_value (DCOPF | Zonal_NTC): power flow model information
        base_scenario (Scenario, optional): nodal base scenario for zonal pricing, defaults to None
        
    Returns:
        PricingAnalysis object
    """
    path = f"results/{scenario}_results"
    os.makedirs(path, exist_ok=True)

    analysis = PriceAnalysis(scenario, allocation, pricing, configuration, base_scenario)
    analysis.compute_all_stats_and_plot_data(path, pf_model_value)

    return analysis


def solve_scenario(dataset: Datasets, power_flow_model: PowerFlowModel, pricing_algorithm: PricingAlgorithms,
                   redispatch_algorithm: RedispatchAlgorithms = RedispatchAlgorithms.MinCostRD) -> PriceAnalysis:
    """Computes allocation and pricing for some scenario.

    Args:
        dataset (Datasets): dataset for which allocation and pricing are computed
        power_flow_model (PowerFlowModels): power flow model for which allocation and pricing are computed
        pricing_algorithm (PricingAlgorithms): pricing algorithm used for the pricing computations
        redispatch_algorithm (RedispatchAlgorithms): redispatch algorithm used to solve the redispatch problem

    Raises:
        ValueError: power flow model 'Zonal_NTC' can only be used in combination with one of the PyPSA datasets

    Returns:
        PriceAnalysis object
    """
    scenario = _retrieve_data(dataset)
    configuration = _create_configuration()
    
    if isinstance(power_flow_model, DCOPF):
        allocation = _solve_allocation_problem(scenario, power_flow_model, configuration)
        pricing = _solve_pricing_problem(scenario, allocation, pricing_algorithm, power_flow_model, configuration)
        return PriceAnalysis(scenario, allocation, pricing, configuration)
        
    else:
        if dataset not in [Datasets.PyPSAEurLarge, Datasets.PyPSAEurSmall]:
            raise ValueError(
                f"The dataset {dataset.name} cannot be used in combination with the power flow model \
                {power_flow_model.value}. Zonal prices can only be computed for the PyPSA datasets."
            )

        zonal_scenario, allocation = _solve_allocation_problem(scenario, power_flow_model, configuration)

        _solve_redispatch_problem(zonal_scenario, power_flow_model, redispatch_algorithm=redispatch_algorithm,
                                  nodal_scenario=scenario, configuration=configuration,
                                  zonal_allocation=allocation.SellersAllocation) # TODO: warum 2x scenario als Input?

        pricing = _solve_pricing_problem(zonal_scenario, allocation, pricing_algorithm, power_flow_model, configuration)
        return PriceAnalysis(zonal_scenario, allocation, pricing, configuration, scenario)


def solve_and_analyse_scenario(dataset: Datasets, power_flow_model: PowerFlowModel,
                               pricing_algorithm: PricingAlgorithms,
                               redispatch_algorithm: RedispatchAlgorithms = RedispatchAlgorithms.MinCostRD):
    """Computes allocation and pricing for some scenario and performs several analyses.

    Args:
        dataset (Datasets): dataset for which allocation and pricing are computed
        power_flow_model (PowerFlowModels): power flow model for which allocation and pricing are computed
        pricing_algorithm (PricingAlgorithms): pricing algorithm used for the pricing computations
        redispatch_algorithm (RedispatchAlgorithms): redispatch algorithm used for solving the redispatch problem

    Raises:
        ValueError: power flow model 'Zonal_NTC' can only be used together with the PyPSA datasets

    Returns:
        PricingAnalysis object
    """
    price_analysis = solve_scenario(dataset, power_flow_model, pricing_algorithm, redispatch_algorithm)
    is_pypsa_dataset = dataset in [Datasets.PyPSAEurLarge, Datasets.PyPSAEurSmall]
    base_scenario = None
    
    if is_pypsa_dataset:
        isDCOPF = isinstance(power_flow_model, DCOPF)
        scenario_to_analyse = (price_analysis.scenario if isDCOPF 
                               else price_analysis.base_scenario)
        base_scenario = None if isDCOPF else price_analysis.base_scenario
        zonal_config = (power_flow_model.zonal_configuration if 
                        isinstance(power_flow_model, Zonal_NTC) else "")
        
        scenario_to_analyse.analyse_scenario()  # analyse base scenario
        scenario_to_analyse.plot_network(zonal_config)  # plot underlying network
        
    return analyse_results(price_analysis.scenario, price_analysis.allocation, price_analysis.pricing, 
                           price_analysis.configuration, power_flow_model, base_scenario)


def apply_all_algorithms(dataset: Datasets):
    """Computes allocation and pricing and performs several analyses for all valid combinations of power flow 
    models and pricing algorithms for a defined dataset.

    Args:
        dataset (Datasets): dataset for which allocation and pricing are computed
    """
    scenario = _retrieve_data(dataset)
    original_scenario = scenario  # keep original scenario for Zonal_NTC
    configuration = _create_configuration()
    is_pypsa_dataset = dataset in [Datasets.PyPSAEurLarge, Datasets.PyPSAEurSmall]
    
    if is_pypsa_dataset:
        scenario.analyse_scenario()  # analyse base scenario

    for power_flow_model in PowerFlowModels:
        if power_flow_model == PowerFlowModels.DCOPF:
            allocation = _solve_allocation_problem(scenario, power_flow_model, configuration)

        elif power_flow_model == PowerFlowModels.Zonal_NTC and is_pypsa_dataset:
            scenario, allocation = _solve_allocation_problem(scenario, power_flow_model, configuration)

        else:
            continue # skip invalid combinations

        if is_pypsa_dataset:
            zonal_config = power_flow_model.value.zonal_configuration if power_flow_model == PowerFlowModels.Zonal_NTC else ""
            original_scenario.plot_network(zonal_config)  # plot underlying network

        for pricing_alg in PricingAlgorithms:
            pricing = _solve_pricing_problem(scenario, allocation, pricing_alg, power_flow_model, configuration)
            
            base_scenario = None if power_flow_model == PowerFlowModels.DCOPF else original_scenario
            analyse_results(scenario, allocation, pricing, configuration, power_flow_model.value, base_scenario)


def apply_to_all_datasets(power_flow_model: PowerFlowModel, pricing_algorithm: PricingAlgorithms):
    """Computes allocation and pricing and performs several analyses for all valid datasets for a defined 
    combination of power flow model and pricing algorithm.

    Args:
        power_flow_model (PowerFlowModels): power flow model for which allocation and pricing are computed
        pricing_algorithm (PricingAlgorithm): pricing algorithm used for the pricing computations
    """
    datasets = Datasets if isinstance(power_flow_model, DCOPF) else [Datasets.PyPSAEurSmall,
                                                                           Datasets.PyPSAEurLarge]

    for dataset in datasets:
        solve_and_analyse_scenario(dataset, power_flow_model, pricing_algorithm)
