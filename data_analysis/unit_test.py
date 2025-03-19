## Unit test 
# Validates the output files in the results folder to ensure correct data types. The output is displayed in the terminal.
# Currently only for DCOPF. Should be extended after implementation of Euphemia..
# Possibility of more precise output by changing precise_output = 1.

import os
import re
import sys

#Determines the path of the current .py file
script_path = os.path.dirname(os.path.abspath(__file__))

# Sets the current working directory to this path
os.chdir(script_path)
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


Testing_Data_Set = 'PyPSAEurLarge'  # Choose between IEEE_RTS, PJM, PyPSAEurSmall, PyPSAEurLarge, ARPA
precise_output = 0  # Set to 1 for detailed output


def unit_test_pricing_stats(testing_data_set, precise_output):
    # Base folder, derived from the dataset name
    modified_string = re.sub(r'([A-Z])([a-z])([a-z])', r'_\1\2\3', testing_data_set)
    base_path = os.path.join('..', 'results', f'{modified_string}_results', 'DCOPF')

    # Files to check
    result_files = ['ELMP_results/ELMP_stats.txt', 
                    'IP_results/IP_stats.txt', 
                    'Join_results/Join_stats.txt', 
                    'Min_MWP_results/Min_MWP_stats.txt']
    
    all_files_valid = True

    for result_file in result_files:
        file_path = os.path.join(base_path, result_file)
        if precise_output:
            print(f'Checking file: {file_path}')

        # Read file content
        try:
            with open(file_path, 'r') as file:
                file_content = file.read()
                is_valid = validate_stats_txt_structure(file_content)

                if is_valid:
                    if precise_output:
                        print(f'{result_file}: File structure is valid.')
                else:
                    if precise_output:
                        print(f'{result_file}: File structure is invalid.')
                    all_files_valid = False  # Set to false if a structure validation fails
        
        except Exception as e:
            print(f'Error reading file: {file_path}')
            all_files_valid = False  # Set to false if the file cannot be read
    
    # Final message on success
    if all_files_valid:
        print('All stats.txt files of the pricing results have a valid structure.')
    else:
        print('Some stats.txt files of the pricing results did not have a valid structure.')


def validate_stats_txt_structure(file_content):
    # Required patterns for structure validation
    required_structure = [
        r'GLOCs buyers: -?\d+\.\d+',
        r'GLOCs sellers: -?\d+\.\d+',
        r'GLOCs network: -?\d+\.\d+',
        r'Total GLOCs: -?\d+\.\d+',
        r'LLOCs buyers: -?\d+\.\d+',
        r'LLOCs sellers: -?\d+\.\d+',
        r'LLOCs network: -?\d+\.\d+',
        r'Total LLOCs: -?\d+\.\d+',
        r'MWPs buyers: -?\d+\.\d+',
        r'MWPs sellers: -?\d+\.\d+',
        r'MWPs network: -?\d+\.\d+',
        r'Total MWPs: -?\d+\.\d+',
        r'Runtime in seconds: \d+\.\d+',
        r'Number of Variables: \d+',
        r'Number of Constraints: \d+',
        r'Average price: -?\d+\.\d+'
    ]

    # Split the file content into lines
    lines = file_content.split('\n')
    
    # Remove empty lines and those with only spaces
    lines = [line for line in lines if line.strip()]
    
    # Remove lines containing specific unwanted characters
    lines = [line for line in lines if '←' not in line]

    is_valid = True

    # Check the structure
    for k, pattern in enumerate(required_structure):
        if k >= len(lines) or not re.search(pattern, lines[k]):
            is_valid = False
            break

    return is_valid




def unit_test_pricing_csv(testing_data_set, precise_output):
    # Base folder, derived from the dataset name
    modified_string = re.sub(r'([A-Z])([a-z])([a-z])', r'_\1\2\3', testing_data_set)
    base_path = os.path.join('..', 'results', f'{modified_string}_results', 'DCOPF')

    # CSV files to check that follow the "Join" pattern
    csv_files = ['ELMP_results/ELMP_prices.csv', 
                 'IP_results/IP_prices.csv', 
                 'Join_results/Join_prices.csv', 
                 'Min_MWP_results/Min_MWP_prices.csv']
    
    all_csv_files_valid = True  # Variable to track the status of all CSV files

    for csv_file in csv_files:
        file_path = os.path.join(base_path, csv_file)
        if precise_output:
            print(f'Checking CSV file: {file_path}')

        try:
            # Read CSV file content
            with open(file_path, 'r') as file:
                file_content = file.read()
                is_valid = validate_prices_csv_structure(file_content)

                if is_valid:
                    if precise_output:
                        print(f'{csv_file}: CSV structure is valid.')
                else:
                    if precise_output:
                        print(f'{csv_file}: CSV structure is invalid.')
                    all_csv_files_valid = False  # Set to false if a structure validation fails
            
        except Exception as e:
            print(f'Error reading CSV file: {file_path}')
            all_csv_files_valid = False  # Set to false if the file cannot be read

    # Final message on success
    if all_csv_files_valid:
        print('All prices.csv files of the pricing results have a valid structure.')
    else:
        print('Some prices.csv files of the pricing results did not have a valid structure.')


