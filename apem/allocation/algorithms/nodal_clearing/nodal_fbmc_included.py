from typing import Optional, Union
import pandas as pd
from gurobipy import GRB

from apem.allocation.allocation import Allocation, SellersAllocation
from apem.allocation.analysis.stats import compute_stats
from apem.allocation.configuration import Configuration
from apem.allocation.error import Error
from apem.allocation.power_flow_model import PowerFlowModel
from apem.data.parsing.scenario import Scenario
from apem.allocation.algorithms.nodal_clearing.nodal_fbmc import NodalDispatchModel
from apem.allocation.algorithms.fbmc_utils import calculate_nodal_ptdf, fix_missing_generator_timeseries, create_pypsa_network_from_scenario, create_allocation_from_nodal_results

C_NSE = 10000  
class NodalFBMC(PowerFlowModel):
    """
    Implementation of the Nodal Flow-Based Market Coupling Model.
    
    This class adapts the NodalDispatchModel to work with the APEM framework,
    taking Scenario objects and returning Allocation objects compatible with
    the existing codebase.
    """

    def solve(self, scenario: Scenario, configuration: Configuration, results_file: Optional[str] = None,
              stats_file: Optional[str] = None, u_fixed: Optional[dict] = None, redispatch: Optional[bool] = False,
              min_cost: Optional[bool] = False, min_vol: Optional[bool] = False,
              zonal_allocation: Optional[SellersAllocation] = None) -> Union[Allocation, Error]:
        """
        Formulate and solve a Nodal FBMC problem using PyPSA and the NodalDispatchModel.

        :param scenario: scenario for which Nodal FBMC is computed
        :param configuration: values of some parameters to be set in the optimizer
        :param results_file: name of the file in which results are written
        :param stats_file: name of the file that contains the statistics
        :param u_fixed: values of the commitment decision variables to be fixed in the problem
        :param redispatch: True if a redispatch solution should be computed
        :param min_cost: True if a minimum-cost redispatch solution should be computed
        :param min_vol: True if a minimum-volume redispatch solution should be computed
        :param zonal_allocation: zonal allocation for which a redispatch solution should be computed
        :return: Allocation object if the problem can be solved optimally or an Error object otherwise
        """
        
        # Convert Scenario to PyPSA Network
        network = create_pypsa_network_from_scenario(scenario)

        # Fix missing generator timeseries if needed
        network = fix_missing_generator_timeseries(network)
        
        # Calculate PTDF matrix
        nodal_ptdf = calculate_nodal_ptdf(network=network)
        
        nodal_model = NodalDispatchModel()
        
        try:
            nodal_results = nodal_model.solve(network, nodal_ptdf, False)
            
            if nodal_results is None or nodal_results.get('model') is None:
                print(f'{self} allocation error: NodalDispatchModel failed to solve or did not return a model.')
                return Error(-1)  # Generic error code for solver failure
            
            if results_file:
                self._save_results_to_file(nodal_results, results_file)
                
            # Convert results to Allocation object
            allocation = create_allocation_from_nodal_results(nodal_results, network, scenario, self)
                
            if stats_file:
                compute_stats(stats_file, scenario, configuration, allocation, nodal_results['model'])
                
            return allocation
            
        except Exception as e:
            print(f'{self} allocation error: {str(e)}')
            return Error(-1)

    def _save_results_to_file(self, nodal_results: dict, results_file: str):
        """
        Save allocation results to a CSV file.

        :param nodal_results: The results dictionary containing model variables and their values.
        :param results_file: Path to the CSV file where results will be saved.
        """
        try:
            model = nodal_results.get('model')
            if model is None:
                print("Could not save results: model object not found in results.")
                return

            status = model.Status
            if status == GRB.OPTIMAL:
                # Use the pre-extracted list of variables
                results_data = nodal_results.get("all_vars")
                if results_data is None:
                    print("Could not save results: 'all_vars' key not found in results dictionary.")
                    return

                df = pd.DataFrame(results_data, columns=["variable", "value"])
                df.to_csv(results_file, index=False)
                print(f"Successfully saved {len(results_data)} variables to {results_file}")

            else:
                # This logic for non-optimal cases remains the same
                status_message = {
                    GRB.INF_OR_UNBD: "Model is infeasible or unbounded",
                    GRB.INFEASIBLE: "Model is infeasible",
                    GRB.UNBOUNDED: "Model is unbounded",
                    GRB.INTERRUPTED: "Optimization was interrupted",
                }.get(status, f"Optimization failed with unknown status code: {status}")

                print(f"Could not save results: {status_message}")
                error_data = [{"status": status, "message": status_message}]
                df = pd.DataFrame(error_data, columns=["status", "message"])
                df.to_csv(results_file, index=False)

        except Exception as e:
            print(f"An unexpected error occurred in _save_results_to_file: {e}")

    def __str__(self):
        return 'NodalFBMC'