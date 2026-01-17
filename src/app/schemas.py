from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class MetricType(str, Enum):
    CPU_USAGE = "cpu.usage.average"
    CPU_SUMMATION = "cpu.ready.summation"
    MEMORY_USAGE = "memory.usage.average"
    DISK_USAGE = "disk.usage.average"
    NETWORK_IO = "net.usage.average"


class LoadLevel(str, Enum):
    IDLE = "idle"
    NORMAL = "normal"
    HIGH = "high"


class MetricFactCreate(BaseModel):
    """Schema for creating a metric fact (without created_at)"""
    vm: str
    timestamp: datetime
    metric: str
    value: float = Field(..., ge=0, le=100)


class MetricFact(BaseModel):
    """Schema for metric fact response"""
    id: Optional[str] = None
    vm: str
    timestamp: datetime
    metric: str
    value: float
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class MetricPredictionCreate(BaseModel):
    """Schema for creating a prediction"""
    vm: str
    timestamp: datetime
    metric: str
    value_predicted: float = Field(..., ge=0, le=100)
    lower_bound: Optional[float] = None
    upper_bound: Optional[float] = None


class MetricPrediction(BaseModel):
    """Schema for prediction response"""
    id: str
    vm: str
    timestamp: datetime
    metric: str
    value_predicted: float
    lower_bound: Optional[float] = None
    upper_bound: Optional[float] = None
    created_at: datetime

    class Config:
        from_attributes = True


class PredictionRequest(BaseModel):
    vm: str
    metric: str
    periods: int = Field(48, ge=1, le=168)  # 1-168 периодов (до 7 дней) # 336 периодов (до 14 дней, за 2 недели)
    frequency: str = "30min"  # 30min, 1h, 4h, 1d


# class PredictionResponse(BaseModel):
#     vm: str
#     metric: str
#     predictions: List[dict]
#     model_accuracy: Optional[float] # чем заполняется это поле
#     created_at: datetime


# Сделать класс алертов по метрикам переданным
class AnomalyAlert(BaseModel):
    vm: str
    timestamp: datetime
    metric: str
    actual_value: float
    predicted_value: float
    anomaly_score: float
    load: LoadLevel
    message: str


class TrainingRequest(BaseModel):
    vm: str
    metric: str
    days_of_history: int = 14 # здесь поправить на число дней истории
    retrain: bool = False


# class TrainingResponse(BaseModel):
#     vm: str
#     metric: str
#     model_id: str
#     accuracy: float
#     training_time: float
#     status: str


class HealthCheck(BaseModel):
    status: str
    database: bool
    models_loaded: int
    uptime: float


class BatchCreateResponse(BaseModel):
    """Response for batch create operations"""
    created: int
    failed: int
    total: int


class DatabaseStatsResponse(BaseModel):
    """Response for database statistics"""
    fact_records: int
    prediction_records: int
    total_records: int
    unique_vms: int
    unique_metrics: int
    data_volume_mb: float
    oldest_record: Optional[datetime] = None
    newest_record: Optional[datetime] = None
    collection_period_days: int


class DataCompletenessResponse(BaseModel):
    """Response for data completeness analysis"""
    expected_points: int
    actual_points: int
    completeness_percentage: float
    missing_points: int
    missing_intervals: List[dict]
    missing_intervals_count: int


class TimeRangeResponse(BaseModel):
    """Response for time range queries"""
    first_timestamp: datetime
    last_timestamp: datetime
    total_hours: float
    total_records: int


class ActualVsPredictedResponse(BaseModel):
    """Response for actual vs predicted comparison"""
    timestamp: datetime
    actual_value: float
    predicted_value: float
    error: float
    relative_error: float
    lower_bound: Optional[float] = None
    upper_bound: Optional[float] = None
