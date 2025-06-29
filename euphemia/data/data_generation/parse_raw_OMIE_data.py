import pandas as pd

from euphemia.utils.paths import RAW_DATA_DIR

'''
--- OMIE ---
Step 1
This script can be used to parse raw OMIE data to csv
Download data from 4. Bid section from https://www.omie.es/en/file-access-list#Day-ahead%20Market4.%20Bids?parent=Day-ahead%20Market
'''

# === STEP 1: Define file paths ===
cab_path = RAW_DATA_DIR / "omie/CAB_20250318.1"
det_path = RAW_DATA_DIR / "omie/DET_20250318.1"
output_csv = RAW_DATA_DIR / "omie/OMIE_orderdata_parsed.csv"

# === STEP 2: Read DET file (detail of orders) ===
det_colspecs = [
    (0, 10),   # cod_oferta
    (10, 15),  # version
    (15, 18),  # periodo
    (18, 20),  # num_block - 0 for simple order
    (20, 22),  # num_tramo - 1 for block order
    (22, 24),  # grupo_excl - exclusive block order group
    (24, 41),  # precio
    (41, 48),  # cantidad
    (48, 55),  # mav
    (55, 60),  # mar
]
det_columns = ['cod_oferta', 'version', 'periodo', 'num_block', 'num_tramo',
               'grupo_excl', 'precio', 'cantidad', 'mav', 'mar']
det_df = pd.read_fwf(det_path, colspecs=det_colspecs, names=det_columns, encoding="latin1")

# === STEP 3: Read CAB file (header metadata) ===
cab_colspecs = [
    (0, 7),    # cod_oferta
    (7, 10),   # version
    (10, 17),  # cod_uof
    (17, 47),  # unidad
    (47, 48),  # cv - C=buy V=sell
    (49, 50),  # ofer_plazo
    (84, 91),  # MaxRamSub - Up load gradient
    (91, 98),  # MaxRamBaj - Down load gradient
    (98, 115), # fijo_eur - fixed term
    (115, 132),# var_eur - variable term
    (132, 139),# potencia_max
    (139, 146),# MaxRamArr - Startup load gradient
    (146, 153),# MaxRamPar - Stopping load gradient
    (153, 155),# cod_int
    (155, 169) # timestamp
]

cab_columns = ['cod_oferta', 'version', 'cod_uof', 'unidad', 'cv', 'ofer_plazo', 'max_ram_sub', 'max_ram_baj',
               'fijo_eur', 'var_eur', 'potencia_max', 'max_ram_arr', 'max_ram_par', 'cod_int', 'timestamp']
cab_df = pd.read_fwf(cab_path, colspecs=cab_colspecs, names=cab_columns, encoding="latin1")

print(cab_df.head())
print(det_df.head())

# === STEP 4: Normalize cod_oferta for merging ===
det_df['cod_oferta'] = det_df['cod_oferta'].astype(str).str.strip()
cab_df['cod_oferta'] = cab_df['cod_oferta'].astype(str).str.strip()

# === STEP 5: Merge both datasets ===
merged_df = pd.merge(det_df, cab_df, on="cod_oferta", how="left")

# === STEP 6: Export as CSV ===
merged_df.to_csv(output_csv, index=False, encoding="utf-8")

print(f"File successfully exported: {output_csv}")
