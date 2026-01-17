from pathlib import Path
import sys

import pandas as pd


sys.path.insert(0, str(Path(__file__).parent.parent / "src" / "ui"))

from utils import data_loader


def test_generate_server_data_returns_expected_columns(monkeypatch):
    monkeypatch.setattr(data_loader, "SessionLocal", None)
    df = data_loader.generate_server_data()

    expected_cols = {
        "server",
        "timestamp",
        "load_percentage",
        "cpu.usage.average",
        "mem.usage.average",
        "net.usage.average",
        "cpu.ready.summation",
        "disk.usage.average",
        "errors",
        "server_type",
        "weekday",
        "hour_of_day",
        "is_business_hours",
        "is_weekend",
        "load_ma_6h",
        "load_ma_24h",
    }

    assert isinstance(df, pd.DataFrame)
    assert expected_cols.issubset(set(df.columns))


def test_load_server_data_from_db_returns_empty_when_no_db(monkeypatch):
    monkeypatch.setattr(data_loader, "SessionLocal", None)
    df = data_loader.load_server_data_from_db()
    assert df.empty
