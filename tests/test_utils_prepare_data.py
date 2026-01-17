from datetime import datetime, timedelta
from pathlib import Path
import sys

import pandas as pd


sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.prepare_data import DATA


def test_analyze_data_returns_expected_summary():
    data = DATA()
    df = pd.DataFrame(
        {
            "vm": ["vm-1", "vm-2"],
            "metric": ["cpu.usage.average", "mem.usage.average"],
            "timestamp": [datetime(2025, 1, 1), datetime(2025, 1, 2)],
            "value": [10.0, 20.0],
        }
    )

    result = data.analyze_data(df)
    assert result["total_rows"] == 2
    assert result["unique_vms"] == 2
    assert result["unique_metrics"] == 2
    assert result["time_range"]["start"] == datetime(2025, 1, 1)
    assert result["time_range"]["end"] == datetime(2025, 1, 2)


def test_analyze_data_empty_returns_empty_dict():
    data = DATA()
    result = data.analyze_data(pd.DataFrame())
    assert result == {}
