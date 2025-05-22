import os
import numpy as np
import pandas as pd

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