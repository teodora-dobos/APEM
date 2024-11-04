import os.path
import shutil
from enum import Enum

from implementation.data.parsing.parse_arpa import ParseARPA
from implementation.pricing.analysis.price_analysis import PriceAnalysis
from implementation.pricing.algorithms.elmp import ELMP
from implementation.pricing.algorithms.ip import IP
from implementation.pricing.algorithms.min_mwp import MinMWP
from implementation.pricing.algorithms.join import Join
from implementation.allocation.algorithms.dcopf import DCOPF
from implementation.allocation.algorithms.zonal_NTC import Zonal_NTC
from implementation.allocation.configuration import Configuration
from data.parsing.parse_ieee_rts import ParseIEEERTS
from data.parsing.parse_pjm import ParsePJM
from data.parsing.parse_pypsa_eur_small import ParsePyPSAEurSmall
from data.parsing.parse_pypsa_eur_large import ParsePyPSAEurLarge


class PowerFlowModels(Enum):
    DCOPF = DCOPF()
    Zonal_NTC = Zonal_NTC(zonal_configuration='zonal_DE2-k', factor=0.8)


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


def retrieve_data(dataset, day=None):
    return dataset.value.parse_data(day)


def create_configuration(MIP_gap=1e-4, optimality_tol=1e-6, time_limit=60 * 60, work_limit=60 * 60, threads=0,
                         presparsify=-1, strict_supply_demand_eq=True, relaxation=False, output_flag=0):
    return Configuration(MIP_gap, optimality_tol, time_limit, work_limit, threads, presparsify, strict_supply_demand_eq,
                         relaxation, output_flag)


def solve_allocation_problem(dataset, power_flow_model, configuration, u_fixed=None):
    if isinstance(dataset, Datasets):
        dataset = retrieve_data(dataset)

    power_flow_model = power_flow_model.value

    path = f'results/{dataset}_results/{power_flow_model}/allocation_results'

    if os.path.exists(path):
        shutil.rmtree(path)

    os.makedirs(path, exist_ok=True)

    return power_flow_model.solve(dataset, configuration, output_file=path + f'/{power_flow_model}.txt',
                                  u_fixed=u_fixed)


def solve_pricing_problem(dataset, allocation, pricing_algorithm, power_flow_model, prices=None):
    if isinstance(dataset, Datasets):
        dataset = retrieve_data(dataset)

    pricing_algorithm = pricing_algorithm.value
    power_flow_model = power_flow_model.value

    path = f"results/{dataset}_results/{power_flow_model}/{pricing_algorithm}_results"

    if os.path.exists(path):
        shutil.rmtree(path)

    os.makedirs(path, exist_ok=True)

    pricing = pricing_algorithm.compute_prices(allocation, dataset,
                                               file_prices=path + f"/{pricing_algorithm}_prices.txt",
                                               fixed_prices=prices)

    return pricing


def analyse_results(dataset, allocation, pricing, power_flow_model, file_pypsa_network=""):
    if isinstance(dataset, Datasets):
        dataset = retrieve_data(dataset)

    path = f"results/{dataset}_results/{power_flow_model.value}/{pricing.used_algorithm}_results"

    os.makedirs(path, exist_ok=True)

    analysis = PriceAnalysis(dataset, allocation, pricing)
    analysis.compute_all_statistics(path, file_pypsa_network=file_pypsa_network)

    return analysis


def solve_scenario(dataset, power_flow_model, pricing_algorithm):
    scenario = retrieve_data(dataset)
    configuration = create_configuration()
    allocation = solve_allocation_problem(scenario, power_flow_model, configuration)
    pricing = solve_pricing_problem(scenario, allocation, pricing_algorithm)
    return PriceAnalysis(scenario, allocation, pricing)


def solve_and_analyse_scenario(dataset, power_flow_model, pricing_algorithm, file_pypsa_network=""):
    scenario = retrieve_data(dataset)
    configuration = create_configuration()
    if power_flow_model == PowerFlowModels.DCOPF:
        allocation = solve_allocation_problem(scenario, power_flow_model, configuration)
    else:
        scenario, allocation = solve_allocation_problem(scenario, power_flow_model, configuration)

    pricing = solve_pricing_problem(scenario, allocation, pricing_algorithm, power_flow_model)

    return analyse_results(scenario, allocation, pricing, power_flow_model, file_pypsa_network=file_pypsa_network)


def apply_all_algorithms(dataset, configuration, file_pypsa_network=""):
    scenario = retrieve_data(dataset)
    for power_flow_model in PowerFlowModels:
        allocation = solve_allocation_problem(scenario, power_flow_model, configuration)
        for pricing_alg in PricingAlgorithms:
            pricing = solve_pricing_problem(scenario, allocation, pricing_alg)
            analyse_results(dataset, allocation, pricing, file_pypsa_network=file_pypsa_network)


def apply_to_all_datasets(power_flow_model, pricing_algorithm):
    for dataset in Datasets:
        solve_and_analyse_scenario(dataset, power_flow_model, pricing_algorithm)
