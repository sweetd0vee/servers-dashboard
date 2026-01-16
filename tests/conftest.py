"""
Pytest configuration and fixtures
"""
import pytest
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from datetime import datetime, timedelta
import sys
from pathlib import Path

# Add src/app to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src" / "app"))

from connection import Base, get_db
import models as db_models
import schemas as pydantic_models


# Test database URL (SQLite in-memory for testing)
TEST_DATABASE_URL = "sqlite:///:memory:"

# Create test.csv engine
test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(scope="function")
def db_session():
    """
    Create a fresh database session for each test.csv.
    Creates tables, yields session, then drops tables.
    """
    # Create tables
    Base.metadata.create_all(bind=test_engine)
    
    # Create session
    session = TestSessionLocal()
    
    try:
        yield session
    finally:
        session.close()
        # Drop tables
        Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def override_get_db(db_session):
    """
    Override the get_db dependency to use test.csv database
    """
    def _get_db():
        try:
            yield db_session
        finally:
            pass
    return _get_db


@pytest.fixture
def sample_vm():
    """Sample VM name for testing"""
    return "test.csv-vm-01"


@pytest.fixture
def sample_metric():
    """Sample metric name for testing"""
    return "cpu.usage.average"


@pytest.fixture
def sample_timestamp():
    """Sample timestamp for testing"""
    return datetime(2025, 1, 27, 12, 0, 0)


@pytest.fixture
def sample_metric_fact(sample_vm, sample_metric, sample_timestamp):
    """Sample metric fact data"""
    return pydantic_models.MetricFact(
        vm=sample_vm,
        timestamp=sample_timestamp,
        metric=sample_metric,
        value=45.5,
        created_at=sample_timestamp
    )


@pytest.fixture
def sample_metric_fact_create(sample_vm, sample_metric, sample_timestamp):
    """Sample metric fact create data"""
    return pydantic_models.MetricFactCreate(
        vm=sample_vm,
        timestamp=sample_timestamp,
        metric=sample_metric,
        value=45.5
    )


@pytest.fixture
def sample_prediction_create(sample_vm, sample_metric, sample_timestamp):
    """Sample prediction create data"""
    future_timestamp = sample_timestamp + timedelta(hours=1)
    return pydantic_models.MetricPredictionCreate(
        vm=sample_vm,
        timestamp=future_timestamp,
        metric=sample_metric,
        value_predicted=48.5,
        lower_bound=45.0,
        upper_bound=52.0
    )


@pytest.fixture
def sample_metrics_data(db_session, sample_vm, sample_metric):
    """
    Create sample metrics data in database for testing
    Returns list of created metric records
    """
    metrics = []
    base_time = datetime(2025, 1, 27, 0, 0, 0)
    
    for i in range(10):
        timestamp = base_time + timedelta(minutes=i * 30)
        metric = db_models.ServerMetricsFact(
            vm=sample_vm,
            timestamp=timestamp,
            metric=sample_metric,
            value=40.0 + (i * 2.0)  # Values from 40 to 58
        )
        db_session.add(metric)
        metrics.append(metric)
    
    db_session.commit()
    
    # Refresh all metrics
    for metric in metrics:
        db_session.refresh(metric)
    
    return metrics


@pytest.fixture
def sample_predictions_data(db_session, sample_vm, sample_metric):
    """
    Create sample predictions data in database for testing
    """
    predictions = []
    base_time = datetime(2025, 1, 28, 0, 0, 0)  # Future date
    
    for i in range(5):
        timestamp = base_time + timedelta(minutes=i * 30)
        prediction = db_models.ServerMetricsPredictions(
            vm=sample_vm,
            timestamp=timestamp,
            metric=sample_metric,
            value_predicted=50.0 + (i * 1.0),
            lower_bound=45.0 + (i * 1.0),
            upper_bound=55.0 + (i * 1.0)
        )
        db_session.add(prediction)
        predictions.append(prediction)
    
    db_session.commit()
    
    for pred in predictions:
        db_session.refresh(pred)
    
    return predictions

