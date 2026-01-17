"""
Integration tests for API endpoints
"""
from datetime import datetime, timedelta

import models as db_models
import pytest
from connection import get_db
from fastapi.testclient import TestClient
from main import app


@pytest.fixture
def client(db_session, override_get_db):
    """Create test.csv client with overridden database dependency"""
    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


class TestDatabaseEndpoints:
    """Test database operation endpoints"""
    
    def test_get_all_vms_empty(self, client):
        """Test getting all VMs when empty"""
        response = client.get("/api/v1/vms")
        assert response.status_code == 200
        assert response.json() == []
    
    def test_get_all_vms(self, client, sample_metrics_data):
        """Test getting all VMs"""
        response = client.get("/api/v1/vms")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert "test.csv-vm-01" in data
    
    def test_get_metrics_for_vm(self, client, sample_metrics_data):
        """Test getting metrics for a VM"""
        response = client.get("/api/v1/vms/test.csv-vm-01/metrics")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert "cpu.usage.average" in data
    
    def test_get_data_time_range(self, client, sample_metrics_data):
        """Test getting data time range"""
        response = client.get("/api/v1/vms/test.csv-vm-01/metrics/cpu.usage.average/time-range")
        assert response.status_code == 200
        data = response.json()
        assert "first_timestamp" in data
        assert "last_timestamp" in data
        assert "total_records" in data
    
    def test_get_data_time_range_not_found(self, client):
        """Test getting time range for non-existent data"""
        response = client.get("/api/v1/vms/non-existent/metrics/metric/time-range")
        assert response.status_code == 404
    
    def test_get_database_stats(self, client, sample_metrics_data, sample_predictions_data):
        """Test getting database statistics"""
        response = client.get("/api/v1/stats")
        assert response.status_code == 200
        data = response.json()
        assert "fact_records" in data
        assert "prediction_records" in data
        assert data["fact_records"] == 10
        assert data["prediction_records"] == 5
    
    def test_cleanup_old_data(self, client, db_session, sample_metrics_data):
        """Test cleaning up old data"""
        # Add old data
        old_metric = db_models.ServerMetricsFact(
            vm="test.csv-vm-01",
            timestamp=datetime.now() - timedelta(days=100),
            metric="cpu.usage.average",
            value=50.0
        )
        db_session.add(old_metric)
        db_session.commit()
        
        response = client.post("/api/v1/cleanup", json={"days_to_keep": 90})
        assert response.status_code == 200
        data = response.json()
        assert "fact_records_deleted" in data
    
    def test_get_data_completeness(self, client, sample_metrics_data):
        """Test getting data completeness"""
        start_date = datetime(2025, 1, 27, 0, 0, 0)
        end_date = datetime(2025, 1, 27, 6, 0, 0)
        
        response = client.get(
            f"/api/v1/vms/test.csv-vm-01/metrics/cpu.usage.average/completeness",
            params={
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "expected_interval_minutes": 30
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "completeness_percentage" in data
        assert 0 <= data["completeness_percentage"] <= 100
    
    def test_get_missing_data(self, client, sample_metrics_data):
        """Test getting missing data"""
        start_date = datetime(2025, 1, 27, 0, 0, 0)
        end_date = datetime(2025, 1, 27, 6, 0, 0)
        
        response = client.get(
            f"/api/v1/vms/test.csv-vm-01/metrics/cpu.usage.average/missing-data",
            params={
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "expected_interval_minutes": 30
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)


class TestFactsEndpoints:
    """Test fact metrics endpoints"""
    
    def test_create_metric_fact(self, client):
        """Test creating a metric fact"""
        metric_data = {
            "vm": "test.csv-vm-01",
            "timestamp": "2025-01-27T12:00:00",
            "metric": "cpu.usage.average",
            "value": 45.5
        }
        response = client.post("/api/v1/facts", json=metric_data)
        assert response.status_code == 201
        data = response.json()
        assert data["vm"] == "test.csv-vm-01"
        assert data["value"] == 45.5
        assert "id" in data
    
    def test_create_metric_fact_invalid_value(self, client):
        """Test creating metric fact with invalid value"""
        metric_data = {
            "vm": "test.csv-vm-01",
            "timestamp": "2025-01-27T12:00:00",
            "metric": "cpu.usage.average",
            "value": 150.0  # Invalid: > 100
        }
        response = client.post("/api/v1/facts", json=metric_data)
        assert response.status_code == 422  # Validation error
    
    def test_create_metrics_fact_batch(self, client):
        """Test batch creating metrics"""
        metrics = [
            {
                "vm": "test.csv-vm-01",
                "timestamp": f"2025-01-27T{12+i:02d}:00:00",
                "metric": "cpu.usage.average",
                "value": 40.0 + i
            }
            for i in range(3)
        ]
        response = client.post("/api/v1/facts/batch", json=metrics)
        assert response.status_code == 200
        data = response.json()
        assert data["created"] == 3
        assert data["total"] == 3
    
    def test_get_metrics_fact(self, client, sample_metrics_data):
        """Test getting metrics fact"""
        response = client.get(
            "/api/v1/facts",
            params={
                "vm": "test.csv-vm-01",
                "metric": "cpu.usage.average"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 10
        assert all(m["vm"] == "test.csv-vm-01" for m in data)
    
    def test_get_metrics_fact_with_dates(self, client, sample_metrics_data):
        """Test getting metrics with date filters"""
        start_date = datetime(2025, 1, 27, 0, 0, 0)
        end_date = datetime(2025, 1, 27, 3, 0, 0)
        
        response = client.get(
            "/api/v1/facts",
            params={
                "vm": "test.csv-vm-01",
                "metric": "cpu.usage.average",
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat()
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) > 0
    
    def test_get_latest_metrics_fact(self, client, sample_metrics_data):
        """Test getting latest metrics"""
        response = client.get(
            "/api/v1/facts/latest",
            params={
                "vm": "test.csv-vm-01",
                "metric": "cpu.usage.average",
                "hours": 24
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) > 0
    
    def test_get_metrics_fact_statistics(self, client, sample_metrics_data):
        """Test getting metrics statistics"""
        response = client.get(
            "/api/v1/facts/statistics",
            params={
                "vm": "test.csv-vm-01",
                "metric": "cpu.usage.average"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "count" in data
        assert "avg" in data
        assert "min" in data
        assert "max" in data


class TestPredictionsEndpoints:
    """Test predictions endpoints"""
    
    def test_save_prediction(self, client):
        """Test saving a prediction"""
        prediction_data = {
            "vm": "test.csv-vm-01",
            "timestamp": "2025-01-28T12:00:00",
            "metric": "cpu.usage.average",
            "value_predicted": 48.5,
            "lower_bound": 45.0,
            "upper_bound": 52.0
        }
        response = client.post("/api/v1/predictions", json=prediction_data)
        assert response.status_code == 201
        data = response.json()
        assert data["value_predicted"] == 48.5
        assert "id" in data
    
    def test_save_predictions_batch(self, client):
        """Test batch saving predictions"""
        predictions = [
            {
                "vm": "test.csv-vm-01",
                "timestamp": f"2025-01-28T{12+i:02d}:00:00",
                "metric": "cpu.usage.average",
                "value_predicted": 50.0 + i,
                "lower_bound": 45.0 + i,
                "upper_bound": 55.0 + i
            }
            for i in range(3)
        ]
        response = client.post("/api/v1/predictions/batch", json=predictions)
        assert response.status_code == 200
        data = response.json()
        assert data["created"] == 3
    
    def test_get_predictions(self, client, sample_predictions_data):
        """Test getting predictions"""
        response = client.get(
            "/api/v1/predictions",
            params={
                "vm": "test.csv-vm-01",
                "metric": "cpu.usage.average"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 5
    
    def test_get_future_predictions(self, client, sample_predictions_data):
        """Test getting future predictions"""
        response = client.get(
            "/api/v1/predictions/future",
            params={
                "vm": "test.csv-vm-01",
                "metric": "cpu.usage.average"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 5
        # All should be in the future (check that we got future predictions)
        # Note: sample_predictions_data creates predictions with future timestamps
        assert len(data) == 5
    
    def test_get_actual_vs_predicted(self, client, db_session, sample_vm, sample_metric):
        """Test comparing actual vs predicted"""
        # Create matching actual and predicted data
        base_time = datetime.now() - timedelta(hours=1)
        for i in range(3):
            actual = db_models.ServerMetricsFact(
                vm=sample_vm,
                timestamp=base_time + timedelta(minutes=i * 30),
                metric=sample_metric,
                value=50.0 + i
            )
            db_session.add(actual)
            
            pred = db_models.ServerMetricsPredictions(
                vm=sample_vm,
                timestamp=base_time + timedelta(minutes=i * 30),
                metric=sample_metric,
                value_predicted=51.0 + i,
                lower_bound=48.0 + i,
                upper_bound=54.0 + i
            )
            db_session.add(pred)
        db_session.commit()
        
        response = client.get(
            "/api/v1/predictions/compare",
            params={
                "vm": sample_vm,
                "metric": sample_metric,
                "hours": 2
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3
        assert all("error" in comp for comp in data)
        assert all("relative_error" in comp for comp in data)


class TestLegacyEndpoints:
    """Test legacy endpoints for backward compatibility"""
    
    def test_get_latest_metrics_legacy(self, client, sample_metrics_data):
        """Test legacy latest_metrics endpoint"""
        response = client.get(
            "/api/v1/latest_metrics",
            params={
                "vm": "test.csv-vm-01",
                "metric": "cpu.usage.average"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) > 0
        assert all("timestamp" in item for item in data)
        assert all("value" in item for item in data)
    
    def test_get_metrics_legacy(self, client, sample_metrics_data):
        """Test legacy metrics endpoint"""
        response = client.get(
            "/api/v1/metrics",
            params={
                "vm": "test.csv-vm-01",
                "metric": "cpu.usage.average",
                "days": 1
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) > 0
    
    def test_get_metrics_legacy_with_dates(self, client, sample_metrics_data):
        """Test legacy metrics endpoint with date range"""
        start_date = datetime(2025, 1, 27, 0, 0, 0)
        end_date = datetime(2025, 1, 27, 6, 0, 0)
        
        response = client.get(
            "/api/v1/metrics",
            params={
                "vm": "test.csv-vm-01",
                "metric": "cpu.usage.average",
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat()
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) > 0
    
    def test_get_metrics_legacy_invalid_params(self, client):
        """Test legacy metrics endpoint with invalid parameters"""
        response = client.get(
            "/api/v1/metrics",
            params={
                "vm": "test.csv-vm-01",
                "metric": "cpu.usage.average",
                "days": 1,
                "start_date": "2025-01-27T00:00:00"
            }
        )
        assert response.status_code == 400

