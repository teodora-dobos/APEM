## run_all
# Executes the function solve_and_analyse_scenario for all possible scenarios within a fixed input dataset "Testing_Data_Set".
# The results are stored in the "Results" folder for further analysis.
# Currently, this is only implemented for DCOPF and should be extended after implementation of Euphemia.


import sys
import os

# Ermittelt den Pfad der aktuellen .py Datei
script_path = os.path.dirname(os.path.abspath(__file__))

# Geht eine Ebene nach oben
parent_path = os.path.dirname(script_path)

# Setzt das Arbeitsverzeichnis auf den übergeordneten Ordner
os.chdir(parent_path)

# Fügt den übergeordneten Ordner zum Python-Pfad hinzu, damit Imports weiterhin funktionieren
sys.path.append(parent_path)

from src.execution_chain import * 
import time

# Define the dataset to be used. Options: IEEE_RTS, PJM, PyPSAEurSmall, PyPSAEurLarge, ARPA
Testing_Data_Set = 'PyPSAEurLarge'


def run_all_models(Testing_Data_Set):
    
    if not Testing_Data_Set:
        return
    
    # Retrieve the dataset object based on the specified dataset name
    dataset = getattr(Datasets, Testing_Data_Set)

    # Define the scenarios to be tested for the selected dataset
    scenarios = [
        (PowerFlowModels.DCOPF, PricingAlgorithms.ELMP),
        (PowerFlowModels.DCOPF, PricingAlgorithms.IP),
        (PowerFlowModels.DCOPF, PricingAlgorithms.MinMWP),
        (PowerFlowModels.DCOPF, PricingAlgorithms.Join),
        #(PowerFlowModels.DCOPF, PricingAlgorithms.ELMP),
        #(PowerFlowModels.DCOPF, PricingAlgorithms.IP),
        #(PowerFlowModels.DCOPF, PricingAlgorithms.MinMWP),
        #(PowerFlowModels.DCOPF, PricingAlgorithms.Join),
    ]
    
    total_time = 0  # Initialize total execution time

    # Extract the dataset name, handling cases where it might not have a '__name__' attribute
    dataset_name = dataset.__name__ if hasattr(dataset, '__name__') else str(dataset).split('.')[-1]   

    # Iterate through each scenario
    for model, algorithm in scenarios:
        # Extract model and algorithm names for logging purposes
        model_name = model.__name__ if hasattr(model, '__name__') else str(model).split('.')[-1]
        algorithm_name = algorithm.__name__ if hasattr(algorithm, '__name__') else str(algorithm).split('.')[-1]

        print(f"Running Model with DataSet {dataset_name}, PowerFlowModel {model_name}, and PricingAlgorithm {algorithm_name}...")
        start_time = time.time()  # Record start time
        
        # Print das aktuelle Arbeitsverzeichnis zur Kontrolle
        #print("Aktuelles Arbeitsverzeichnis:", os.getcwd())

        # Execute the scenario with the given dataset, model, and algorithm
        solve_and_analyse_scenario(dataset, model, algorithm) 
        
        end_time = time.time()  # Record end time
        elapsed_time = end_time - start_time  # Calculate execution time
        total_time += elapsed_time  # Accumulate total execution time

        print(f"Completed in {elapsed_time:.2f} seconds.\n")

    # Convert total execution time into minutes and seconds
    minutes, seconds = divmod(int(total_time), 60)
    print(f"Total completed with DataSet {dataset_name} in {minutes:.2f} min {seconds:.2f} sec.\n")


# Execute the function with the specified dataset
run_all_models(Testing_Data_Set)








