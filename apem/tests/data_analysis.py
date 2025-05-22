import sys
import os

# Füge den übergeordneten Ordner zu sys.path hinzu
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data_saver import save_results
from data_indicators import indicators
from data.analysis.data_plotter import plot_results  # Angepasster Import-Pfad

# Sets the working directory to the parent folder
script_path = os.path.dirname(os.path.abspath(__file__))
parent_path = os.path.dirname(script_path)
parent_path = os.path.dirname(parent_path)
os.chdir(parent_path)

Testing_Data_Set = 'PyPSAEurSmall'  # Choose between IEEE_RTS, PJM, PyPSAEurSmall, PyPSAEurLarge, ARPA
saving = 1  # for 1: All Outputs will be saved at apem/tests/results_data_analysis
show_plots = 1

# Function Calls
all_results = save_results(Testing_Data_Set)
plot_results(all_results, Testing_Data_Set, saving=saving, show_plots=show_plots)
indicators(all_results, Testing_Data_Set)