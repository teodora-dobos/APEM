import pandas as pd
import os
from collections import defaultdict

"""
--- GME ---
Helps merging raw period data into one big file that can be further adjusted in order to be readable by EUPHEMIA
example data: https://www.mercatoelettrico.org/it-it/Home/Esiti/Elettricita/MGP/Esiti/DomandaOfferta#IntestazioneGrafico
"""

# Folder containing the input Excel files
folder_path = "<>"  # e.g. "/Users/yourname/Documents/Excels"

# Folder to save the merged output files
output_folder = os.path.join(folder_path, "merged_by_sheet")
os.makedirs(output_folder, exist_ok=True)

# Collect all .xlsx files in the folder
excel_files = [f for f in os.listdir(folder_path) if f.endswith(".xlsx")]

# Dictionary to collect sheets by name
# Format: {"Sheet1": [df1, df2, ...], "Sheet2": [...]}
sheets_dict = defaultdict(list)

for file in excel_files:
    file_path = os.path.join(folder_path, file)
    try:
        # Read all sheets from the file
        sheets = pd.read_excel(file_path, sheet_name=None)

        for sheet_name, df in sheets.items():
            df["SourceFile"] = file  # Optional: track origin
            sheets_dict[sheet_name].append(df)

    except Exception as e:
        print(f"Error processing {file}: {e}")

# Merge and save one file per sheet name
for sheet_name, df_list in sheets_dict.items():
    try:
        merged_df = pd.concat(df_list, ignore_index=True)
        safe_name = "".join(c for c in sheet_name if c.isalnum() or c in (' ', '_')).rstrip()
        output_path = os.path.join(output_folder, f"{safe_name}.xlsx")
        merged_df.to_excel(output_path, index=False)
        print(f"Saved merged sheet: {output_path}")
    except Exception as e:
        print(f"Error saving {sheet_name}: {e}")
