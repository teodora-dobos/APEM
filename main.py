import warnings

from src.execution_chain import Datasets, PowerFlowModels, PricingAlgorithms, solve_and_analyse_scenario

warnings.simplefilter(action='ignore', category=FutureWarning)

solve_and_analyse_scenario(Datasets.PyPSAEurSmall, PowerFlowModels.Zonal_NTC, PricingAlgorithms.ELMP
