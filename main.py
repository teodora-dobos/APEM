from src.execution_chain import Datasets, PowerFlowModels, PricingAlgorithms, solve_and_analyse_scenario


solve_and_analyse_scenario(Datasets.PyPSAEurSmall, PowerFlowModels.Zonal_NTC, PricingAlgorithms.IP)
