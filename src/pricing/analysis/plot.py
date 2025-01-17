import matplotlib as mpl
import pypsa
from matplotlib import pyplot as plt


def plot_avg_prices(avg_prices, scenario, file_plot="") -> None:
    avg_prices.plot(xlim=(min(scenario.periods), max(scenario.periods)),
                    xlabel='period', ylabel='€/MWh')
    plt.savefig(file_plot, dpi=300)


def pypsa_heatmap(self, file_pypsa_network, file_heatmap, avg_prices=None) -> None:
    if avg_prices is None:
        avg_prices = self.avg_node_prices()

    n = pypsa.Network(file_pypsa_network)
    n.buses = n.buses[n.buses.index.isin(avg_prices.keys())]
    n.lines = n.lines[n.lines["s_nom"] > 0]

    norm = mpl.colors.Normalize(vmin=0, vmax=100)
    cmap = mpl.colormaps["jet"]
    plt.clf()
    n.plot(boundaries=[6, 15, 47, 55], bus_colors=avg_prices, bus_cmap=cmap, bus_norm=norm, color_geomap=True)

    fig = plt.gcf()
    ax = plt.gca()
    axpos = ax.get_position()
    pos_x = axpos.x0 + axpos.width + 0.01
    pos_y = axpos.y0
    cax_width = 0.04
    cax_height = axpos.height
    pos_cax = fig.add_axes((pos_x, pos_y, cax_width, cax_height))

    cbar = plt.colorbar(mappable=mpl.cm.ScalarMappable(norm=norm, cmap=cmap), cax=pos_cax,
                        ticks=[0, 20, 40, 60, 80, 100], label="€/MWh")
    cbar.set_ticklabels(['≤0', '20', '40', '60', '80', '≥100'])

    plt.savefig(file_heatmap, bbox_inches='tight', dpi=300)