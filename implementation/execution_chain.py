from enum import Enum

from implementation.euphemia import Euphemia
from implementation.data.parsing.parse_eu import ParseEU


class Datasets(Enum):
    EU = ParseEU()


def retrieve_data(dataset, day=None):
    return dataset.value.parse_data(day)


#def create_configuration(MIP_gap=1e-4, optimality_tol=1e-6, time_limit=60 * 60, work_limit=60 * 60, threads=0,
#                         presparsify=-1, strict_supply_demand_eq=True, relaxation=False, output_flag=0):
#    return Configuration(MIP_gap, optimality_tol, time_limit, work_limit, threads, presparsify, strict_supply_demand_eq,
#                         relaxation, output_flag)


def solve_and_analyse_scenario(dataset):
    scenario = retrieve_data(dataset)

    file = open("euphemia_results/scenario", 'w+')
    file.write(scenario.overview())
    file.close()

    if dataset == Datasets.EU:
        euphemia = Euphemia(scenario)
        euphemia.solve()
