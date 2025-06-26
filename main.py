from apem.execution_chain import Datasets, PowerFlowModels, PricingAlgorithms, solve_and_analyse_scenario

from euphemia.execution_chain import Datasets as Euphemia_datasets
from euphemia.execution_chain import solve_and_analyse_scenario as solve_euphemia


solve_euphemia(Euphemia_datasets.OMIE)

#solve_and_analyse_scenario(Datasets.IEEE_RTS, PowerFlowModels.DCOPF, PricingAlgorithms.IP)



