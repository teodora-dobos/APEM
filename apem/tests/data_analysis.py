import os
import re
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# Sets the working directory to the parent folder
script_path = os.path.dirname(os.path.abspath(__file__))
parent_path = os.path.dirname(script_path)
parent_path = os.path.dirname(parent_path)
os.chdir(parent_path)

Testing_Data_Set = 'PyPSAEurSmall'  # Choose between IEEE_RTS, PJM, PyPSAEurSmall, PyPSAEurLarge, ARPA
saving = 1  # for 1: All Outputs will be saved at apem/tests/results_data_analysis
show_plots = 1

def save_results(testing_data_set):
    """Saves the results of the algorithms into an Excel file.

    Args:
        testing_data_set (str): The dataset for which results are being saved. IEEE_RTS, PJM, PyPSAEurSmall, PyPSAEurLarge, ARPA

    Returns:
        list: Collected data from the results files.
    """
    output_dir = 'apem/tests/results_data_analysis'
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, f'Summary_{testing_data_set}.xlsx')

    modified_string = re.sub(r'(?<!^)(?=[A-Z][a-z])', '_', testing_data_set)
    base_path = f"results/{modified_string}_results/DCOPF/"

    result_files = {
        'ELMP': 'ELMP_results\\ELMP_stats.txt',
        'IP': 'IP_results\\IP_stats.txt',
        'Join': 'Join_results\\Join_stats.txt'
    }

    data_dict = {}

    for key, rel_path in result_files.items():
        file_path = os.path.join(base_path, rel_path)
        file_path = os.path.normpath(file_path)

        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as file:
                for line in file:
                    if ':' in line:
                        parts = line.split(':', 1)
                        label = parts[0].strip()
                        value = parts[1].strip()

                        try:
                            value = float(value)
                        except ValueError:
                            pass

                        if label in data_dict:
                            data_dict[label].append(value)
                        else:
                            data_dict[label] = [value]
        else:
            print(f'Warning: File {file_path} does not exist and will be skipped.')

    data = [[key] + values for key, values in data_dict.items()]
    headers = ["Label"] + list(result_files.keys())

    df1 = pd.DataFrame(data, columns=headers)
    df1 = df1.applymap(lambda x: str(x).replace('.', ',') if isinstance(x, (float, int)) else x)
    txt_file_path = f"results/{modified_string}_results/DCOPF/allocation_results/DCOPF_stats.txt"

    if os.path.exists(txt_file_path):
        with open(txt_file_path, 'r', encoding='utf-8') as txt_file:
            txt_content = txt_file.readlines()
    else:
        raise FileNotFoundError(
            f"The file '{txt_file_path}' does not exist. "
            f"Please ensure results are generated via analyze_results() before running this step."
        )

    df2 = pd.DataFrame(txt_content, columns=["Allocation Results:"])
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
        df1.to_excel(writer, sheet_name='Pricing Results', index=False)
        df2.to_excel(writer, sheet_name='Allocation Results', index=False)

    print(f'Excel file successfully saved at: {output_file}')

    return data

