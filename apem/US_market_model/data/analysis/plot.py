from matplotlib import pyplot as plt
from apem.US_market_model.data.parsing.scenario import Scenario


def plot_supply_demand(dir_plots: str, scenario: Scenario) -> None:
    """
    Plots the supply and demand curves.
    """
    demand = scenario.df_buyers[['period', 'inelastic_dem']]
    demand = demand.groupby(['period']).sum()
    demand = demand.rename(columns={'inelastic_dem': 'Total demand'})

    supply = scenario.df_sellers[['period', 'max_prod']]
    supply = supply.groupby(['period']).sum()
    supply = supply.rename(columns={'max_prod': 'Total supply'})

    plt.clf()
    demand.plot(xlim=(min(scenario.periods), max(scenario.periods)), xlabel='period', ylabel='MWh')
    plt.savefig(f"{dir_plots}/{scenario.__str__()}_demand.png", dpi=300)
    plt.close()
    
    plt.clf()
    supply.plot(xlim=(min(scenario.periods), max(scenario.periods)), xlabel='period', ylabel='MWh',
                color='orange')
    plt.savefig(f"{dir_plots}/{scenario.__str__()}_supply.png", dpi=300)
    plt.close()
