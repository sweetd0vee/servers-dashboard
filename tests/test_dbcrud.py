"""
Unit tests for DBCRUD class
"""
from datetime import datetime, timedelta

from dbcrud import DBCRUD
import models as db_models
import pytest


class TestDBCRUD:
    """Test suite for DBCRUD operations"""
    
    def test_get_all_vms_empty(self, db_session):
        """Test getting all VMs when database is empty"""
        crud = DBCRUD(db_session)
        vms = crud.get_all_vms()
        assert vms == []
    
    def test_get_all_vms(self, db_session, sample_metrics_data):
        """Test getting all VMs"""
        crud = DBCRUD(db_session)
        vms = crud.get_all_vms()
        assert len(vms) == 1
        assert "test.csv-vm-01" in vms
    
    def test_get_metrics_for_vm(self, db_session, sample_metrics_data):
        """Test getting metrics for a specific VM"""
        crud = DBCRUD(db_session)
        metrics = crud.get_metrics_for_vm("test.csv-vm-01")
        assert len(metrics) == 1
        assert "cpu.usage.average" in metrics
    
    def test_get_metrics_for_vm_not_found(self, db_session):
        """Test getting metrics for non-existent VM"""
        crud = DBCRUD(db_session)
        metrics = crud.get_metrics_for_vm("non-existent-vm")
        assert metrics == []
    
    def test_get_data_time_range(self, db_session, sample_metrics_data):
        """Test getting data time range"""
        crud = DBCRUD(db_session)
        time_range = crud.get_data_time_range("test.csv-vm-01", "cpu.usage.average")
        
        assert time_range is not None
        assert "first_timestamp" in time_range
        assert "last_timestamp" in time_range
        assert "total_hours" in time_range
        assert "total_records" in time_range
        assert time_range["total_records"] == 10
    
    def test_get_data_time_range_not_found(self, db_session):
        """Test getting time range for non-existent data"""
        crud = DBCRUD(db_session)
        time_range = crud.get_data_time_range("non-existent", "metric")
        assert time_range == {}
    
    def test_get_historical_metrics(self, db_session, sample_metrics_data):
        """Test getting historical metrics"""
        crud = DBCRUD(db_session)
        start_date = datetime(2025, 1, 27, 0, 0, 0)
        end_date = datetime(2025, 1, 27, 5, 0, 0)
        
        metrics = crud.get_historical_metrics(
            "test.csv-vm-01",
            "cpu.usage.average",
            start_date,
            end_date
        )
        
        assert len(metrics) > 0
        assert all(m.vm == "test.csv-vm-01" for m in metrics)
        assert all(m.metric == "cpu.usage.average" for m in metrics)
    
    def test_get_historical_metrics_with_limit(self, db_session, sample_metrics_data):
        """Test getting historical metrics with limit"""
        crud = DBCRUD(db_session)
        metrics = crud.get_historical_metrics(
            "test.csv-vm-01",
            "cpu.usage.average",
            limit=5
        )
        
        assert len(metrics) == 5
    
    def test_get_latest_metrics(self, db_session, sample_metrics_data):
        """Test getting latest metrics"""
        crud = DBCRUD(db_session)
        metrics = crud.get_latest_metrics("test.csv-vm-01", "cpu.usage.average", hours=24)
        
        assert len(metrics) > 0
        # All metrics should be within last 24 hours
        cutoff = datetime.now() - timedelta(hours=24)
        assert all(m.timestamp >= cutoff for m in metrics)
    
    def test_get_metrics_by_date_range(self, db_session, sample_metrics_data):
        """Test getting metrics by date range"""
        crud = DBCRUD(db_session)
        start_date = datetime(2025, 1, 27, 1, 0, 0)
        end_date = datetime(2025, 1, 27, 3, 0, 0)
        
        metrics = crud.get_metrics_by_date_range(
            "test.csv-vm-01",
            "cpu.usage.average",
            start_date,
            end_date
        )
        
        assert len(metrics) > 0
        assert all(start_date <= m.timestamp <= end_date for m in metrics)
    
    def test_get_database_stats(self, db_session, sample_metrics_data, sample_predictions_data):
        """Test getting database statistics"""
        crud = DBCRUD(db_session)
        stats = crud.get_database_stats()
        
        assert stats is not None
        assert "fact_records" in stats
        assert "prediction_records" in stats
        assert "total_records" in stats
        assert "unique_vms" in stats
        assert "unique_metrics" in stats
        assert stats["fact_records"] == 10
        assert stats["prediction_records"] == 5
        assert stats["unique_vms"] == 1
    
    def test_cleanup_old_data(self, db_session, sample_metrics_data):
        """Test cleaning up old data"""
        crud = DBCRUD(db_session)
        
        # Add old data
        old_timestamp = datetime.now() - timedelta(days=100)
        old_metric = db_models.ServerMetricsFact(
            vm="test.csv-vm-01",
            timestamp=old_timestamp,
            metric="cpu.usage.average",
            value=50.0
        )
        db_session.add(old_metric)
        db_session.commit()
        
        # Cleanup data older than 90 days
        result = crud.cleanup_old_data(days_to_keep=90)
        
        assert result is not None
        assert "fact_records_deleted" in result
        assert result["fact_records_deleted"] >= 0
        
        # Verify old data is deleted
        remaining = db_session.query(db_models.ServerMetricsFact).count()
        assert remaining <= 10  # Should have only recent data
    
    def test_detect_missing_data(self, db_session, sample_metrics_data):
        """Test detecting missing data"""
        crud = DBCRUD(db_session)
        start_date = datetime(2025, 1, 27, 0, 0, 0)
        end_date = datetime(2025, 1, 27, 6, 0, 0)
        
        missing = crud.detect_missing_data(
            "test.csv-vm-01",
            "cpu.usage.average",
            start_date,
            end_date,
            expected_interval_minutes=30
        )
        
        # Should detect some missing intervals if data is sparse
        assert isinstance(missing, list)
    
    def test_calculate_data_completeness(self, db_session, sample_metrics_data):
        """Test calculating data completeness"""
        crud = DBCRUD(db_session)
        start_date = datetime(2025, 1, 27, 0, 0, 0)
        end_date = datetime(2025, 1, 27, 6, 0, 0)
        
        completeness = crud.calculate_data_completeness(
            "test.csv-vm-01",
            "cpu.usage.average",
            start_date,
            end_date,
            expected_interval_minutes=30
        )
        
        assert completeness is not None
        assert "expected_points" in completeness
        assert "actual_points" in completeness
        assert "completeness_percentage" in completeness
        assert 0 <= completeness["completeness_percentage"] <= 100
        assert completeness["actual_points"] == 10

