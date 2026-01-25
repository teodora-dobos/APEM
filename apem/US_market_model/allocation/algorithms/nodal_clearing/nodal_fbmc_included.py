from typing import Optional, Union
import pandas as pd
from gurobipy import GRB

from apem.US_market_model.allocation.allocation import Allocation, SellersAllocation
from apem.US_market_model.allocation.analysis.stats import compute_stats
from apem.US_market_model.allocation.configuration import Configuration
from apem.US_market_model.allocation.error import Error
from apem.US_market_model.allocation.power_flow_model import PowerFlowModel
from apem.US_market_model.data.parsing.scenario import Scenario
from apem.US_market_model.allocation.algorithms.nodal_clearing.nodal_fbmc import NodalDispatchModel
from apem.US_market_model.allocation.algorithms.fbmc_utils import (
    calculate_nodal_ptdf,
    fix_missing_generator_timeseries,
    create_pypsa_network_from_scenario,
)

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
            nodal_results = nodal_model.solve(network, nodal_ptdf, False, configuration)
            
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
    
def create_allocation_from_nodal_results(nodal_results, network, scenario, power_flow_model):
    """
    Converts results from the NodalDispatchModel into an APEM Allocation object.

    This function is specifically designed to handle a mismatch between integer 'seller'
    IDs in the APEM scenario and string 'generator' names used in the PyPSA model results.
    It creates a mapping to correctly translate between them.

    :param nodal_results: Dictionary from NodalDispatchModel.solve(), containing result 
                            DataFrames and the Gurobi model.
    :param network: The PyPSA network object used for the simulation.
    :param scenario: The input APEM Scenario object.
    :param power_flow_model: The instance of the power flow model (e.g., NodalFBMC) that was run.
    :return: An Allocation object containing the detailed results.
    :raises ValueError: If the model in nodal_results was not solved to optimality.
    """
    model = nodal_results.get('model')
    if model is None or model.Status != GRB.OPTIMAL:
        raise ValueError("Cannot create allocation from a non-optimally solved or missing model.")

    # --- 1. Extract result DataFrames and create identifier mappings ---
    p_gen_df = nodal_results['p_gen']        # Results indexed by string 'generator' name
    u_df = nodal_results['u']                
    startup_df = nodal_results['startup']    
    flow_df = nodal_results['flow']          
    nse_df = nodal_results['nse']            
    duals_df = nodal_results['duals']['nodal_price'] 

    periods = scenario.periods
    snapshot_to_period = {snap: p for p, snap in zip(periods, network.snapshots)}

    # The scenario contains both identifiers. We use it as the bridge.
    mapping_df = scenario.df_sellers[['seller', 'generator']].drop_duplicates()
    gen_name_to_seller_id = pd.Series(mapping_df.seller.values, index=mapping_df.generator).to_dict()

    # --- 2. Convert supply-side results (y_st, u_st, phi_st) using the mapping ---
    y_st, u_st, phi_st = {}, {}, {}

    # Iterate over the results (which use string names) and map them to the integer IDs
    for gen_name in p_gen_df.columns:
        seller_id = gen_name_to_seller_id.get(gen_name)
        if seller_id is None:
            continue # Skip if a generator from model is not in our mapping

        for snapshot in p_gen_df.index:
            period = snapshot_to_period[snapshot]
            y_st[(seller_id, period)] = p_gen_df.loc[snapshot, gen_name]
            u_st[(seller_id, period)] = round(u_df.loc[snapshot, gen_name])
            phi_st[(seller_id, period)] = startup_df.loc[snapshot, gen_name]

    # Reconstruct block-level supply (y_stl) assuming a single block
    y_stl = {
        (s, t, 1): val for (s, t), val in y_st.items()
    }

    # --- 3. Convert network results (f_vwt, alpha_vt) ---
    alpha_vt = {
        (bus, snapshot_to_period[t]): duals_df.loc[t, bus]
        for bus in duals_df.columns for t in duals_df.index
    }

    f_vwt = {}
    for line_name, flows_over_time in flow_df.items():
        line_info = network.lines.loc[line_name]
        v, w = line_info.bus0, line_info.bus1
        for snapshot, flow in flows_over_time.items():
            t = snapshot_to_period[snapshot]
            f_vwt[(v, w, t)] = flow
            f_vwt[(w, v, t)] = -flow

    # --- 4. Reconstruct demand-side results (x_bt, x_btl) ---
    x_bt, x_btl = {}, {}
    bus_demand_df = network.loads_t.p_set.T.groupby(network.loads.bus).sum().T

    for bus_name, nse_at_bus in nse_df.items():
        buyers_at_bus = scenario.nodes_agents.get(bus_name, {}).get('buyers', [])
        if not buyers_at_bus:
            continue
            
        for snapshot, nse_val in nse_at_bus.items():
            t = snapshot_to_period[snapshot]
            total_bus_demand = bus_demand_df.loc[snapshot, bus_name]
            
            if total_bus_demand <= 1e-6:
                for b in buyers_at_bus:
                    x_bt[(b, t)] = 0
                continue
            
            served_ratio = 1.0 - (nse_val / total_bus_demand)
            
            for b in buyers_at_bus:
                buyer_info = scenario.df_buyers[
                    (scenario.df_buyers['buyer'] == b) & (scenario.df_buyers['period'] == t)
                ]
                
                original_demand = buyer_info['inelastic_dem'].sum() + buyer_info[[f'size_{lb}' for lb in scenario.blocks_buyers]].sum().sum()
                
                accepted_demand = original_demand * served_ratio
                x_bt[(b, t)] = accepted_demand
                
                remaining_demand = accepted_demand - buyer_info['inelastic_dem'].iloc[0]
                for lb in scenario.blocks_buyers:
                    block_size = buyer_info[f'size_{lb}'].iloc[0]
                    accepted_block_demand = min(max(0, remaining_demand), block_size)
                    x_btl[(b, t, lb)] = accepted_block_demand
                    remaining_demand -= accepted_block_demand

    # --- 5. Calculate Welfare ---
    total_demand = bus_demand_df.sum().sum()
    total_nse = nse_df.sum().sum()
    value_of_served_energy = C_NSE * (total_demand - total_nse)
    total_production_cost = model.ObjVal - (C_NSE * total_nse)
    welfare = value_of_served_energy - total_production_cost

    # FBMC MILP does not include slack variables; assume zero slack
    slack_vt = {(v, t): 0.0 for v in scenario.network.nodes for t in periods}

    # --- 6. Instantiate and return the Allocation object ---
    allocation = Allocation(
        welfare=welfare,
        x_bt=x_bt,
        y_st=y_st,
        x_btl=x_btl,
        y_stl=y_stl,
        f_vwt=f_vwt,
        alpha_vt=alpha_vt,
        u_st=u_st,
        phi_st=phi_st,
        slack_vt=slack_vt,
        power_flow_model=power_flow_model,
        runtime=model.Runtime,
        num_vars=model.NumVars,
        num_constrs=model.NumConstrs,
        MIP_gap=model.MIPGap if not model.IsMIP == 0 else 0.0,
        num_cont_vars=model.NumVars - model.NumBinVars,
        num_bin_vars=model.NumBinVars,
        dataset=scenario
    )

    return allocation
