import os
import re
import pandas as pd

def save_results(testing_data_set):
    """Saves the results of the algorithms into an Excel file.

    Args:
        testing_data_set (str): The dataset for which results are being saved. 

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