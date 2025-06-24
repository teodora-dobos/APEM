import pandas as pd

from euphemia.utils.paths import RAW_DATA_DIR

'''
--- OMIE ---
Step 1
This script can be used to parse raw OMIE data to csv
Download data from 4. Bid section from https://www.omie.es/en/file-access-list#Day-ahead%20Market4.%20Bids?parent=Day-ahead%20Market
'''

# === STEP 1: Define file paths ===
cab_path = RAW_DATA_DIR / "omie/CAB_20250325.1"
det_path = RAW_DATA_DIR / "omie/DET_20250325.1"
output_csv = RAW_DATA_DIR / "omie/OMIE_orderdata_parsed.csv"

# === STEP 2: Read DET file (detail of orders) ===
det_colspecs = [
    (0, 10),   # cod_oferta
    (10, 15),  # version
    (15, 18),  # periodo
    (18, 20),  # num_block
    (20, 22),  # num_tramo
    (22, 24),  # grupo_excl
    (24, 41),  # precio
    (41, 48),  # cantidad
    (48, 55),  # mav
    (55, 61),  # mar
]
det_columns = ['cod_oferta', 'version', 'periodo', 'num_block', 'num_tramo',
               'grupo_excl', 'precio', 'cantidad', 'mav', 'mar']
det_df = pd.read_fwf(det_path, colspecs=det_colspecs, names=det_columns, encoding="latin1")

# === STEP 3: Read CAB file (header metadata) ===
cab_colspecs = [
    (0, 10),   # cod_oferta
    (10, 15),  # version
    (15, 22),  # cod_uof
    (22, 52),  # unidad
    (52, 53),  # cv
    (53, 54),  # ofer_plazo
    (54, 71),  # fijo_eur
    (71, 78),  # potencia_max
    (78, 80),  # cod_int
    (80, 93),  # timestamp
]
cab_columns = ['cod_oferta', 'version_hdr', 'cod_uof', 'unidad', 'cv', 'ofer_plazo',
               'fijo_eur', 'potencia_max', 'cod_int', 'timestamp']
cab_df = pd.read_fwf(cab_path, colspecs=cab_colspecs, names=cab_columns, encoding="latin1")

# === STEP 4: Normalize cod_oferta for merging ===
det_df['cod_oferta'] = det_df['cod_oferta'].astype(str).str.strip()
cab_df['cod_oferta'] = cab_df['cod_oferta'].astype(str).str.strip()

# === STEP 5: Merge both datasets ===
merged_df = pd.merge(det_df, cab_df, on="cod_oferta", how="left")

# === STEP 6: Export as CSV ===
merged_df.to_csv(output_csv, index=False, encoding="utf-8")

print(f"File successfully exported: {output_csv}")