def plot_results(all_results, testing_data_set):
    """Generates and saves plots based on the results.

    Args:
        all_results (list): The results to plot.
        testing_data_set (str): The dataset for which results are being plotted.
    """
    average_price_keys = [f'Average price in period {x}' for x in list(range(1, 25))]
    
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
    
    # Create plots
    plt.figure()
    plt.plot(elmp, '-o', label='ELMP')
    plt.plot(ip, '-o', label='IP')
    plt.plot(join, '-o', label='Join')
    plt.title(f'Average Costs per Hour; {testing_data_set}')
    plt.xlabel('Hour')
    plt.xticks(ticks=range(24), labels=range(1, 25))
    plt.ylim([0, 100])
    plt.ylabel('Costs €/MWh')
    plt.legend()
    plt.grid(True)
    
    if saving:
        os.makedirs('apem/tests/results_data_analysis', exist_ok=True)
        plt.savefig(f'apem/tests/results_data_analysis/Average_Costs_Hour_{testing_data_set}.png')
    if not show_plots:
        plt.close()
    else:
        plt.show()
    
    # Boxplot creation
    data = [elmp, ip, join]  
    variable_names = ['ELMP', 'IP', 'Join'] 
    
    plt.figure()
    plt.boxplot(data, tick_labels=variable_names, notch=False, patch_artist=True, boxprops=dict(facecolor='lightgray'))
    plt.ylim([0, 100])
    plt.ylabel('Values')
    plt.title(f'Boxplot of average Costs per zone; {testing_data_set}')
    plt.grid(True)
    
    if saving:
        plt.savefig(f'apem/tests/results_data_analysis/Boxplot_Average_Costs_{testing_data_set}.png')
        
    if not show_plots:
        plt.close()
    else:
        plt.show()
    
    num_zones = 0

    if testing_data_set =='PyPSAEurSmall':
        average_price_keys = [f'Average price at node DE0 {x}' for x in list(range(1, 40))]
        num_zones = 40
        
        ELMP, IP, Join = [], [], []
        
        for key in average_price_keys:
            row = next((row for row in all_results if row[0] == key), None)
            if row:
                ELMP.append(float(row[1]))
                IP.append(float(row[2]))
                Join.append(float(row[3]))
            else:
                raise ValueError(f'Row with {key} not found.')
        
    elif testing_data_set =='PyPSAEurLarge':
        average_price_keys = [row[0] for row in all_results if row[0].startswith('Average price at node')]
    
        ELMP, IP, Join = [], [], []
        
        for key in average_price_keys:
            num_zones += 1
            row = next((row for row in all_results if row[0] == key), None)
            if row:
                ELMP.append(float(row[1]))
                IP.append(float(row[2]))
                Join.append(float(row[3]))
            else:
                raise ValueError(f'Row with {key} not found.')
        
    plt.figure()
    plt.plot(ELMP, '-o', label='ELMP')
    plt.plot(IP, '-o', label='IP')
    plt.plot(Join, '-o', label='Join')
    plt.title(f'Average Costs per zone ({num_zones} zones); {testing_data_set}')
    plt.xlabel('Zones')
    if testing_data_set =='PyPSAEurSmall':
        plt.xticks(range(0, num_zones, 2))
        plt.ylim(-25, 275) 
    elif testing_data_set =='PyPSAEurLarge':
        plt.xticks(range(0, num_zones, 20))
    plt.ylabel('Costs')
    plt.legend()
    plt.grid()

    if saving:
        os.makedirs('apem/tests/results_data_analysis', exist_ok=True)
        plt.savefig(f'apem/tests/results_data_analysis/Average_Zone_{testing_data_set}.png')
    
    if not show_plots:
        plt.close()
    else:
        plt.show()
    
    # Create boxplot
    data = [ELMP, IP, Join]
    variable_names = ['ELMP', 'IP', 'Join']
    
    plt.figure()
    plt.boxplot(data, tick_labels=variable_names, patch_artist=True)
    plt.ylabel('Values')
    plt.title(f'Boxplot of average Costs per zone; {testing_data_set}')
    plt.grid()
    if testing_data_set =='PyPSAEurSmall':    
        plt.ylim(-25, 275) 
    
    if saving:
        plt.savefig(f'apem/tests/results_data_analysis/Boxplot_Average_Zone_{testing_data_set}.png')
    if not show_plots:
        plt.close()
    else:
        plt.show()

    # Load the Excel file and read the specific sheet
    with pd.ExcelFile(f"apem/tests/results_data_analysis/Summary_{testing_data_set}.xlsx") as xls:
        allocation_results_df = pd.read_excel(xls, sheet_name='Allocation Results')
    
    # Extract welfare values
    welfare_values = []
    for _, row in allocation_results_df.iterrows():
        line = row[0]  # assuming the first column contains the data
        if isinstance(line, str) and line.startswith("Welfare period"):
            value = line.split(":")[1].strip()
            welfare_values.append(float(value))

    # Check if exactly 24 welfare values are found
    if len(welfare_values) != 24:
        print("Error: Expected 24 welfare period values, found:", len(welfare_values))
        return

    # Plot the welfare values
    plt.figure(figsize=(10, 6))
    plt.plot(range(1, 25), welfare_values, marker='o', linestyle='-')
    plt.title(f'Welfare Over 24 Periods for {testing_data_set}')
    plt.xlabel('Period')
    plt.ylabel('Welfare Value')
    plt.xticks(range(1, 25))
    plt.grid(True)
    plt.tight_layout()
    plt.show()

    if saving:
        plt.savefig(f'apem/tests/results_data_analysis/Wellfare_{testing_data_set}.png')
    if not show_plots:
        plt.close()
    else:
        plt.show()

