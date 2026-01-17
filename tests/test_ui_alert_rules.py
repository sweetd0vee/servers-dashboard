from datetime import datetime, timedelta
from pathlib import Path
import sys

import pandas as pd


sys.path.insert(0, str(Path(__file__).parent.parent / "src" / "ui"))

from utils.alert_rules import AlertSystem, ServerStatus


def _build_df(values, metric_name):
    base_time = datetime(2025, 1, 1, 0, 0, 0)
    return pd.DataFrame(
        {
            "timestamp": [base_time + timedelta(minutes=30 * i) for i in range(len(values))],
            metric_name: values,
        }
    )


def test_analyze_server_status_empty_returns_unknown():
    system = AlertSystem()
    result = system.analyze_server_status(pd.DataFrame(), "server-1")
    assert result["status"] == ServerStatus.UNKNOWN
    assert result["alerts"] == []


def test_analyze_server_status_underloaded():
    system = AlertSystem()
    df = _build_df([5.0] * 10, "cpu.usage.average")
    df["mem.usage.average"] = [10.0] * 10
    df["net.usage.average"] = [1.0] * 10

    result = system.analyze_server_status(df, "server-1")
    assert result["status"] == ServerStatus.UNDERLOADED


def test_analyze_server_status_overloaded():
    system = AlertSystem()
    df = _build_df([90.0] * 10, "cpu.usage.average")
    df["mem.usage.average"] = [90.0] * 10
    df["net.usage.average"] = [1.0] * 10

    result = system.analyze_server_status(df, "server-1")
    assert result["status"] == ServerStatus.OVERLOADED
