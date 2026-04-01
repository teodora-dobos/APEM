import pandas as pd
import pytest

from apem.unit_based_model.evaluation.price_analysis import (
    compare_price_algorithms,
    summarize_prices,
    validate_price_table,
)


@pytest.fixture
def sample_price_data():
    return pd.DataFrame(
        {
            "algorithm": ["ELMP", "ELMP", "ELMP", "IP", "IP", "IP"],
            "scenario": ["s1", "s1", "s1", "s1", "s1", "s1"],
            "period": [1, 2, 3, 1, 2, 3],
            "node": ["n1", "n1", "n1", "n1", "n1", "n1"],
            "price": [10.0, 12.0, -2.0, 11.0, 9.0, 1.0],
        }
    )


def test_summarize_prices_returns_expected_statistics(sample_price_data):
    summary = summarize_prices(sample_price_data, group_by=["algorithm"])

    elmp = summary.loc[summary["algorithm"] == "ELMP"].iloc[0]
    ip = summary.loc[summary["algorithm"] == "IP"].iloc[0]

    assert elmp["count"] == 3
    assert elmp["negative_price_count"] == 1
    assert elmp["mean"] == pytest.approx((10.0 + 12.0 - 2.0) / 3.0)
    assert elmp["spread"] == pytest.approx(14.0)

    assert ip["count"] == 3
    assert ip["negative_price_count"] == 0
    assert ip["variance"] == pytest.approx(28.0)


def test_compare_price_algorithms_aligns_rows_and_reports_pairwise_metrics(sample_price_data):
    comparisons = compare_price_algorithms(sample_price_data, align_on=["scenario", "period", "node"])

    row = comparisons.iloc[0]
    expected_differences = pd.Series([-1.0, 3.0, -3.0])

    assert row["algorithm_left"] == "ELMP"
    assert row["algorithm_right"] == "IP"
    assert row["shared_observations"] == 3
    assert row["mean_difference"] == pytest.approx(expected_differences.mean())
    assert row["mean_absolute_difference"] == pytest.approx(expected_differences.abs().mean())
    assert row["max_absolute_difference"] == pytest.approx(expected_differences.abs().max())


def test_validate_price_table_rejects_missing_required_columns():
    invalid = pd.DataFrame({"algo": ["ELMP"], "value": [1.0]})

    with pytest.raises(ValueError, match="Missing required columns"):
        validate_price_table(invalid)

