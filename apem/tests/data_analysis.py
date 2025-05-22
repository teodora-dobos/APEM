## Data Analysis
# Makes the results of the algorithms comparable via Visualizations and Indicators. Results are saved in data_analysis/results_data_analysis
# Currently only for DCOPF. Should be extended after implementation of Euphemia..
# Comparison with Real Day Ahead Prices only possible on local computers for data protection reasons


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


#PowerFlowModels: DCOPF, Zonal_NTC
#Pricing Algorithms: ELMP, IP, Join

Testing_Data_Set = 'PyPSAEurLarge'  #Choose between IEEE_RTS, PJM, PyPSAEurSmall, PyPSAEurLarge, ARPA
saving = 1 #for 1: All Outputs will be saved at apem/tests/results_data_analysis
show_plots = 1




def save_results(Testing_Data_Set):
    # Get the directory of the script and move one level up
    #script_dir = os.path.dirname(os.path.abspath(__file__))
    #parent_dir = os.path.dirname(script_dir)  # Move one level up

    # Create Excel output directory
    output_dir = 'apem/tests/results_data_analysis'
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, f'Summary_{Testing_Data_Set}.xlsx')

    # Set the working directory to the parent directory
    #os.chdir(script_dir)
    
    # Define the base path for result files
    modified_string = re.sub(r'(?<!^)(?=[A-Z][a-z])', '_', Testing_Data_Set)  # Convert variable name to corresponding folder name
    base_path = f"results/{modified_string}_results/DCOPF/"

    # Define result files with corresponding paths
    result_files = {
        'ELMP': 'ELMP_results\\ELMP_stats.txt',
        'IP': 'IP_results\\IP_stats.txt',
        'Join': 'Join_results\\Join_stats.txt'
    }

    # Collect results
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
    # **Read the .txt file for the second sheet**
    

    if os.path.exists(txt_file_path):
        # **Read the .txt file for the second sheet**
        with open(txt_file_path, 'r', encoding='utf-8') as txt_file:
            txt_content = txt_file.readlines()
    else:
        raise FileNotFoundError(
            f"The file '{txt_file_path}' does not exist. "
            f"Please ensure results are generated via analyze_results() before running this step."
        )




    # with open(txt_file_path, 'r', encoding='utf-8') as txt_file:
    #     txt_content = txt_file.readlines()

    df2 = pd.DataFrame(txt_content, columns=["Allocation Results:"])
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
        df1.to_excel(writer, sheet_name='Pricing Results', index=False)
        df2.to_excel(writer, sheet_name='Allocation Results', index=False)

    print(f'Excel file successfully saved at: {output_file}')

    return data




def plot_results(all_results, testing_data_set):

    # List of column names
    # Creating the column names
    average_price_keys = [f'Average price in period {x}' for x in list(range(1, 25))]# + list(range(8, 25))]
    #output_folder = 'results_data_analysis'
    
   
    
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
    
    
    # Save the plot as PNG
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
    
    # Initialize plot
    plt.figure()
    plt.boxplot(data, tick_labels=variable_names, notch=False, patch_artist=True, boxprops=dict(facecolor='lightgray'))
    plt.ylim([0, 100])
    plt.ylabel('Values')
    plt.title(f'Boxplot of average Costs per zone; {testing_data_set}')
    plt.grid(True)
   
    
    # Save the boxplot as PNG
    if saving:
        os.makedirs('apem/tests/results_data_analysis', exist_ok=True)
        plt.savefig(f'apem/tests/results_data_analysis/Boxplot_Average_Costs_{testing_data_set}.png')
        
    if not show_plots:
        plt.close()
    else:
        plt.show()
    
    num_zones = 0

    if testing_data_set =='PyPSAEurSmall':
        # Create column names
        average_price_keys = [f'Average price at node DE0 {x}' for x in list(range(1, 40))]# + list(range(8, 40)),]
        num_zones = 40
        
        # Prepare plot data
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
    
        # Prepare plot data
        ELMP, IP, Join = [], [], []
        
        for key in average_price_keys:
            num_zones = num_zones + 1
            row = next((row for row in all_results if row[0] == key), None)
            if row:
                ELMP.append(float(row[1]))
                IP.append(float(row[2]))
                Join.append(float(row[3]))
            else:
                raise ValueError(f'Row with {key} not found.')
       
        
    # Create plots
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
            # Extract the numeric value after the colon and convert it to float
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
    plt.tight_layout()  # Adjust the layout
    plt.show()

    if saving:
        plt.savefig(f'apem/tests/results_data_analysis/Wellfare_{testing_data_set}.png')
    if not show_plots:
        plt.close()
    else:
        plt.show()




    

