"""
Unit tests for FactsCRUD class
"""
from datetime import datetime, timedelta

from facts_crud import FactsCRUD
import models as db_models
import pytest
import schemas as pydantic_models


class TestFactsCRUD:
    """Test suite for FactsCRUD operations"""
    
    def test_create_metric_fact(self, db_session, sample_metric_fact):
        """Test creating a metric fact"""
        crud = FactsCRUD(db_session)
        result = crud.create_metric_fact(sample_metric_fact)
        
        assert result is not None
        assert result.vm == sample_metric_fact.vm
        assert result.metric == sample_metric_fact.metric
        assert result.value == sample_metric_fact.value
        assert result.id is not None
    
    def test_create_metric_fact_upsert(self, db_session, sample_metric_fact):
        """Test upsert behavior - updating existing metric"""
        crud = FactsCRUD(db_session)
        
        # Create first time
        first = crud.create_metric_fact(sample_metric_fact)
        first_id = first.id
        first_value = first.value
        
        # Update with new value
        updated_metric = pydantic_models.MetricFact(
            vm=sample_metric_fact.vm,
            timestamp=sample_metric_fact.timestamp,
            metric=sample_metric_fact.metric,
            value=99.9,
            created_at=sample_metric_fact.created_at
        )
        second = crud.create_metric_fact(updated_metric)
        
        # Should be same record (upsert)
        assert second.id == first_id
        assert second.value == 99.9
        assert second.value != first_value
    
    def test_create_metrics_fact_batch(self, db_session, sample_vm, sample_metric):
        """Test batch creating metrics"""
        crud = FactsCRUD(db_session)
        
        metrics = []
        base_time = datetime(2025, 1, 27, 0, 0, 0)
        for i in range(5):
            metric = pydantic_models.MetricFact(
                vm=sample_vm,
                timestamp=base_time + timedelta(minutes=i * 30),
                metric=sample_metric,
                value=40.0 + i,
                created_at=base_time
            )
            metrics.append(metric)
        
        count = crud.create_metrics_fact_batch(metrics)
        assert count == 5
        
        # Verify all were created
        all_metrics = db_session.query(db_models.ServerMetricsFact).all()
        assert len(all_metrics) == 5
    
    def test_get_metrics_fact(self, db_session, sample_metrics_data):
        """Test getting metrics fact"""
        crud = FactsCRUD(db_session)
        start_date = datetime(2025, 1, 27, 0, 0, 0)
        end_date = datetime(2025, 1, 27, 5, 0, 0)
        
        metrics = crud.get_metrics_fact(
            "test.csv-vm-01",
            "cpu.usage.average",
            start_date,
            end_date
        )
        
        assert len(metrics) > 0
        assert all(m.vm == "test.csv-vm-01" for m in metrics)
        assert all(m.metric == "cpu.usage.average" for m in metrics)
    
    def test_get_metrics_fact_with_limit(self, db_session, sample_metrics_data):
        """Test getting metrics with limit"""
        crud = FactsCRUD(db_session)
        metrics = crud.get_metrics_fact(
            "test.csv-vm-01",
            "cpu.usage.average",
            limit=3
        )
        
        assert len(metrics) == 3
    
    def test_get_latest_metrics(self, db_session, sample_metrics_data):
        """Test getting latest metrics"""
        crud = FactsCRUD(db_session)
        metrics = crud.get_latest_metrics("test.csv-vm-01", "cpu.usage.average", hours=24)
        
        assert len(metrics) > 0
        # Verify they're sorted by timestamp
        timestamps = [m.timestamp for m in metrics]
        assert timestamps == sorted(timestamps)
    
    def test_get_metrics_as_dataframe(self, db_session, sample_metrics_data):
        """Test getting metrics in Prophet format"""
        crud = FactsCRUD(db_session)
        start_date = datetime(2025, 1, 27, 0, 0, 0)
        end_date = datetime(2025, 1, 27, 6, 0, 0)
        
        data = crud.get_metrics_as_dataframe(
            "test.csv-vm-01",
            "cpu.usage.average",
            start_date,
            end_date
        )
        
        assert data is not None
        assert "ds" in data
        assert "y" in data
        assert len(data["ds"]) == len(data["y"])
        assert len(data["ds"]) > 0
    
    def test_get_metrics_as_dataframe_empty(self, db_session):
        """Test getting metrics dataframe when no data exists"""
        crud = FactsCRUD(db_session)
        start_date = datetime(2025, 1, 27, 0, 0, 0)
        end_date = datetime(2025, 1, 27, 6, 0, 0)
        
        data = crud.get_metrics_as_dataframe(
            "non-existent",
            "metric",
            start_date,
            end_date
        )
        
        assert data is None
    
    def test_get_metrics_fact_statistics(self, db_session, sample_metrics_data):
        """Test getting metrics statistics"""
        crud = FactsCRUD(db_session)
        stats = crud.get_metrics_fact_statistics(
            "test.csv-vm-01",
            "cpu.usage.average"
        )
        
        assert stats is not None
        assert "count" in stats
        assert "min" in stats
        assert "max" in stats
        assert "avg" in stats
        assert "stddev" in stats
        assert stats["count"] == 10
        assert stats["min"] >= 0
        assert stats["max"] <= 100
    
    def test_get_metrics_fact_statistics_with_dates(self, db_session, sample_metrics_data):
        """Test getting statistics with date range"""
        crud = FactsCRUD(db_session)
        start_date = datetime(2025, 1, 27, 0, 0, 0)
        end_date = datetime(2025, 1, 27, 3, 0, 0)
        
        stats = crud.get_metrics_fact_statistics(
            "test.csv-vm-01",
            "cpu.usage.average",
            start_date,
            end_date
        )
        
        assert stats is not None
        assert stats["count"] > 0
        assert stats["period"]["start"] == start_date.isoformat()
        assert stats["period"]["end"] == end_date.isoformat()
    
    def test_get_metrics_fact_statistics_empty(self, db_session):
        """Test getting statistics when no data exists"""
        crud = FactsCRUD(db_session)
        stats = crud.get_metrics_fact_statistics(
            "non-existent",
            "metric"
        )
        
        assert stats is not None
        assert stats["count"] == 0
        assert stats["min"] == 0.0
        assert stats["max"] == 0.0
        assert stats["avg"] == 0.0

