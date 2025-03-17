from src.execution_chain import Datasets, PowerFlowModels, PricingAlgorithms, solve_and_analyse_scenario
import os
#os.chdir(r"C:\Users\SimonKreiml\OneDrive - FIM Forschungsinstitut\Desktop\APEM\GitHUB\Git Clone\APEM") 
solve_and_analyse_scenario(Datasets.PyPSAEurSmall, PowerFlowModels.Zonal_NTC, PricingAlgorithms.IP)
