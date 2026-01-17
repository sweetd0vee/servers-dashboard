from datetime import datetime, timedelta

from anomaly_detector import AnomalyDetector


def test_detect_anomalies_length_mismatch():
    detector = AnomalyDetector()
    result = detector.detect_anomalies(
        actual_values=[10.0],
        predicted_values=[10.0, 11.0],
        timestamps=[datetime(2025, 1, 1)],
        metric="cpu.usage.average",
    )
    assert result == []


def test_detect_anomalies_critical_level():
    detector = AnomalyDetector()
    result = detector.detect_anomalies(
        actual_values=[85.0],
        predicted_values=[60.0],
        timestamps=[datetime(2025, 1, 1)],
        metric="cpu.usage.average",
    )
    assert any(item["type"] == "critical_level" for item in result)


def test_detect_anomalies_prediction_error():
    detector = AnomalyDetector()
    result = detector.detect_anomalies(
        actual_values=[10.0],
        predicted_values=[5.0],
        timestamps=[datetime(2025, 1, 1)],
        metric="cpu.usage.average",
    )
    assert any(item["type"] == "prediction_error" for item in result)


def test_detect_anomalies_rate_of_change():
    detector = AnomalyDetector()
    result = detector.detect_anomalies(
        actual_values=[10.0, 40.0],
        predicted_values=[10.0, 40.0],
        timestamps=[datetime(2025, 1, 1), datetime(2025, 1, 1, 0, 30)],
        metric="cpu.usage.average",
    )
    assert any(item["type"] == "rate_of_change" for item in result)


def test_detect_realtime_anomaly_short_history_returns_none():
    detector = AnomalyDetector()
    result = detector.detect_realtime_anomaly(
        current_value=10.0,
        historical_values=[1.0, 2.0, 3.0],
        predicted_value=10.0,
        metric="cpu.usage.average",
    )
    assert result is None


def test_detect_realtime_anomaly_critical():
    detector = AnomalyDetector()
    result = detector.detect_realtime_anomaly(
        current_value=90.0,
        historical_values=[50.0] * 20,
        predicted_value=60.0,
        metric="cpu.usage.average",
    )
    assert result["type"] == "critical_level"


def test_detect_realtime_anomaly_prediction_error():
    detector = AnomalyDetector()
    result = detector.detect_realtime_anomaly(
        current_value=30.0,
        historical_values=[30.0] * 20,
        predicted_value=10.0,
        metric="cpu.usage.average",
    )
    assert result["type"] == "prediction_error"
