import os.path
from enum import Enum
from typing import Optional, Union

from src.allocation.algorithms.nodal_clearing.dcopf import DCOPF
from src.allocation.algorithms.zonal_clearing.zonal_NTC import Zonal_NTC
from src.allocation.allocation import SellersAllocation, Allocation
from src.allocation.configuration import Configuration
from src.allocation.error import Error
from src.data.parsing.parse_arpa import ParseARPA
from src.data.parsing.parse_ieee_rts import ParseIEEERTS
from src.data.parsing.parse_pjm import ParsePJM
from src.data.parsing.parse_pypsa_eur_large import ParsePyPSAEurLarge
from src.data.parsing.parse_pypsa_eur_small import ParsePyPSAEurSmall
from src.data.parsing.scenario import Scenario
from src.pricing.algorithms.elmp import ELMP
from src.pricing.algorithms.ip import IP
from src.pricing.algorithms.join import Join
from src.pricing.algorithms.min_mwp import MinMWP
from src.pricing.analysis.price_analysis import PriceAnalysis
from src.allocation.algorithms.zonal_clearing.redispatch.min_cost import MinCostRD
from src.allocation.algorithms.zonal_clearing.redispatch.min_vol import MinVolRD


class PowerFlowModels(Enum):
    DCOPF = DCOPF()
    Zonal_NTC = Zonal_NTC(zonal_configuration='zonal_DE4-refined',
                          factor=0.8)
    # set zonal_configuration to one of national, zonal_DE2-k, zonal_DE2-s, zonal_DE3, zonal_DE4, zonal_DE4-refined,
    # as described in zonal_configuration.py
    # the factor (between 0 and 1) describes the conservativeness of the NTC model


class PricingAlgorithms(Enum):
    ELMP = ELMP()
    IP = IP()
    MinMWP = MinMWP()
    Join = Join()


class RedispatchAlgorithms(Enum):
    MinCostRD = MinCostRD()
    MinVolRD = MinVolRD()


class Datasets(Enum):
    IEEE_RTS = ParseIEEERTS()
    PJM = ParsePJM()
    PyPSAEurSmall = ParsePyPSAEurSmall()
    PyPSAEurLarge = ParsePyPSAEurLarge()
    ARPA = ParseARPA()


def _retrieve_data(dataset):
    return dataset.value.parse_data()


def _create_configuration(MIP_gap=1e-4, optimality_tol=1e-6, time_limit=60 * 60, work_limit=60 * 60, threads=0,
                          presparsify=-1, strict_supply_demand_eq=True, relaxation=False, output_flag=0):
    return Configuration(MIP_gap, optimality_tol, time_limit, work_limit, threads, presparsify,
                         strict_supply_demand_eq, relaxation, output_flag)


def _solve_allocation_problem(scenario, power_flow_model, configuration, u_fixed=None):
    power_flow_model = power_flow_model.value

    zonal_part = f"{power_flow_model.zonal_configuration}/" if isinstance(power_flow_model, Zonal_NTC) else ""
    base_path = f"results/{scenario}_results/{power_flow_model}"
    path = base_path + "/" + zonal_part + "allocation_results"
    os.makedirs(path, exist_ok=True)

    return power_flow_model.solve(scenario, configuration, results_file=path + f'/{power_flow_model}.csv',
                                  stats_file=path + f'/{power_flow_model}_stats.txt', u_fixed=u_fixed)


def _solve_redispatch_problem(scenario: Scenario, power_flow_model: PowerFlowModels,
                              redispatch_algorithm: RedispatchAlgorithms, zonal_scenario: Scenario,
                              nodal_scenario: Scenario, zonal_allocation: SellersAllocation,
                              configuration: Configuration) -> Union[Allocation, Error]:
    redispatch_algorithm = redispatch_algorithm.value
    power_flow_model = power_flow_model.value

    zonal_part = f"{power_flow_model.zonal_configuration}/" if isinstance(power_flow_model, Zonal_NTC) else ""
    base_path = f"results/{scenario}_results/{power_flow_model}"
    path = base_path + "/" + zonal_part + "allocation_results/redispatch"
    os.makedirs(path, exist_ok=True)

    return redispatch_algorithm.compute_redispatch(zonal_scenario, nodal_scenario, zonal_allocation, configuration,
                                                   path)


def _solve_pricing_problem(scenario, allocation, pricing_algorithm, power_flow_model, prices=None):
    pricing_algorithm = pricing_algorithm.value
    power_flow_model = power_flow_model.value

    zonal_part = f"{power_flow_model.zonal_configuration}/" if isinstance(power_flow_model, Zonal_NTC) else ""
    path = f"results/{scenario}_results/{power_flow_model}/{zonal_part}{pricing_algorithm}_results"
    os.makedirs(path, exist_ok=True)

    pricing = pricing_algorithm.compute_prices(allocation, scenario,
                                               file_prices=path + f"/{pricing_algorithm}_prices.csv",
                                               fixed_prices=prices)
    return pricing