def indicators(All_Results, Testing_Data_Set):
    
    # Create column names
    average_price_keys = [f'Average price in period {x}' for x in range(1, 25)]
    
    # Prepare plot data
    ELMP, IP, Join = [], [], []
    All_Results = np.array(All_Results) 
    key_indicators = All_Results[:16, :]
    print(key_indicators)
    
    for key in average_price_keys:
        rowIndex = np.where(All_Results[:, 0] == key)[0]
        if rowIndex.size > 0:
            rowIndex = rowIndex[0]
            ELMP.append(float(All_Results[rowIndex, 1]))  # Column 2
            IP.append(float(All_Results[rowIndex, 2]))    # Column 3
            Join.append(float(All_Results[rowIndex, 3]))  # Column 4
        else:
            raise ValueError(f'Row with {key} not found.')
    
    
    
    data = np.array([ELMP, IP, Join])
    # Compute the statistics matrix
    average = np.mean(data, axis=1)
    medianValue = np.median(data, axis=1)
    variance = np.var(data, axis=1)
    minimum = np.min(data, axis=1)
    maximum = np.max(data, axis=1)
    
    statisticsMatrix = np.vstack((average, medianValue, variance, minimum, maximum)).T
    
    # Initialize correlation and distance matrix
    n = data.shape[0]
    correlationMatrix = np.corrcoef(data)
    distanceMatrix = np.linalg.norm(data[:, np.newaxis] - data, axis=2)
    
    # Names of time series
    
    names = ['ELMP', 'IP', 'Join']#, 'Real Day-Ahead price']
    statNames = ['Average', 'Median', 'Variance', 'Min', 'Max']
    Key_ind_names = ['ELMP', 'IP', 'Join']
    
    # Display statistics matrix
    print('Statistics Matrix:')
    print(pd.DataFrame(statisticsMatrix, index=names, columns=statNames))
    
    # Display correlation matrix
    print('Correlation Matrix:')
    print(pd.DataFrame(correlationMatrix, index=names, columns=names))
    
    # Display distance matrix
    print('Distance Matrix (Euclidean Distance):')
    print(pd.DataFrame(distanceMatrix, index=names, columns=names))
    
    # Ensure output folder exists
    output_folder = 'apem/tests/results_data_analysis'
    os.makedirs(output_folder, exist_ok=True)
    
    # Excel file name
    excel_filename = os.path.join(output_folder, f'Indicators_{Testing_Data_Set}.xlsx')

    # Use ExcelWriter to store multiple sheets in one file
    with pd.ExcelWriter(excel_filename, engine='xlsxwriter') as writer:
        # Process key_indicators
        headers = key_indicators[:, 0]
        nums = np.array(key_indicators[:, 1:5], dtype=float)
        df_key_indicators = pd.DataFrame(nums, index=headers, columns=Key_ind_names)
        df_key_indicators.to_excel(writer, sheet_name='Key_Indicators')

        # Save statistics matrix
        df_statistics = pd.DataFrame(statisticsMatrix, index=names, columns=statNames)
        df_statistics.to_excel(writer, sheet_name='Statistics')

        # Save correlation matrix
        df_correlation = pd.DataFrame(correlationMatrix, index=names, columns=names)
        df_correlation.to_excel(writer, sheet_name='Correlation')

        # Save distance matrix
        df_distance = pd.DataFrame(distanceMatrix, index=names, columns=names)
        df_distance.to_excel(writer, sheet_name='Distance')

    print(f'Excel file saved: {excel_filename}')



#Function Calls

All_Results = save_results(Testing_Data_Set)
plot_results(All_Results,Testing_Data_Set)
indicators(All_Results, Testing_Data_Set)



