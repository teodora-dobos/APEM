import os
from collections import defaultdict

import pandas as pd

"""
--- GME ---
Merge multiple raw period Excel files into one output workbook per sheet name.
Example data:
https://www.mercatoelettrico.org/it-it/Home/Esiti/Elettricita/MGP/Esiti/DomandaOfferta#IntestazioneGrafico
"""


def merge_excels_by_sheet(folder_path: str) -> None:
    # Folder to save the merged output files
    output_folder = os.path.join(folder_path, "merged_by_sheet")
    os.makedirs(output_folder, exist_ok=True)

    # Collect all .xlsx files in the folder
    excel_files = [f for f in os.listdir(folder_path) if f.endswith(".xlsx")]

    # Format: {"Sheet1": [df1, df2, ...], "Sheet2": [...]}
    sheets_dict = defaultdict(list)

    for file in excel_files:
        file_path = os.path.join(folder_path, file)
        try:
            sheets = pd.read_excel(file_path, sheet_name=None)
            for sheet_name, df in sheets.items():
                df["SourceFile"] = file  # Optional: track origin
                sheets_dict[sheet_name].append(df)
        except Exception as e:  # noqa: BLE001
            print(f"Error processing {file}: {e}")

    # Merge and save one file per sheet name
    for sheet_name, df_list in sheets_dict.items():
        try:
            merged_df = pd.concat(df_list, ignore_index=True)
            safe_name = "".join(c for c in sheet_name if c.isalnum() or c in (" ", "_")).rstrip()
            output_path = os.path.join(output_folder, f"{safe_name}.xlsx")
            merged_df.to_excel(output_path, index=False)
            print(f"Saved merged sheet: {output_path}")
        except Exception as e:  # noqa: BLE001
            print(f"Error saving {sheet_name}: {e}")


def main() -> None:
    # Set this to your input folder before running directly.
    folder_path = "<>"
    if folder_path == "<>":
        raise ValueError("Set 'folder_path' in merge_GME_data.py before running this script.")
    merge_excels_by_sheet(folder_path)


if __name__ == "__main__":
    main()
