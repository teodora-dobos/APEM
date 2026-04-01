from apem.order_book_based_model.euphemia.utils.paths import DATA_DIR

"""
Convert an raw GME block data CSV to the EUPHEMIA format

- id is a sequential integer (1, 2, 3 ...)
- block_type is always "normal"
- code_prm is left empty
- p is copied from the source row
- q is written into the correct q1-q24 column based on Intervallo
- MAR is fixed to 1
"""

from pathlib import Path
import pandas as pd

SOURCE_PATH = DATA_DIR / "gme" / "raw_data" / "block_offers_original_format.csv"
OUTPUT_FILE    = DATA_DIR / "gme" / "block_orders.csv"


def convert(offerte_path: Path) -> pd.DataFrame:
    """Transform the Offerte a blocchi file into block-orders format."""
    offerte = pd.read_csv(offerte_path)

    # Define block-orders header explicitly
    header = (
        ["id", "block_type", "code_prm", "p"]
        + [f"q{i}" for i in range(1, 25)]
        + ["MAR"]
    )

    rows = []
    for idx, src in offerte.iterrows():   # idx starts at 0
        row = dict.fromkeys(header, "")   # pre-fill blanks

        row["id"] = idx + 1
        row["block_type"] = "normal"
        row["code_prm"] = ""
        row["p"] = src["p"]

        period = int(src["Intervallo"])
        if not (1 <= period <= 24):
            raise ValueError(f"Intervallo {period} is outside 1-24.")
        for i in range(1,25):
            if i == period:
                row[f"q{period}"] = src["q"]
            else:
                row[f"q{i}"] = 0

        row["MAR"] = 1
        rows.append(row)

    return pd.DataFrame(rows, columns=header)


def main() -> None:
    """Convert source GME block offers and write ``block_orders.csv``."""

    print("Reading:", SOURCE_PATH)
    df = convert(SOURCE_PATH)

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT_FILE, index=False)

    print(f"Saved {len(df)} rows to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
