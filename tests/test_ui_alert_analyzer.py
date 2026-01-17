from datetime import datetime, timedelta
from pathlib import Path
import sys

import pandas as pd


sys.path.insert(0, str(Path(__file__).parent.parent / "src" / "ui"))

from utils.alert_analyzer import analyze_server_alerts
from utils.alert_rules import ServerStatus


def _build_df(values, metric_name):
    base_time = datetime(2025, 1, 1, 0, 0, 0)
    return pd.DataFrame(
        {
            "timestamp": [base_time + timedelta(minutes=30 * i) for i in range(len(values))],
            metric_name: values,
        }
    )


def test_analyze_server_alerts_overloaded():
    df = _build_df([90.0] * 10, "cpu_usage")
    df["memory_usage"] = [90.0] * 10
    df["network_in_mbps"] = [100.0] * 10

    result = analyze_server_alerts(df, "server-1")
    assert result["status"] == ServerStatus.OVERLOADED
    assert result["alerts"]


def test_analyze_server_alerts_underloaded():
    df = _build_df([5.0] * 10, "cpu_usage")
    df["memory_usage"] = [10.0] * 10
    df["network_in_mbps"] = [1.0] * 10

    result = analyze_server_alerts(df, "server-1")
    assert result["status"] == ServerStatus.UNDERLOADED
    assert result["alerts"]


def test_analyze_server_alerts_normal():
    df = _build_df([50.0] * 10, "cpu_usage")
    df["memory_usage"] = [50.0] * 10
    df["network_in_mbps"] = [100.0] * 10

    result = analyze_server_alerts(df, "server-1")
    assert result["status"] == ServerStatus.NORMAL