def validate_prices_csv_structure(file_content):
    
    # Regular expressions for the six types
    patterns = [
        r'^DE0 -?\d+,-?\d+,-?\d+\.\d+', #PyPSAEurSmall
        r'^\d+,-?\d+,-?\d+\.\d+' #PyPSAEurLarge
    ]

    # Split into lines
    lines = file_content.strip().split('\n')

    is_valid = True
    for k in range(1, len(lines)):  # Start from 1 because the first line may be a header or empty
        line = lines[k].strip()
        # Skip empty lines
        if not line:
            continue
        # Check if the line matches any of the patterns
        if not any(re.match(pattern, line) for pattern in patterns):
            is_valid = False
            break

    return is_valid
    
    


def unit_test_allocation_stats(testing_data_set, precise_output):
    # Base folder, derived from the dataset name
    modified_string = re.sub(r'([A-Z])([a-z])([a-z])', r'_\1\2\3', testing_data_set)
    base_path = os.path.join('..', 'results', f'{modified_string}_results', 'DCOPF')

    # Files to check
    result_files = ['allocation_results/DCOPF_stats.txt']
    
    all_files_valid = True

    for result_file in result_files:
        file_path = os.path.join(base_path, result_file)
        if precise_output:
            print(f'Checking file: {file_path}')

        # Read file content
        try:
            with open(file_path, 'r') as file:
                file_content = file.read()
                is_valid = validate_stats_DCOPF_txt_structure(file_content)

                if is_valid:
                    if precise_output:
                        print(f'{result_file}: File structure is valid.')
                else:
                    if precise_output:
                        print(f'{result_file}: File structure is invalid.')
                    all_files_valid = False  # Set to false if a structure validation fails
        
        except Exception as e:
            print(f'Error reading file: {file_path}')
            all_files_valid = False  # Set to false if the file cannot be read
    
    # Final message on success
    if all_files_valid:
        print('All stats.txt files of the allocation results have a valid structure.')
    else:
        print('Some stats.txt files of the allocation results did not have a valid structure.')


def validate_stats_DCOPF_txt_structure(file_content):
    # Required patterns for structure validation
    required_structure = required_structure = [
        r'Welfare period \d+: -?\d+\.\d+',  # Welfare period
        r'Total welfare: -?\d+\.\d+',  # Total welfare
        r'Total INELASTIC DEMAND: -?\d+\.\d+',  # Total inelastic demand
        r'Total ELASTIC DEMAND: -?\d+\.\d+',  # Total elastic demand
        r'Total supply: -?\d+\.\d+',  # Total supply
        r'Fulfilled elastic demand: \d+',  # Fulfilled elastic demand
        r'Supply = -?\d+\.\d+',  # Supply
        r'Demand = -?\d+\.\d+',  # Demand
        r'Final MIP gap value: -?\d+\.\d+e?-?\d*',  # MIP gap value
        r'Nodes: \d+',  # Nodes
        r'Branches: \d+',  # Branches
        r'Buyers: \d+',  # Buyers
        r'Sellers: \d+',  # Sellers
        r'Constraints: \d+',  # Constraints
        r'Variables: \d+',  # Variables
        r'Runtime in sec: -?\d+\.\d+'  # Runtime in seconds
    ]

    # Adjusting for multiple welfare periods
    welfare_period_pattern = r'Welfare period \d+: -?\d+\.\d+'
    for i in range(1, 24):  # For 24 occurrences of Welfare period
        required_structure.insert(i-1, welfare_period_pattern)

    # Split the file content into lines
    lines = file_content.split('\n')
    
    # Remove empty lines and those with only spaces
    lines = [line for line in lines if line.strip()]
    
    # Remove lines containing specific unwanted characters
    lines = [line for line in lines if '←' not in line]

    is_valid = True

    # Check the structure
    for k, pattern in enumerate(required_structure):
        if k >= len(lines) or not re.search(pattern, lines[k]):
            is_valid = False
            break

    return is_valid





