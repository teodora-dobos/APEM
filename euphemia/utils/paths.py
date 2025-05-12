from pathlib import Path

# Root of APEM package
EUPHEMIA_ROOT = Path(__file__).resolve().parent.parent

# Path to raw data inside APEM
RAW_DATA_DIR = EUPHEMIA_ROOT / "data" / "raw_data"

def ensure_dir(path: Path):
    """Ensure the given directory exists."""
    path.mkdir(parents=True, exist_ok=True)