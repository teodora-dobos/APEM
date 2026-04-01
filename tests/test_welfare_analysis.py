import pandas as pd
import pytest

from apem.unit_based_model.evaluation.welfare_analysis import (
    load_welfare_table,
    validate_welfare_table,
)


def test_validate_welfare_table_rejects_missing_required_columns():
    invalid = pd.DataFrame({"model": ["DCOPF"], "period": [1], "welfare": [1.0]})

    with pytest.raises(ValueError, match="Missing required columns"):
        validate_welfare_table(invalid)


def test_load_welfare_table_parses_stats_file(tmp_path):
    stats_file = tmp_path / "DCOPF_stats.txt"
    stats_file.write_text(
        "\n".join(
            [
                "Welfare period 1: 10.5",
                "Welfare period 2: 12.5",
                "",
                "Total welfare: 23.0",
            ]
        ),
        encoding="utf-8",
    )

    loaded = load_welfare_table(stats_file)

    assert set(loaded["welfare_scope"]) == {"period", "total"}
    assert loaded["power_flow_model"].unique().tolist() == ["DCOPF"]
    assert loaded.loc[loaded["welfare_scope"] == "period", "period"].astype(int).tolist() == [1, 2]