def indicators(all_results, testing_data_set):
    """Calculates and displays various indicators based on the results.

    Args:
        all_results (list): The results for which indicators are calculated.
        testing_data_set (str): The dataset for which indicators are being calculated.
    """
    average_price_keys = [f'Average price in period {x}' for x in range(1, 25)]
    
    ELMP, IP, Join = [], [], []
    all_results = np.array(all_results) 
    key_indicators = all_results[:16, :]
    print(key_indicators)
    
    for key in average_price_keys:
        rowIndex = np.where(all_results[:, 0] == key)[0]
        if rowIndex.size > 0:
            rowIndex = rowIndex[0]
            ELMP.append(float(all_results[rowIndex, 1]))  # Column 2
            IP.append(float(all_results[rowIndex, 2]))    # Column 3
            Join.append(float(all_results[rowIndex, 3]))  # Column 4
        else:
            raise ValueError(f'Row with {key} not found.')
    
    data = np.array([ELMP, IP, Join])
    average = np.mean(data, axis=1)
    medianValue = np.median(data, axis=1)
    variance = np.var(data, axis=1)
    minimum = np.min(data, axis=1)
    maximum = np.max(data, axis=1)
    
    statisticsMatrix = np.vstack((average, medianValue, variance, minimum, maximum)).T
    
    n = data.shape[0]
    correlationMatrix = np.corrcoef(data)
    distanceMatrix = np.linalg.norm(data[:, np.newaxis] - data, axis=2)
    
    names = ['ELMP', 'IP', 'Join']
    statNames = ['Average', 'Median', 'Variance', 'Min', 'Max']
    Key_ind_names = ['ELMP', 'IP', 'Join']
    
    print('Statistics Matrix:')
    print(pd.DataFrame(statisticsMatrix, index=names, columns=statNames))
    
    print('Correlation Matrix:')
    print(pd.DataFrame(correlationMatrix, index=names, columns=names))
    
    print('Distance Matrix (Euclidean Distance):')
    print(pd.DataFrame(distanceMatrix, index=names, columns=names))
    
    output_folder = 'apem/tests/results_data_analysis'
    os.makedirs(output_folder, exist_ok=True)
    
    excel_filename = os.path.join(output_folder, f'Indicators_{testing_data_set}.xlsx')

    with pd.ExcelWriter(excel_filename, engine='xlsxwriter') as writer:
        headers = key_indicators[:, 0]
        nums = np.array(key_indicators[:, 1:5], dtype=float)
        df_key_indicators = pd.DataFrame(nums, index=headers, columns=Key_ind_names)
        df_key_indicators.to_excel(writer, sheet_name='Key_Indicators')

        df_statistics = pd.DataFrame(statisticsMatrix, index=names, columns=statNames)
        df_statistics.to_excel(writer, sheet_name='Statistics')

        df_correlation = pd.DataFrame(correlationMatrix, index=names, columns=names)
        df_correlation.to_excel(writer, sheet_name='Correlation')

        df_distance = pd.DataFrame(distanceMatrix, index=names, columns=names)
        df_distance.to_excel(writer, sheet_name='Distance')

    print(f'Excel file saved: {excel_filename}')


# Function Calls
all_results = save_results(Testing_Data_Set)
plot_results(all_results, Testing_Data_Set)
indicators(all_results, Testing_Data_Set)






