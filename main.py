from apem.execution_chain import Datasets, PowerFlowModels, PricingAlgorithms, solve_and_analyse_scenario
from euphemia.enums.cut_types import CutType

from euphemia.execution_chain import Datasets as EuphemiaDatasets, run_evaluation
from euphemia.execution_chain import solve_euphemia as solve_euphemia

# Euphemia example
#solve_euphemia(EuphemiaDatasets.OMIE, CutType.PB)
run_evaluation(withIEEE=True)

solve_and_analyse_scenario(Datasets.ARPA, PowerFlowModels.DCOPF, PricingAlgorithms.IP)



