import os.path
import shutil
from enum import Enum

from src.allocation.algorithms.dcopf import DCOPF
from src.allocation.algorithms.zonal_NTC import Zonal_NTC
from src.allocation.configuration import Configuration
from src.data.parsing.parse_arpa import ParseARPA
from src.data.parsing.parse_ieee_rts import ParseIEEERTS
from src.data.parsing.parse_pjm import ParsePJM
from src.data.parsing.parse_pypsa_eur_large import ParsePyPSAEurLarge
from src.data.parsing.parse_pypsa_eur_small import ParsePyPSAEurSmall
from src.pricing.algorithms.elmp import ELMP
from src.pricing.algorithms.ip import IP
from src.pricing.algorithms.join import Join
from src.pricing.algorithms.min_mwp import MinMWP
from src.pricing.analysis.price_analysis import PriceAnalysis


class PowerFlowModels(Enum):
    DCOPF = DCOPF()
    Zonal_NTC = Zonal_NTC(zonal_configuration='zonal_DE2-k', factor=0.8) # the factor (between 0 and 1) describes the conservativeness of the NTC model


class PricingAlgorithms(Enum):
    ELMP = ELMP()
    IP = IP()
    MinMWP = MinMWP()
    Join = Join()


class Datasets(Enum):
    IEEE_RTS = ParseIEEERTS()
    PJM = ParsePJM()
    PyPSAEurSmall = ParsePyPSAEurSmall()
    PyPSAEurLarge = ParsePyPSAEurLarge()
    ARPA = ParseARPA()


def retrieve_data(dataset):
    return dataset.value.parse_data()


def create_configuration(MIP_gap=1e-4, optimality_tol=1e-6, time_limit=60 * 60, work_limit=60 * 60, threads=0,
                         presparsify=-1, strict_supply_demand_eq=True, relaxation=False, output_flag=0):
    return Configuration(MIP_gap, optimality_tol, time_limit, work_limit, threads, presparsify, strict_supply_demand_eq,
                         relaxation, output_flag)


def solve_allocation_problem(dataset, power_flow_model, configuration, u_fixed=None):
    if isinstance(dataset, Datasets):
        dataset = retrieve_data(dataset)
        
    power_flow_model = power_flow_model.value

    zonal_part = f"{power_flow_model.zonal_configuration}/" if isinstance(power_flow_model, Zonal_NTC) else ""
    base_path = f"results/{dataset}_results/{power_flow_model}"   
    path = base_path + "/" + zonal_part + "allocation_results"
    os.makedirs(base_path, exist_ok=True)
    os.makedirs(path, exist_ok=True)

    return power_flow_model.solve(dataset, configuration, results_file=path + f'/{power_flow_model}.csv',
                                  stats_file=path + f'/{power_flow_model}_stats.txt', u_fixed=u_fixed)


def solve_pricing_problem(dataset, allocation, pricing_algorithm, power_flow_model, prices=None):
    if isinstance(dataset, Datasets):
        dataset = retrieve_data(dataset)

    pricing_algorithm = pricing_algorithm.value
    power_flow_model = power_flow_model.value

    zonal_part = f"{power_flow_model.zonal_configuration}/" if isinstance(power_flow_model, Zonal_NTC) else ""
    path = f"results/{dataset}_results/{power_flow_model}/{zonal_part}{pricing_algorithm}_results"

    if os.path.exists(path):
        shutil.rmtree(path)

    os.makedirs(path, exist_ok=True)

    pricing = pricing_algorithm.compute_prices(allocation, dataset,
                                               file_prices=path + f"/{pricing_algorithm}_prices.csv",
                                               fixed_prices=prices)
    return pricing


def analyse_results(dataset, allocation, pricing, power_flow_model):
    if isinstance(dataset, Datasets):
        dataset = retrieve_data(dataset)

    path = f"results/{dataset}_results"
    os.makedirs(path, exist_ok=True)

    analysis = PriceAnalysis(dataset, allocation, pricing)
    analysis.compute_all_stats_and_plot_data(path, power_flow_model)

    return analysis


def solve_scenario(dataset, power_flow_model, pricing_algorithm):
    scenario = retrieve_data(dataset)
    configuration = create_configuration()
    if power_flow_model == PowerFlowModels.DCOPF:
        allocation = solve_allocation_problem(scenario, power_flow_model, configuration)
    else:
        if dataset not in [Datasets.PyPSAEurLarge, Datasets.PyPSAEurSmall]:
            raise ValueError(f"The dataset {dataset.name} cannot be used in combination with the power flow model {power_flow_model.value}. Zonal prices can only be computed for the PyPSA datasets.")
        scenario, allocation = solve_allocation_problem(scenario, power_flow_model, configuration)
    pricing = solve_pricing_problem(scenario, allocation, pricing_algorithm, power_flow_model)
    return PriceAnalysis(scenario, allocation, pricing)


def solve_and_analyse_scenario(dataset, power_flow_model, pricing_algorithm):
    scenario = retrieve_data(dataset)
    if dataset in [Datasets.PyPSAEurLarge, Datasets.PyPSAEurSmall]:
        scenario.analyse_scenario() # analyse nodal scenario

    configuration = create_configuration()
    if power_flow_model == PowerFlowModels.DCOPF:
        allocation = solve_allocation_problem(scenario, power_flow_model, configuration)
    else:
        if dataset not in [Datasets.PyPSAEurLarge, Datasets.PyPSAEurSmall]:
            raise ValueError(f"The dataset {dataset.name} cannot be used in combination with the power flow model {power_flow_model.value}. Zonal prices can only be computed for the PyPSA datasets.")

        scenario, allocation = solve_allocation_problem(scenario, power_flow_model, configuration)

    if dataset in [Datasets.PyPSAEurLarge, Datasets.PyPSAEurSmall]:
        zonal_config = power_flow_model.value.zonal_configuration if power_flow_model == PowerFlowModels.Zonal_NTC else ""
        scenario.plot_network(zonal_config) # plot PyPSA network
        
    pricing = solve_pricing_problem(scenario, allocation, pricing_algorithm, power_flow_model)

    return analyse_results(scenario, allocation, pricing, power_flow_model)


def apply_all_algorithms(dataset, configuration):
    scenario = retrieve_data(dataset)
    for power_flow_model in PowerFlowModels:
        allocation = solve_allocation_problem(scenario, power_flow_model, configuration)
        for pricing_alg in PricingAlgorithms:
            pricing = solve_pricing_problem(scenario, allocation, pricing_alg)
            analyse_results(dataset, allocation, pricing)


def apply_to_all_datasets(power_flow_model, pricing_algorithm):
    for dataset in Datasets:
        solve_and_analyse_scenario(dataset, power_flow_model, pricing_algorithm)