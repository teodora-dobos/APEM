from pathlib import Path
from apem.unit_based_model.data.parsing.parse_pypsa_eur_small import ParsePyPSAEurSmall
from apem.unit_based_model.data.parsing.parse_pjm import ParsePJM
from apem.unit_based_model.data.parsing.parse_pypsa_eur_large import ParsePyPSAEurLarge
from apem.unit_based_model.data.parsing.parse_arpa import ParseARPA
from apem.unit_based_model.data.parsing.parse_ieee_rts import ParseIEEERTS

# Root of EUPHEMIA package
EUPHEMIA_ROOT = Path(__file__).resolve().parent.parent

# Path to raw data inside EUPHEMIA
DATA_DIR = EUPHEMIA_ROOT / "data" / "datasets"

CONVERTED_DATASET_PATH_MAP = {
    ParseIEEERTS: DATA_DIR / "ieee_rts",
    ParsePJM: DATA_DIR / "pjm",
    ParseARPA: DATA_DIR / "arpa",
    ParsePyPSAEurLarge: DATA_DIR / "pypsa_large",
    ParsePyPSAEurSmall: DATA_DIR / "pypsa_small",
}


def ensure_dir(path: Path):
    """Ensure the given directory exists."""
    path.mkdir(parents=True, exist_ok=True)

