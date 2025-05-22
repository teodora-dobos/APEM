import os
import re
import sys

# Sets the current working directory to this path
script_path = os.path.dirname(os.path.abspath(__file__))
parent_path = os.path.dirname(script_path)
os.chdir(parent_path)
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

Testing_Data_Set = 'PyPSAEurLarge'  # Choose between IEEE_RTS, PJM, PyPSAEurSmall, PyPSAEurLarge, ARPA
precise_output = 0  # Set to 1 for detailed output

def unit_test_pricing_stats(testing_data_set, precise_output):
    """Validates the output files in the results folder to ensure correct data types for pricing stats.

    Args:
        testing_data_set (str): The dataset to be validated. IEEE_RTS, PJM, PyPSAEurSmall, PyPSAEurLarge, ARPA
        precise_output (int): Set to 1 for detailed output in the terminal.
    """
    modified_string = re.sub(r'([A-Z])([a-z])([a-z])', r'_\1\2\3', testing_data_set)
    base_path = os.path.join('..', 'results', f'{modified_string}_results', 'DCOPF')

    result_files = ['ELMP_results/ELMP_stats.txt', 
                    'IP_results/IP_stats.txt', 
                    'Join_results/Join_stats.txt']
    
    all_files_valid = True

    for result_file in result_files:
        file_path = os.path.join(base_path, result_file)
        if precise_output:
            print(f'Checking file: {file_path}')

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
                    all_files_valid = False
        
        except Exception as e:
            print(f'Error reading file: {file_path}')
            all_files_valid = False
    
    if all_files_valid:
        print('All stats.txt files of the pricing results have a valid structure.')
    else:
        print('Some stats.txt files of the pricing results did not have a valid structure.')

def validate_stats_txt_structure(file_content):
    """Validates the structure of the stats.txt file content.

    Args:
        file_content (str): The content of the file to validate.

    Returns:
        bool: True if the structure is valid, else False.
    """
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

    lines = [line for line in file_content.split('\n') if line.strip() and '←' not in line]

    is_valid = True

    for k, pattern in enumerate(required_structure):
        if k >= len(lines) or not re.search(pattern, lines[k]):
            is_valid = False
            break

    return is_valid

def unit_test_pricing_csv(testing_data_set, precise_output):
    """Validates the output CSV files in the results folder for pricing data.

    Args:
        testing_data_set (str): The dataset to be validated.
        precise_output (int): Set to 1 for detailed output in the terminal.
    """
    modified_string = re.sub(r'([A-Z])([a-z])([a-z])', r'_\1\2\3', testing_data_set)
    base_path = os.path.join('..', 'results', f'{modified_string}_results', 'DCOPF')

    csv_files = ['ELMP_results/ELMP_prices.csv', 
                 'IP_results/IP_prices.csv', 
                 'Join_results/Join_prices.csv']
    
    all_csv_files_valid = True

    for csv_file in csv_files:
        file_path = os.path.join(base_path, csv_file)
        if precise_output:
            print(f'Checking CSV file: {file_path}')

        try:
            with open(file_path, 'r') as file:
                file_content = file.read()
                is_valid = validate_prices_csv_structure(file_content)

                if is_valid:
                    if precise_output:
                        print(f'{csv_file}: CSV structure is valid.')
                else:
                    if precise_output:
                        print(f'{csv_file}: CSV structure is invalid.')
                    all_csv_files_valid = False
            
        except Exception as e:
            print(f'Error reading CSV file: {file_path}')
            all_csv_files_valid = False

    if all_csv_files_valid:
        print('All prices.csv files of the pricing results have a valid structure.')
    else:
        print('Some prices.csv files of the pricing results did not have a valid structure.')

def validate_prices_csv_structure(file_content):
    """Validates the structure of the prices CSV file content.

    Args:
        file_content (str): The content of the CSV file to validate.

    Returns:
        bool: True if the structure is valid, else False.
    """
    patterns = [
        r'^DE0 -?\d+,-?\d+,-?\d+\.\d+', #PyPSAEurSmall
        r'^\d+,-?\d+,-?\d+\.\d+' #PyPSAEurLarge
    ]

    lines = file_content.strip().split('\n')

    is_valid = True
    for k in range(1, len(lines)):
        line = lines[k].strip()
        if not line:
            continue
        if not any(re.match(pattern, line) for pattern in patterns):
            is_valid = False
            break

    return is_valid

def unit_test_allocation_stats(testing_data_set, precise_output):
    """Validates the output files in the results folder for allocation stats.

    Args:
        testing_data_set (str): The dataset to be validated.
        precise_output (int): Set to 1 for detailed output in the terminal.
    """
    modified_string = re.sub(r'([A-Z])([a-z])([a-z])', r'_\1\2\3', testing_data_set)
    base_path = os.path.join('..', 'results', f'{modified_string}_results', 'DCOPF')

    result_files = ['allocation_results/DCOPF_stats.txt']
    
    all_files_valid = True

    for result_file in result_files:
        file_path = os.path.join(base_path, result_file)
        if precise_output:
            print(f'Checking file: {file_path}')

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
                    all_files_valid = False
        
        except Exception as e:
            print(f'Error reading file: {file_path}')
            all_files_valid = False
    
    if all_files_valid:
        print('All stats.txt files of the allocation results have a valid structure.')
    else:
        print('Some stats.txt files of the allocation results did not have a valid structure.')

