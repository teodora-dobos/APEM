import pandas as pd

from apem.EU_market_model.euphemia.utils.paths import DATA_DIR

'''
--- OMIE ---
Step 1
This script can be used to parse raw OMIE data to csv
Download data from 4. Bid section from https://www.omie.es/en/file-access-list#Day-ahead%20Market4.%20Bids?parent=Day-ahead%20Market
'''

# === STEP 1: Define file paths ===
cab_path = DATA_DIR / "omie/raw_data/CAB_20250318.1"
det_path = DATA_DIR / "omie/raw_data/DET_20250318.1"
output_csv = DATA_DIR / "omie/raw_data/OMIE_orderdata_parsed.csv"

# === STEP 2: Read DET file (detail of orders) ===
det_colspecs = [
    (0, 7),   # CodOferta
    (7, 10),  # Version
    (10, 12),  # Período
    (12, 14),  # NumBloq
    (31, 48),  # PrecEuro
    (48, 55),  # Energía
    (55, 56),  # BloqInd
    (56, 57),  # BloqRet
]
det_columns = ['cod_oferta', 'version', 'periodo', 'num_bloq',
               'prec_euro', 'energia', 'bloq_ind', 'bloq_ret']
det_df = pd.read_fwf(det_path, colspecs=det_colspecs, names=det_columns, encoding="latin1")

# === STEP 3: Read CAB file (header metadata) ===
cab_colspecs = [
    (0, 7),    # CodOferta
    (7, 10),   # Version
    (10, 17),  # Código Unidad
    (17, 47),  # Descripción
    (47, 48),  # CV
    (49, 50),  # OferPlazo
    (84, 91),  # MaxRamSub
    (91, 98),  # MaxRamBaj
    (98, 115), # Fijoeuro
    (115, 132),# Vareuro
    (132, 139),# MaxPot
    (139, 146),# MaxRamArr
    (146, 153),# MaxRamPar
    (153, 155),# CodInt
    (155, 169) # timestamp (Año, Mes, Día, Hora, Minuto, Segundo)
]

cab_columns = ['cod_oferta', 'version', 'codigo_unidad', 'descripcion', 'cv', 'ofer_plazo', 'max_ram_sub', 'max_ram_baj',
               'fijoeuro', 'vareuro', 'max_pot', 'max_ram_arr', 'max_ram_par', 'cod_int', 'timestamp']
cab_df = pd.read_fwf(cab_path, colspecs=cab_colspecs, names=cab_columns, encoding="latin1")

print(cab_df.head())
print(det_df.head())

# === STEP 4: Normalize CodOferta for merging ===
det_df['cod_oferta'] = det_df['cod_oferta'].astype(str).str.strip()
cab_df['cod_oferta'] = cab_df['cod_oferta'].astype(str).str.strip()

# === STEP 5: Merge both datasets ===
merged_df = pd.merge(det_df, cab_df, on="cod_oferta", how="left")

# === STEP 6: Export as CSV ===
merged_df.to_csv(output_csv, index=False, encoding="utf-8")

print(f"File successfully exported: {output_csv}")
