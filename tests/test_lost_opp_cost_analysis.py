import pandas as pd
import pytest

from apem.unit_based_model.evaluation.lost_opp_cost_analysis import (
    load_lost_opp_cost_table,
    validate_lost_opp_cost_table,
)


def test_validate_lost_opp_cost_table_rejects_missing_required_columns():
    invalid = pd.DataFrame({"algo": ["ELMP"], "metric": ["glocs"], "value": [1.0]})

    with pytest.raises(ValueError, match="Missing required columns"):
        validate_lost_opp_cost_table(invalid)


def test_load_lost_opp_cost_table_parses_stats_file(tmp_path):
    stats_file = tmp_path / "ELMP_stats.txt"
    stats_file.write_text(
        "\n".join(
            [
                "GLOCs buyers: 1.5",
                "GLOCs sellers: 2.5",
                "GLOCs network: 3.5",
                "Total GLOCs: 7.5",
                "Runtime in seconds: 10",
            ]
        ),
        encoding="utf-8",
    )

    loaded = load_lost_opp_cost_table(stats_file)

    assert set(loaded["lost_opp_cost"]) == {"glocs"}
    assert set(loaded["component"]) == {"buyers", "sellers", "network", "total"}
    assert loaded["algorithm"].unique().tolist() == ["ELMP"]

