import pandas as pd
import pytest

from apem.US_market_model.evaluation.redispatch_analysis import (
    load_redispatch_metric_file,
    validate_redispatch_table,
)


def test_validate_redispatch_table_rejects_missing_required_columns():
    invalid = pd.DataFrame({"algo": ["MinCostRD"], "metric": ["costs"]})

    with pytest.raises(ValueError, match="Missing required columns"):
        validate_redispatch_table(invalid)


def test_load_redispatch_metric_file_parses_metric_file(tmp_path):
    metric_file = tmp_path / "MinCostRD_False_0_redispatch_costs.csv"
    metric_file.write_text("Redispatch costs: 15.5", encoding="utf-8")

    loaded = load_redispatch_metric_file(metric_file)

    assert loaded["redispatch_algorithm"].unique().tolist() == ["MinCostRD"]
    assert loaded["metric"].unique().tolist() == ["costs"]
    assert loaded["value"].tolist() == [15.5]