def analyse_results(scenario, allocation, pricing, pf_model_value):
    """Performs several analyses.
    
    Args:
        scenario (Scenario): dataset for which the price analysis is to be performed
        allocation (Allocation): precomputed allocation
        pricing (Pricing): precomputed pricing
        pf_model_value (DCOPF | Zonal_NTC): power flow model information

    Returns:
        PricingAnalysis object
    """
    path = f"results/{scenario}_results"
    os.makedirs(path, exist_ok=True)

    analysis = PriceAnalysis(scenario, allocation, pricing)
    analysis.compute_all_stats_and_plot_data(path, pf_model_value)

    return analysis


def solve_scenario(dataset, power_flow_model, pricing_algorithm,
                   redispatch_algorithm: Optional[RedispatchAlgorithms] = RedispatchAlgorithms.MinCostRD):
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
    if power_flow_model == PowerFlowModels.DCOPF:
        allocation = _solve_allocation_problem(scenario, power_flow_model, configuration)
    else:
        if dataset not in [Datasets.PyPSAEurLarge, Datasets.PyPSAEurSmall]:
            raise ValueError(
                f"The dataset {dataset.name} cannot be used in combination with the power flow model \
                {power_flow_model.value}. Zonal prices can only be computed for the PyPSA datasets."
            )

        zonal_scenario, allocation = _solve_allocation_problem(scenario, power_flow_model, configuration)

        _solve_redispatch_problem(scenario, power_flow_model, redispatch_algorithm=redispatch_algorithm,
                                  zonal_scenario=zonal_scenario, nodal_scenario=scenario, configuration=configuration,
                                  zonal_allocation=allocation.SellersAllocation)

        scenario = zonal_scenario

    pricing = _solve_pricing_problem(scenario, allocation, pricing_algorithm, power_flow_model)
    return PriceAnalysis(scenario, allocation, pricing)


def solve_and_analyse_scenario(dataset, power_flow_model, pricing_algorithm,
                               redispatch_algorithm: Optional[RedispatchAlgorithms] = RedispatchAlgorithms.MinVolRD):
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
    if dataset in [Datasets.PyPSAEurLarge, Datasets.PyPSAEurSmall]:
        price_analysis.scenario.analyse_scenario()  # analyse nodal scenario

        zonal_config = power_flow_model.value.zonal_configuration \
            if power_flow_model == PowerFlowModels.Zonal_NTC else ""
        price_analysis.scenario.plot_network(zonal_config)

    return analyse_results(price_analysis.scenario, price_analysis.allocation, price_analysis.pricing,
                           power_flow_model.value)


def apply_all_algorithms(dataset):
    """Computes allocation and pricing and performs several analyses for all valid combinations of power flow 
    models and pricing algorithms for a defined dataset.

    Args:
        dataset (Datasets): dataset for which allocation and pricing are computed
    """
    scenario = _retrieve_data(dataset)
    if dataset in [Datasets.PyPSAEurLarge, Datasets.PyPSAEurSmall]:
        scenario.analyse_scenario()  # analyse nodal scenario

    configuration = _create_configuration()

    for power_flow_model in PowerFlowModels:
        if power_flow_model == PowerFlowModels.DCOPF:
            allocation = _solve_allocation_problem(scenario, power_flow_model, configuration)

        elif power_flow_model == PowerFlowModels.Zonal_NTC and dataset in [Datasets.PyPSAEurLarge,
                                                                           Datasets.PyPSAEurSmall]:
            scenario, allocation = _solve_allocation_problem(scenario, power_flow_model, configuration)

        else:
            break

        if dataset in [Datasets.PyPSAEurLarge, Datasets.PyPSAEurSmall]:
            zonal_config = power_flow_model.value.zonal_configuration if power_flow_model == PowerFlowModels.Zonal_NTC else ""
            scenario.plot_network(zonal_config)  # plot PyPSA network

        for pricing_alg in PricingAlgorithms:
            pricing = _solve_pricing_problem(scenario, allocation, pricing_alg, power_flow_model)
            analyse_results(scenario, allocation, pricing, power_flow_model.value)


def apply_to_all_datasets(power_flow_model, pricing_algorithm):  # TODO remove
    """Computes allocation and pricing and performs several analyses for all valid datasets for a defined 
    combination of power flow model and pricing algorithm.

    Args:
        power_flow_model (PowerFlowModels): power flow model for which allocation and pricing are computed
        pricing_algorithm (PricingAlgorithm): pricing algorithm used for the pricing computations
    """
    datasets = Datasets if power_flow_model == PowerFlowModels.DCOPF else [Datasets.PyPSAEurSmall,
                                                                           Datasets.PyPSAEurLarge]

    for dataset in datasets:
        solve_and_analyse_scenario(dataset, power_flow_model, pricing_algorithm)
