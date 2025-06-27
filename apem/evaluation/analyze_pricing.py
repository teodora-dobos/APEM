import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data_saver import save_results
from data_indicators import indicators
from data_plotter import plot_results

if __name__ == "__main__":
    script_path = os.path.dirname(os.path.abspath(__file__))
    parent_path = os.path.dirname(script_path)
    project_root = os.path.dirname(parent_path)
    os.chdir(project_root)

    print("Working directory set to:", os.getcwd())

    Testing_Data_Set = 'PyPSAEurSmall'  # Choose between IEEE_RTS, PJM, PyPSAEurSmall, PyPSAEurLarge, ARPA
    saving = True  # If True: All Outputs will be saved at results_data_analysis
    show_plots = False

    all_results = save_results(Testing_Data_Set)
    if Testing_Data_Set != 'ARPA':  # These methods work only for data sets with 24 periods
        plot_results(all_results, Testing_Data_Set, saving=saving, show_plots=show_plots)
        indicators(all_results, Testing_Data_Set)
