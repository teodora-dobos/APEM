import os.path
import shutil
from enum import Enum

from implementation.data.parsing.parse_arpa import ParseARPA
from implementation.allocation.algorithms.dcopf import DCOPF
from implementation.allocation.configuration import Configuration
from data.parsing.parse_ieee_rts import ParseIEEERTS
from data.parsing.parse_pjm import ParsePJM
from data.parsing.parse_pypsa_eur_small import ParsePyPSAEurSmall
from data.parsing.parse_pypsa_eur_large import ParsePyPSAEurLarge


class PowerFlowModels(Enum):
    DCOPF = DCOPF()


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

    path = f'results/{dataset}_results/allocation_results'

    if os.path.exists(path):
        shutil.rmtree(path)

    os.makedirs(path, exist_ok=True)

    return power_flow_model.solve(dataset, configuration, output_file=path + f'/{power_flow_model}.txt',
                                  u_fixed=u_fixed)


def solve_pricing_problem(dataset, allocation, pricing_algorithm, prices=None):
    if isinstance(dataset, Datasets):
        dataset = retrieve_data(dataset)

    pricing_algorithm = pricing_algorithm.value

    path = f"results/{dataset}_results/{pricing_algorithm}_results"

    if os.path.exists(path):
        shutil.rmtree(path)

    os.makedirs(path, exist_ok=True)

    pricing = pricing_algorithm.compute_prices(allocation, dataset,
                                               file_prices=path + f"/{pricing_algorithm}_prices.txt",
                                               fixed_prices=prices)

    return pricing


def solve_and_analyse_scenario(dataset, power_flow_model, pricing_algorithm=None, file_pypsa_network=""):
    scenario = retrieve_data(dataset)
    configuration = create_configuration()
    allocation = solve_allocation_problem(scenario, power_flow_model, configuration)
    return allocation



def apply_to_all_datasets(power_flow_model, pricing_algorithm):
    for dataset in Datasets:
        solve_and_analyse_scenario(dataset, power_flow_model, pricing_algorithm)
