"""
Unit tests for PredsCRUD class
"""
from datetime import datetime, timedelta

import models as db_models
import pytest
from preds_crud import PredsCRUD


class TestPredsCRUD:
    """Test suite for PredsCRUD operations"""
    
    def test_save_prediction(self, db_session, sample_vm, sample_metric):
        """Test saving a prediction"""
        crud = PredsCRUD(db_session)
        timestamp = datetime(2025, 1, 28, 12, 0, 0)
        
        prediction = crud.save_prediction(
            vm=sample_vm,
            metric=sample_metric,
            timestamp=timestamp,
            value=48.5,
            lower_bound=45.0,
            upper_bound=52.0
        )
        
        assert prediction is not None
        assert prediction.vm == sample_vm
        assert prediction.metric == sample_metric
        assert prediction.value_predicted == 48.5
        assert prediction.lower_bound == 45.0
        assert prediction.upper_bound == 52.0
        assert prediction.id is not None
    
    def test_save_prediction_upsert(self, db_session, sample_vm, sample_metric):
        """Test upsert behavior - updating existing prediction"""
        crud = PredsCRUD(db_session)
        timestamp = datetime(2025, 1, 28, 12, 0, 0)
        
        # Create first time
        first = crud.save_prediction(
            vm=sample_vm,
            metric=sample_metric,
            timestamp=timestamp,
            value=48.5,
            lower_bound=45.0,
            upper_bound=52.0
        )
        first_id = first.id
        
        # Update with new value
        second = crud.save_prediction(
            vm=sample_vm,
            metric=sample_metric,
            timestamp=timestamp,
            value=50.0,
            lower_bound=47.0,
            upper_bound=53.0
        )
        
        # Should be same record (upsert)
        assert second.id == first_id
        assert second.value_predicted == 50.0
    
    def test_save_predictions_batch(self, db_session, sample_vm, sample_metric):
        """Test batch saving predictions"""
        crud = PredsCRUD(db_session)
        base_time = datetime(2025, 1, 28, 0, 0, 0)
        
        predictions = []
        for i in range(5):
            predictions.append({
                'vm': sample_vm,
                'metric': sample_metric,
                'timestamp': base_time + timedelta(minutes=i * 30),
                'value': 50.0 + i,
                'lower': 45.0 + i,
                'upper': 55.0 + i
            })
        
        count = crud.save_predictions_batch(predictions)
        assert count == 5
        
        # Verify all were saved
        all_predictions = db_session.query(db_models.ServerMetricsPredictions).all()
        assert len(all_predictions) == 5
    
    def test_get_predictions(self, db_session, sample_predictions_data):
        """Test getting predictions"""
        crud = PredsCRUD(db_session)
        start_date = datetime(2025, 1, 28, 0, 0, 0)
        end_date = datetime(2025, 1, 28, 3, 0, 0)
        
        predictions = crud.get_predictions(
            "test.csv-vm-01",
            "cpu.usage.average",
            start_date,
            end_date
        )
        
        assert len(predictions) > 0
        assert all(p.vm == "test.csv-vm-01" for p in predictions)
        assert all(p.metric == "cpu.usage.average" for p in predictions)
        # Verify they're sorted by timestamp
        timestamps = [p.timestamp for p in predictions]
        assert timestamps == sorted(timestamps)
    
    def test_get_predictions_no_dates(self, db_session, sample_predictions_data):
        """Test getting predictions without date filters"""
        crud = PredsCRUD(db_session)
        predictions = crud.get_predictions(
            "test.csv-vm-01",
            "cpu.usage.average"
        )
        
        assert len(predictions) == 5
    
    def test_get_future_predictions(self, db_session, sample_predictions_data):
        """Test getting future predictions"""
        crud = PredsCRUD(db_session)
        
        # Add a past prediction
        past_pred = db_models.ServerMetricsPredictions(
            vm="test.csv-vm-01",
            timestamp=datetime.now() - timedelta(days=1),
            metric="cpu.usage.average",
            value_predicted=45.0
        )
        db_session.add(past_pred)
        db_session.commit()
        
        future_predictions = crud.get_future_predictions(
            "test.csv-vm-01",
            "cpu.usage.average"
        )
        
        # Should only return future predictions
        assert len(future_predictions) == 5
        assert all(p.timestamp > datetime.now() for p in future_predictions)
    
    def test_get_actual_vs_predicted(self, db_session, sample_vm, sample_metric):
        """Test comparing actual vs predicted values"""
        crud = PredsCRUD(db_session)
        
        # Create actual metrics
        base_time = datetime.now() - timedelta(hours=2)
        for i in range(5):
            actual = db_models.ServerMetricsFact(
                vm=sample_vm,
                timestamp=base_time + timedelta(minutes=i * 30),
                metric=sample_metric,
                value=50.0 + i
            )
            db_session.add(actual)
        
        # Create matching predictions
        for i in range(5):
            pred = db_models.ServerMetricsPredictions(
                vm=sample_vm,
                timestamp=base_time + timedelta(minutes=i * 30),
                metric=sample_metric,
                value_predicted=51.0 + i,  # Slightly different
                lower_bound=48.0 + i,
                upper_bound=54.0 + i
            )
            db_session.add(pred)
        
        db_session.commit()
        
        # Get comparison
        comparison = crud.get_actual_vs_predicted(sample_vm, sample_metric, hours=3)
        
        assert len(comparison) == 5
        assert all("timestamp" in comp for comp in comparison)
        assert all("actual_value" in comp for comp in comparison)
        assert all("predicted_value" in comp for comp in comparison)
        assert all("error" in comp for comp in comparison)
        assert all("relative_error" in comp for comp in comparison)
        
        # Verify error calculation
        for comp in comparison:
            expected_error = abs(comp["actual_value"] - comp["predicted_value"])
            assert comp["error"] == expected_error
    
    def test_get_actual_vs_predicted_no_matches(self, db_session, sample_vm, sample_metric):
        """Test comparison when no matching timestamps"""
        crud = PredsCRUD(db_session)
        
        # Create actual metric
        actual = db_models.ServerMetricsFact(
            vm=sample_vm,
            timestamp=datetime.now() - timedelta(hours=1),
            metric=sample_metric,
            value=50.0
        )
        db_session.add(actual)
        
        # Create prediction at different time
        pred = db_models.ServerMetricsPredictions(
            vm=sample_vm,
            timestamp=datetime.now() + timedelta(hours=1),
            metric=sample_metric,
            value_predicted=55.0
        )
        db_session.add(pred)
        db_session.commit()
        
        comparison = crud.get_actual_vs_predicted(sample_vm, sample_metric, hours=2)
        
        # Should be empty since timestamps don't match
        assert len(comparison) == 0

