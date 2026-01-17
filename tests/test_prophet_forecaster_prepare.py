from datetime import datetime, timedelta

import pandas as pd

from prophet_forecaster import ProphetForecaster


def test_prepare_data_empty_raises():
    forecaster = ProphetForecaster(model_storage_path="./.tmp_models", enable_optimization=False)
    try:
        forecaster.prepare_data([])
        assert False, "Expected ValueError for empty input"
    except ValueError:
        assert True


def test_prepare_data_adds_features_and_sorts(tmp_path):
    forecaster = ProphetForecaster(model_storage_path=tmp_path.as_posix(), enable_optimization=False)
    data = [
        {"timestamp": datetime(2025, 1, 2, 1, 0), "value": 10.0},
        {"timestamp": datetime(2025, 1, 1, 1, 0), "value": None},
        {"timestamp": datetime(2025, 1, 3, 1, 0), "value": 20.0},
    ]

    df = forecaster.prepare_data(data)

    assert list(df.columns[:2]) == ["ds", "y"]
    assert df["ds"].is_monotonic_increasing
    assert df["y"].isna().sum() == 0

    for col in ["hour", "is_work_hours", "is_night", "day_of_week", "is_weekend"]:
        assert col in df.columns

    assert df["ds"].dt.tz is None
