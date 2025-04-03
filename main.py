from apem.execution_chain import Datasets, PowerFlowModels, PricingAlgorithms, solve_and_analyse_scenario


solve_and_analyse_scenario(Datasets.PyPSAEurLarge, PowerFlowModels.Zonal_NTC, PricingAlgorithms.IP)