def unit_test_allocation_csv(testing_data_set, precise_output):
    # Base folder, derived from the dataset name
    modified_string = re.sub(r'([A-Z])([a-z])([a-z])', r'_\1\2\3', testing_data_set)
    base_path = os.path.join('..', 'results', f'{modified_string}_results', 'DCOPF')

    # CSV files to check that follow the "Join" pattern
    csv_files = ['allocation_results/DCOPF.csv']

    all_csv_files_valid = True  # Variable to track the status of all CSV files

    for csv_file in csv_files:
        file_path = os.path.join(base_path, csv_file)
        if precise_output:
            print(f'Checking CSV file: {file_path}')

        try:
            # Read CSV file content
            with open(file_path, 'r') as file:
                file_content = file.read()
                is_valid = validate_prices_allocation_csv_structure(file_content)

                if is_valid:
                    if precise_output:
                        print(f'{csv_file}: CSV structure is valid.')
                else:
                    if precise_output:
                        print(f'{csv_file}: CSV structure is invalid.')
                    all_csv_files_valid = False  # Set to false if a structure validation fails
            
        except Exception as e:
            print(f'Error reading CSV file: {file_path}')
            all_csv_files_valid = False  # Set to false if the file cannot be read

    # Final message on success
    if all_csv_files_valid:
        print('All prices.csv files of the allocation results have a valid structure.')
    else:
        print('Some prices.csv files of the allocation results did not have a valid structure.')


def validate_prices_allocation_csv_structure(file_content):
  
    # Regular expressions for the six types
    patterns = [
        #PyPSAEurSmall
        r'^x_bt\[[A-ZA-Z0-9]+ \d+,\d+\],-?\d+\.\d+$',  # x_bt
        r'^y_st\[\d+,\d+\],-?\d+\.\d+$',  # y_st
        r'^y_stl\[\d+,\d+,\d+\],-?\d+\.\d+$',  # y_stl
        r'^u_st\[\d+,\d+\],-?\d+\.\d+$',  # u_st
        r'^phi_st\[\d+,\d+\],-?\d+\.\d+$',  # phi_st
        r'^alpha_vt\[[A-Za-z0-9]+\s*\d*,\d+\],-?\d+\.\d+$',  # alpha_vt
        r'^f_vwt\[[A-Za-z0-9]+ \d+,[A-Za-z0-9]+ \d+,\d+\],-?\d+\.\d+$',  # f_vwt

        #PyPSAEurLarge
        r'^x_bt\[\d+,\d+\],-?\d+\.\d+$',  # x_bt
        r'^y_st\[\d+,\d+\],-?\d+\.\d+$',  # y_st
        r'^y_stl\[\d+,\d+,\d+\],-?\d+\.\d+$',  # y_stl
        r'^u_st\[\d+,\d+\],-?\d+\.\d+$',  # u_st
        r'^phi_st\[\d+,\d+\],-?\d+\.\d+$',  # phi_st
        r'^alpha_vt\[\s*\d*,\d+\],-?\d+\.\d$',  # alpha_vt
        r'^f_vwt\[\d+,\d+,\d+\],-?\d+\.\d+$',  # f_vwt
        r'^x_bt\[\d+,\d+\],-?\d+\.\d+[a-z]-?\d\d$',  # x_bt
        r'^y_st\[\d+,\d+\],-?\d+\.\d+[a-z]-?\d\d$',  # y_st
        r'^y_stl\[\d+,\d+,\d+\],-?\d+\.\d+[a-z]-?\d\d$',  # y_stl
        r'^u_st\[\d+,\d+\],-?\d+\.\d+[a-z]-?\d\d$',  # u_st
        r'^phi_st\[\d+,\d+\],-?\d+\.\d+$',  # phi_st
        r'^alpha_vt\[\s*\d*,\d+\],-?\d+\.\d[a-z]-?\d\d$',  # alpha_vt
        r'^f_vwt\[\d+,\d+,\d+\],-?\d+\.\d+[a-z]-?\d\d$'  # f_vwt
    ]

    # Split into lines
    lines = file_content.strip().split('\n')

    is_valid = True
    for k in range(1, len(lines)):  # Start from 1 because the first line may be a header or empty
        line = lines[k].strip()
        line = line.replace('"', '')
        # Skip empty lines
        if not line:
            continue
        # Check if the line matches any of the patterns
        if not any(re.match(pattern, line) for pattern in patterns):
            is_valid = False
            break

    return is_valid




#Function Calls

unit_test_pricing_stats(Testing_Data_Set, precise_output)
unit_test_pricing_csv(Testing_Data_Set, precise_output)
unit_test_allocation_stats(Testing_Data_Set, precise_output)
unit_test_allocation_csv(Testing_Data_Set, precise_output)
