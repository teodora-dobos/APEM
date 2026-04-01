import os
import re
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


def plot_results(all_results, testing_data_set, saving=1, show_plots=1):
    """Generates and saves plots based on the results.

    Args:
        all_results (list): The results to plot.
        testing_data_set (str): The dataset for which results are being plotted.
        saving (int): Flag to save the plots.
        show_plots (int): Flag to show the plots.
    """
    average_price_rows = [
        item for item in all_results
        if isinstance(item[0], str) and item[0].startswith('Average price in period ')
    ]
    average_price_rows.sort(
        key=lambda item: int(re.search(r'(\d+)$', item[0]).group(1))
    )
    average_price_keys = [item[0] for item in average_price_rows]
    period_labels = [
        int(re.search(r'(\d+)$', key).group(1))
        for key in average_price_keys
    ]

    if not average_price_keys:
        raise ValueError('No average price per period rows found.')

    # Prepare plot data
    elmp, ip, join = [], [], []

    for key in average_price_keys:
        row = next((item for item in all_results if item[0] == key), None)
        if row is not None:
            elmp.append(float(row[1]))
            ip.append(float(row[2]))
            join.append(float(row[3]))
        else:
            raise ValueError(f'Row with {key} not found.')

    # Create plots for average costs per hour
    plt.figure()
    plt.plot(elmp, '-o', label='ELMP')
    plt.plot(ip, '-o', label='IP')
    plt.plot(join, '-o', label='Join')
    plt.title(f'Average Costs per Hour; {testing_data_set}')
    plt.xlabel('Hour')
    plt.xticks(ticks=range(len(period_labels)), labels=period_labels)
    plt.ylim([0, 100])
    plt.ylabel('Costs €/MWh')
    plt.legend()
    plt.grid(True)

    if saving:
        os.makedirs('apem/evaluation/results_data_analysis', exist_ok=True)
        plt.savefig(f'apem/evaluation/results_data_analysis/Average_Costs_Hour_{testing_data_set}.png')
    if not show_plots:
        plt.close()
    else:
        plt.show()

    # Boxplot creation for average costs per hour
    data = [elmp, ip, join]
    variable_names = ['ELMP', 'IP', 'Join']

    plt.figure()
    plt.boxplot(data, tick_labels=variable_names, notch=False, patch_artist=True, boxprops=dict(facecolor='lightgray'))
    plt.ylim([0, 100])
    plt.ylabel('Values')
    plt.title(f'Boxplot of Average Costs per Hour; {testing_data_set}')
    plt.grid(True)

    if saving:
        plt.savefig(f'apem/evaluation/results_data_analysis/Boxplot_Average_Costs_{testing_data_set}.png')

    if not show_plots:
        plt.close()
    else:
        plt.show()

    # Prepare plot data for average costs per zone
    num_zones = 0
    ELMP, IP, Join = [], [], []

    if testing_data_set == 'PyPSAEurSmall':
        average_price_keys = [f'Average price at node DE0 {x}' for x in list(range(1, 40))]
        num_zones = 40

        for key in average_price_keys:
            row = next((row for row in all_results if row[0] == key), None)
            if row:
                ELMP.append(float(row[1]))
                IP.append(float(row[2]))
                Join.append(float(row[3]))
            else:
                raise ValueError(f'Row with {key} not found.')

    elif testing_data_set == 'PyPSAEurLarge':
        average_price_keys = [row[0] for row in all_results if row[0].startswith('Average price at node')]

        for key in average_price_keys:
            num_zones += 1
            row = next((row for row in all_results if row[0] == key), None)
            if row:
                ELMP.append(float(row[1]))
                IP.append(float(row[2]))
                Join.append(float(row[3]))
            else:
                raise ValueError(f'Row with {key} not found.')

    # Create line plot for average costs per zone
    plt.figure()
    plt.plot(ELMP, '-o', label='ELMP')
    plt.plot(IP, '-o', label='IP')
    plt.plot(Join, '-o', label='Join')
    plt.title(f'Average Costs per Zone ({num_zones} zones); {testing_data_set}')
    plt.xlabel('Zones')
    if testing_data_set == 'PyPSAEurSmall':
        plt.xticks(range(0, num_zones, 2))
        plt.ylim(-25, 275)
    elif testing_data_set == 'PyPSAEurLarge':
        plt.xticks(range(0, num_zones, 20))
    plt.ylabel('Costs')
    plt.legend()
    plt.grid()

    if saving:
        os.makedirs('apem/evaluation/results_data_analysis', exist_ok=True)
        plt.savefig(f'apem/evaluation/results_data_analysis/Average_Zone_{testing_data_set}.png')

    if not show_plots:
        plt.close()
    else:
        plt.show()

    # Create boxplot for average costs per zone
    data = [ELMP, IP, Join]
    variable_names = ['ELMP', 'IP', 'Join']

    plt.figure()
    plt.boxplot(data, tick_labels=variable_names, patch_artist=True)
    plt.ylabel('Values')
    plt.title(f'Boxplot of Average Costs per Zone; {testing_data_set}')
    plt.grid()
    if testing_data_set == 'PyPSAEurSmall':
        plt.ylim(-25, 275)

    if saving:
        plt.savefig(f'apem/evaluation/results_data_analysis/Boxplot_Average_Zone_{testing_data_set}.png')
    if not show_plots:
        plt.close()
    else:
        plt.show()

    # Load the Excel file and read the specific sheet
    with pd.ExcelFile(f"apem/evaluation/results_data_analysis/Summary_{testing_data_set}.xlsx") as xls:
        allocation_results_df = pd.read_excel(xls, sheet_name='Allocation Results')

    # Extract welfare values
    welfare_pairs = []
    for _, row in allocation_results_df.iterrows():
        line = row[0]  # assuming the first column contains the data
        if isinstance(line, str) and line.startswith("Welfare period"):
            period_match = re.search(r'Welfare period\s+(\d+)', line)
            if period_match is None:
                continue
            period = int(period_match.group(1))
            value = line.split(":", 1)[1].strip()
            welfare_pairs.append((period, float(value)))

    if not welfare_pairs:
        print("Error: No welfare period values found.")
        return

    welfare_pairs.sort(key=lambda item: item[0])
    welfare_periods = [period for period, _ in welfare_pairs]
    welfare_values = [value for _, value in welfare_pairs]

    # Plot the welfare values
    plt.figure(figsize=(10, 6))
    plt.plot(welfare_periods, welfare_values, marker='o', linestyle='-')
    plt.title(f'Welfare Over {len(welfare_periods)} Periods for {testing_data_set}')
    plt.xlabel('Period')
    plt.ylabel('Welfare Value')
    plt.xticks(welfare_periods)
    plt.grid(True)
    plt.tight_layout()
    plt.show()

    if saving:
        plt.savefig(f'apem/evaluation/results_data_analysis/Wellfare_{testing_data_set}.png')
    if not show_plots:
        plt.close()
    else:
        plt.show()