def validate_stats_DCOPF_txt_structure(file_content):
    """Validates the structure of the DCOPF stats.txt file content.

    Args:
        file_content (str): The content of the file to validate.

    Returns:
        bool: True if the structure is valid, else False.
    """
    required_structure = [
        r'Welfare period \d+: -?\d+\.\d+',
        r'Total welfare: -?\d+\.\d+',
        r'Total INELASTIC DEMAND: -?\d+\.\d+',
        r'Total ELASTIC DEMAND: -?\d+\.\d+',
        r'Total supply: -?\d+\.\d+',
        r'Fulfilled elastic demand: \d+',
        r'Supply = -?\d+\.\d+',
        r'Demand = -?\d+\.\d+',
        r'Final MIP gap value: -?\d+\.\d+e?-?\d*',
        r'Nodes: \d+',
        r'Branches: \d+',
        r'Buyers: \d+',
        r'Sellers: \d+',
        r'Constraints: \d+',
        r'Variables: \d+',
        r'Runtime in sec: -?\d+\.\d+'
    ]

    welfare_period_pattern = r'Welfare period \d+: -?\d+\.\d+'
    for i in range(1, 24):
        required_structure.insert(i-1, welfare_period_pattern)

    lines = [line for line in file_content.split('\n') if line.strip() and '←' not in line]

    is_valid = True

    for k, pattern in enumerate(required_structure):
        if k >= len(lines) or not re.search(pattern, lines[k]):
            is_valid = False
            break

    return is_valid

def unit_test_allocation_csv(testing_data_set, precise_output):
    """Validates the output CSV files in the results folder for allocation data.

    Args:
        testing_data_set (str): The dataset to be validated.
        precise_output (int): Set to 1 for detailed output in the terminal.
    """
    modified_string = re.sub(r'([A-Z])([a-z])([a-z])', r'_\1\2\3', testing_data_set)
    base_path = os.path.join('..', 'results', f'{modified_string}_results', 'DCOPF')

    csv_files = ['allocation_results/DCOPF.csv']

    all_csv_files_valid = True

    for csv_file in csv_files:
        file_path = os.path.join(base_path, csv_file)
        if precise_output:
            print(f'Checking CSV file: {file_path}')

        try:
            with open(file_path, 'r') as file:
                file_content = file.read()
                is_valid = validate_prices_allocation_csv_structure(file_content)

                if is_valid:
                    if precise_output:
                        print(f'{csv_file}: CSV structure is valid.')
                else:
                    if precise_output:
                        print(f'{csv_file}: CSV structure is invalid.')
                    all_csv_files_valid = False
            
        except Exception as e:
            print(f'Error reading CSV file: {file_path}')
            all_csv_files_valid = False

    if all_csv_files_valid:
        print('All prices.csv files of the allocation results have a valid structure.')
    else:
        print('Some prices.csv files of the allocation results did not have a valid structure.')

def validate_prices_allocation_csv_structure(file_content):
    """Validates the structure of the allocation prices CSV file content.

    Args:
        file_content (str): The content of the CSV file to validate.

    Returns:
        bool: True if the structure is valid, else False.
    """
    patterns = [
        r'^x_bt\[[A-ZA-Z0-9]+ \d+,\d+\],-?\d+\.\d+$',  # x_bt
        r'^y_st\[\d+,\d+\],-?\d+\.\d+$',  # y_st
        r'^y_stl\[\d+,\d+,\d+\],-?\d+\.\d+$',  # y_stl
        r'^u_st\[\d+,\d+\],-?\d+\.\d+$',  # u_st
        r'^phi_st\[\d+,\d+\],-?\d+\.\d+$',  # phi_st
        r'^alpha_vt\[[A-Za-z0-9]+\s*\d*,\d+\],-?\d+\.\d+$',  # alpha_vt
        r'^f_vwt\[[A-Za-z0-9]+ \d+,[A-Za-z0-9]+ \d+,\d+\],-?\d+\.\d+$',  # f_vwt
        r'^x_bt\[\d+,\d+\],-?\d+\.\d+$',  # x_bt
        r'^y_st\[\d+,\d+\],-?\d+\.\d+$',  # y_st
        r'^y_stl\[\d+,\d+,\d+\],-?\d+\.\d+$',  # y_stl
        r'^u_st\[\d+,\d+\],-?\d+\.\d+$',  # u_st
        r'^phi_st\[\d+,\d+\],-?\d+\.\d+$',  # phi_st
        r'^alpha_vt\[\s*\d*,\d+\],-?\d+\.\d$',  # alpha_vt
        r'^f_vwt\[\d+,\d+,\d+\],-?\d+\.\d+$'  # f_vwt
    ]

    lines = file_content.strip().split('\n')

    is_valid = True
    for k in range(1, len(lines)):
        line = lines[k].strip().replace('"', '')
        if not line:
            continue
        if not any(re.match(pattern, line) for pattern in patterns):
            is_valid = False
            break

    return is_valid

# Function Calls
unit_test_pricing_stats(Testing_Data_Set, precise_output)
unit_test_pricing_csv(Testing_Data_Set, precise_output)
unit_test_allocation_stats(Testing_Data_Set, precise_output)
unit_test_allocation_csv(Testing_Data_Set, precise_output)





