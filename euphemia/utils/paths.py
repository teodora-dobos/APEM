from pathlib import Path
from apem.data.parsing.parse_pypsa_eur_small import ParsePyPSAEurSmall
from apem.data.parsing.parse_pjm import ParsePJM
from apem.data.parsing.parse_pypsa_eur_large import ParsePyPSAEurLarge
from apem.data.parsing.parse_arpa import ParseARPA
from apem.data.parsing.parse_ieee_rts import ParseIEEERTS


# Root of EUPHEMIA package
EUPHEMIA_ROOT = Path(__file__).resolve().parent.parent

# Path to raw data inside EUPHEMIA
RAW_DATA_DIR = EUPHEMIA_ROOT / "data" / "raw_data"

CONVERTED_DATASET_PATH_MAP = {
    ParseIEEERTS: RAW_DATA_DIR / "ieee_rts",
    ParsePJM: RAW_DATA_DIR / "pjm",
    ParseARPA: RAW_DATA_DIR / "arpa",
    ParsePyPSAEurLarge: RAW_DATA_DIR / "pypsa_large",
    ParsePyPSAEurSmall: RAW_DATA_DIR / "pypsa_small",
}

def ensure_dir(path: Path):
    """Ensure the given directory exists."""
    path.mkdir(parents=True, exist_ok=True)