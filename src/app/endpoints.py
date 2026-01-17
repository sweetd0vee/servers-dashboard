"""
API Endpoints for AIOps Dashboard

This module provides RESTful API endpoints for:
- Database operations (VMs, metrics, statistics)
- Fact metrics CRUD operations
- Predictions CRUD operations
- Legacy endpoints for backward compatibility
"""
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import models as db_models
import schemas as pydantic_models
from connection import get_db
from dbcrud import DBCRUD
from facts_crud import FactsCRUD
from fastapi import (APIRouter, BackgroundTasks, Body, Depends, HTTPException,
                     Query, status)
from preds_crud import PredsCRUD
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from base_logger import logger

router = APIRouter()

# ===========================================
# CONSTANTS
# ===========================================
DEFAULT_LIMIT = 5000
MAX_LIMIT = 10000
DEFAULT_HOURS = 24
MAX_HOURS = 720
DEFAULT_DAYS_TO_KEEP = 90
MAX_DAYS_TO_KEEP = 365
MIN_INTERVAL_MINUTES = 1
MAX_INTERVAL_MINUTES = 1440
DEFAULT_INTERVAL_MINUTES = 30


# ===========================================
# HELPER FUNCTIONS
# ===========================================


def db_metric_to_schema(db_metric: db_models.ServerMetricsFact) -> pydantic_models.MetricFact:
    """
    Convert database metric model to Pydantic schema.

    Args:
        db_metric: Database model instance

    Returns:
        Pydantic schema instance
    """
    return pydantic_models.MetricFact(
        id=str(db_metric.id) if db_metric.id else None,
        vm=db_metric.vm,
        timestamp=db_metric.timestamp,
        metric=db_metric.metric,
        value=float(db_metric.value) if db_metric.value is not None else 0.0,
        created_at=db_metric.created_at
    )


def db_prediction_to_schema(db_pred: db_models.ServerMetricsPredictions) -> pydantic_models.MetricPrediction:
    """
    Convert database prediction model to Pydantic schema.

    Args:
        db_pred: Database model instance

    Returns:
        Pydantic schema instance
    """
    return pydantic_models.MetricPrediction(
        id=str(db_pred.id),
        vm=db_pred.vm,
        timestamp=db_pred.timestamp,
        metric=db_pred.metric,
        value_predicted=float(db_pred.value_predicted),
        lower_bound=float(db_pred.lower_bound) if db_pred.lower_bound is not None else None,
        upper_bound=float(db_pred.upper_bound) if db_pred.upper_bound is not None else None,
        created_at=db_pred.created_at
    )


def validate_date_range(start_date: Optional[datetime], end_date: Optional[datetime]) -> None:
    """
    Validate that start_date is before end_date.

    Args:
        start_date: Start date
        end_date: End date

    Raises:
        HTTPException: If dates are invalid
    """
    if start_date and end_date and start_date > end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="start_date must be before or equal to end_date"
        )


def handle_database_error(operation: str, error: Exception, context: Optional[str] = None) -> HTTPException:
    """
    Handle database errors and return appropriate HTTP exception.

    Args:
        operation: Description of the operation
        error: The exception that occurred
        context: Additional context (e.g., vm/metric names)

    Returns:
        HTTPException with appropriate status code and message
    """
    error_msg = str(error)
    context_str = f" for {context}" if context else ""

    if isinstance(error, IntegrityError):
        logger.error(f"Integrity error during {operation}{context_str}: {error_msg}")
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Data conflict: {error_msg}"
        )
    elif isinstance(error, SQLAlchemyError):
        logger.error(f"Database error during {operation}{context_str}: {error_msg}")
        return HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error during {operation}: {error_msg}"
        )
    else:
        logger.error(f"Unexpected error during {operation}{context_str}: {error_msg}", exc_info=True)
        return HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error during {operation}: {error_msg}"
        )


# ===========================================
# DBCRUD ENDPOINTS (General Database Operations)
# ===========================================

@router.get("/vms", response_model=List[str], tags=["Database"])
async def get_all_vms(db: Session = Depends(get_db)) -> List[str]:
    """
    Get list of all virtual machines in the database.

    Returns:
        List of VM names (empty list if no VMs found)

    Raises:
        HTTPException: If database error occurs
    """
    try:
        crud = DBCRUD(db)
        vms = crud.get_all_vms()
        return vms or []
    except SQLAlchemyError as e:
        raise handle_database_error("retrieving VMs", e)
    except Exception as e:
        logger.error(f"Unexpected error getting VMs: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while retrieving VMs"
        )


@router.get("/vms/{vm}/metrics", response_model=List[str], tags=["Database"])
async def get_metrics_for_vm(vm: str, db: Session = Depends(get_db)) -> List[str]:
    """
    Get list of available metrics for a specific VM.

    Args:
        vm: Virtual machine name

    Returns:
        List of metric names (empty list if VM not found or has no metrics)

    Raises:
        HTTPException: If database error occurs
    """
    if not vm or not vm.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="VM name cannot be empty"
        )

    try:
        crud = DBCRUD(db)
        metrics = crud.get_metrics_for_vm(vm.strip())
        return metrics or []
    except SQLAlchemyError as e:
        raise handle_database_error("retrieving metrics", e, f"VM: {vm}")
    except Exception as e:
        logger.error(f"Unexpected error getting metrics for VM {vm}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred while retrieving metrics for VM: {vm}"
        )


@router.get("/vms/{vm}/metrics/{metric}/time-range", response_model=pydantic_models.TimeRangeResponse,
            tags=["Database"])
async def get_data_time_range(
        vm: str,
        metric: str,
        db: Session = Depends(get_db)
) -> pydantic_models.TimeRangeResponse:
    """
    Get time range of available data for a VM and metric.

    Args:
        vm: Virtual machine name
        metric: Metric name

    Returns:
        Time range information including first/last timestamp and total records

    Raises:
        HTTPException: 404 if no data found, 500 if database error occurs
    """
    if not vm or not vm.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="VM name cannot be empty"
        )
    if not metric or not metric.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Metric name cannot be empty"
        )

    try:
        crud = DBCRUD(db)
        time_range = crud.get_data_time_range(vm.strip(), metric.strip())

        if not time_range:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No data found for VM '{vm}' and metric '{metric}'"
            )

        return pydantic_models.TimeRangeResponse(**time_range)
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        raise handle_database_error("retrieving time range", e, f"VM: {vm}, Metric: {metric}")
    except Exception as e:
        logger.error(f"Unexpected error getting time range for {vm}/{metric}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred while retrieving time range"
        )


@router.get("/stats", response_model=pydantic_models.DatabaseStatsResponse, tags=["Database"])
async def get_database_stats(db: Session = Depends(get_db)) -> pydantic_models.DatabaseStatsResponse:
    """
    Get database statistics.

    Returns:
        Database statistics including record counts, unique VMs/metrics, data volume

    Raises:
        HTTPException: If database error occurs
    """
    try:
        crud = DBCRUD(db)
        stats = crud.get_database_stats()
        return pydantic_models.DatabaseStatsResponse(**stats)
    except SQLAlchemyError as e:
        raise handle_database_error("retrieving database statistics", e)
    except Exception as e:
        logger.error(f"Unexpected error getting database stats: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while retrieving database statistics"
        )


@router.post("/cleanup", response_model=Dict[str, Any], tags=["Database"])
async def cleanup_old_data(
        days_to_keep: int = Body(
            DEFAULT_DAYS_TO_KEEP,
            ge=1,
            le=MAX_DAYS_TO_KEEP,
            description="Number of days to keep"
        ),
        db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Clean up old data from database.

    Args:
        days_to_keep: Number of days of data to keep (default: 90, max: 365)

    Returns:
        Statistics about deleted records

    Raises:
        HTTPException: If database error occurs
    """
    try:
        crud = DBCRUD(db)
        result = crud.cleanup_old_data(days_to_keep)
        logger.info(f"Cleanup completed: {result}")
        return result
    except SQLAlchemyError as e:
        raise handle_database_error("cleaning up old data", e)
    except Exception as e:
        logger.error(f"Unexpected error cleaning up old data: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while cleaning up old data"
        )


@router.get("/vms/{vm}/metrics/{metric}/completeness", response_model=pydantic_models.DataCompletenessResponse,
            tags=["Database"])
async def get_data_completeness(
        vm: str,
        metric: str,
        start_date: datetime = Query(..., description="Start date"),
        end_date: datetime = Query(..., description="End date"),
        expected_interval_minutes: int = Query(
            DEFAULT_INTERVAL_MINUTES,
            ge=MIN_INTERVAL_MINUTES,
            le=MAX_INTERVAL_MINUTES,
            description="Expected interval in minutes"
        ),
        db: Session = Depends(get_db)
) -> pydantic_models.DataCompletenessResponse:
    """
    Calculate data completeness for a VM and metric.

    Args:
        vm: Virtual machine name
        metric: Metric name
        start_date: Start date for analysis
        end_date: End date for analysis
        expected_interval_minutes: Expected interval between data points (default: 30, max: 1440)

    Returns:
        Data completeness metrics including missing intervals

    Raises:
        HTTPException: 400 if invalid date range, 500 if database error occurs
    """
    validate_date_range(start_date, end_date)

    if not vm or not vm.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="VM name cannot be empty"
        )
    if not metric or not metric.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Metric name cannot be empty"
        )

    try:
        crud = DBCRUD(db)
        completeness = crud.calculate_data_completeness(
            vm.strip(), metric.strip(), start_date, end_date, expected_interval_minutes
        )
        return pydantic_models.DataCompletenessResponse(**completeness)
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        raise handle_database_error("calculating data completeness", e, f"VM: {vm}, Metric: {metric}")
    except Exception as e:
        logger.error(f"Unexpected error calculating completeness for {vm}/{metric}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while calculating data completeness"
        )


@router.get("/vms/{vm}/metrics/{metric}/missing-data", response_model=List[Dict[str, Any]], tags=["Database"])
async def get_missing_data(
        vm: str,
        metric: str,
        start_date: datetime = Query(..., description="Start date"),
        end_date: datetime = Query(..., description="End date"),
        expected_interval_minutes: int = Query(
            DEFAULT_INTERVAL_MINUTES,
            ge=MIN_INTERVAL_MINUTES,
            le=MAX_INTERVAL_MINUTES,
            description="Expected interval in minutes"
        ),
        db: Session = Depends(get_db)
) -> List[Dict[str, Any]]:
    """
    Detect missing data intervals for a VM and metric.

    Args:
        vm: Virtual machine name
        metric: Metric name
        start_date: Start date for analysis
        end_date: End date for analysis
        expected_interval_minutes: Expected interval between data points (default: 30, max: 1440)

    Returns:
        List of missing data intervals (empty list if no missing data)

    Raises:
        HTTPException: 400 if invalid date range, 500 if database error occurs
    """
    validate_date_range(start_date, end_date)

    if not vm or not vm.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="VM name cannot be empty"
        )
    if not metric or not metric.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Metric name cannot be empty"
        )

    try:
        crud = DBCRUD(db)
        missing = crud.detect_missing_data(
            vm.strip(), metric.strip(), start_date, end_date, expected_interval_minutes
        )
        return missing or []
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        raise handle_database_error("detecting missing data", e, f"VM: {vm}, Metric: {metric}")
    except Exception as e:
        logger.error(f"Unexpected error detecting missing data for {vm}/{metric}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while detecting missing data"
        )


# ===========================================
# FACTS CRUD ENDPOINTS (Fact Metrics)
# ===========================================

@router.post("/facts", response_model=pydantic_models.MetricFact, status_code=status.HTTP_201_CREATED, tags=["Facts"])
async def create_metric_fact(
        metric: pydantic_models.MetricFactCreate,
        db: Session = Depends(get_db),
        background_tasks: Optional[BackgroundTasks] = None
) -> pydantic_models.MetricFact:
    """
    Create or update a metric fact (upsert operation).

    Args:
        metric: Metric fact data
        background_tasks: Optional background tasks for anomaly detection

    Returns:
        Created or updated metric fact

    Raises:
        HTTPException: 400 if validation fails, 500 if database error occurs
    """
    try:
        crud = FactsCRUD(db)
        # Create a MetricFact with created_at for the CRUD method
        fact_data = pydantic_models.MetricFact(
            vm=metric.vm.strip() if metric.vm else metric.vm,
            timestamp=metric.timestamp,
            metric=metric.metric.strip() if metric.metric else metric.metric,
            value=metric.value,
            created_at=datetime.now()
        )
        db_metric = crud.create_metric_fact(fact_data)

        # TODO: Add background task for anomaly detection if needed
        # if background_tasks:
        #     background_tasks.add_task(check_for_anomalies, metric.vm, metric.metric, db)

        return db_metric_to_schema(db_metric)
    except ValueError as e:
        logger.warning(f"Validation error creating metric fact: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Validation error: {str(e)}"
        )
    except SQLAlchemyError as e:
        raise handle_database_error("creating metric fact", e, f"VM: {metric.vm}, Metric: {metric.metric}")
    except Exception as e:
        logger.error(f"Unexpected error creating metric fact: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while creating metric fact"
        )


@router.post("/facts/batch", response_model=pydantic_models.BatchCreateResponse, tags=["Facts"])
async def create_metrics_fact_batch(
        metrics: List[pydantic_models.MetricFactCreate],
        db: Session = Depends(get_db)
) -> pydantic_models.BatchCreateResponse:
    """
    Batch create or update metric facts.

    Args:
        metrics: List of metric facts to create (max recommended: 1000 per batch)

    Returns:
        Batch creation statistics

    Raises:
        HTTPException: 400 if empty list, 500 if database error occurs
    """
    if not metrics:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Metrics list cannot be empty"
        )

    if len(metrics) > 10000:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Batch size too large. Maximum 10000 metrics per batch"
        )

    try:
        crud = FactsCRUD(db)

        # Convert create schemas to fact schemas
        fact_metrics = []
        for metric in metrics:
            fact_data = pydantic_models.MetricFact(
                vm=metric.vm.strip() if metric.vm else metric.vm,
                timestamp=metric.timestamp,
                metric=metric.metric.strip() if metric.metric else metric.metric,
                value=metric.value,
                created_at=datetime.now()
            )
            fact_metrics.append(fact_data)

        created_count = crud.create_metrics_fact_batch(fact_metrics)
        failed_count = len(metrics) - created_count

        logger.info(f"Batch create completed: {created_count}/{len(metrics)} metrics created")

        return pydantic_models.BatchCreateResponse(
            created=created_count,
            failed=failed_count,
            total=len(metrics)
        )
    except SQLAlchemyError as e:
        raise handle_database_error("creating metrics batch", e)
    except Exception as e:
        logger.error(f"Unexpected error creating metrics batch: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while creating metrics batch"
        )


@router.get("/facts", response_model=List[pydantic_models.MetricFact], tags=["Facts"])
async def get_metrics_fact(
        vm: str = Query(..., description="Virtual machine name"),
        metric: str = Query(..., description="Metric name"),
        start_date: Optional[datetime] = Query(None, description="Start date (inclusive)"),
        end_date: Optional[datetime] = Query(None, description="End date (inclusive)"),
        limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT, description="Maximum number of records"),
        db: Session = Depends(get_db)
) -> List[pydantic_models.MetricFact]:
    """
    Get historical metric facts with optional date filtering.

    Args:
        vm: Virtual machine name
        metric: Metric name
        start_date: Optional start date filter
        end_date: Optional end date filter
        limit: Maximum number of records to return (default: 5000, max: 10000)

    Returns:
        List of metric facts (empty list if no data found)

    Raises:
        HTTPException: 400 if invalid date range, 500 if database error occurs
    """
    validate_date_range(start_date, end_date)

    if not vm or not vm.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="VM name cannot be empty"
        )
    if not metric or not metric.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Metric name cannot be empty"
        )

    try:
        crud = FactsCRUD(db)
        records = crud.get_metrics_fact(vm.strip(), metric.strip(), start_date, end_date, limit)

        return [db_metric_to_schema(record) for record in records]
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        raise handle_database_error("retrieving metrics fact", e, f"VM: {vm}, Metric: {metric}")
    except Exception as e:
        logger.error(f"Unexpected error getting metrics fact: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while retrieving metrics"
        )


@router.get("/facts/latest", response_model=List[pydantic_models.MetricFact], tags=["Facts"])
async def get_latest_metrics_fact(
        vm: str = Query(..., description="Virtual machine name"),
        metric: str = Query(..., description="Metric name"),
        hours: int = Query(DEFAULT_HOURS, ge=1, le=MAX_HOURS, description="Number of hours to retrieve"),
        db: Session = Depends(get_db)
) -> List[pydantic_models.MetricFact]:
    """
    Get latest metric facts for the last N hours.

    Args:
        vm: Virtual machine name
        metric: Metric name
        hours: Number of hours to retrieve (default: 24, max: 720)

    Returns:
        List of metric facts (empty list if no data found)

    Raises:
        HTTPException: 500 if database error occurs
    """
    if not vm or not vm.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="VM name cannot be empty"
        )
    if not metric or not metric.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Metric name cannot be empty"
        )

    try:
        crud = FactsCRUD(db)
        records = crud.get_latest_metrics(vm.strip(), metric.strip(), hours)

        return [db_metric_to_schema(record) for record in records]
    except SQLAlchemyError as e:
        raise handle_database_error("retrieving latest metrics", e, f"VM: {vm}, Metric: {metric}")
    except Exception as e:
        logger.error(f"Unexpected error getting latest metrics: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while retrieving latest metrics"
        )


@router.get("/facts/statistics", response_model=Dict[str, Any], tags=["Facts"])
async def get_metrics_fact_statistics(
        vm: str = Query(..., description="Virtual machine name"),
        metric: str = Query(..., description="Metric name"),
        start_date: Optional[datetime] = Query(None, description="Start date (inclusive)"),
        end_date: Optional[datetime] = Query(None, description="End date (inclusive)"),
        db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get aggregated statistics for a metric.

    Args:
        vm: Virtual machine name
        metric: Metric name
        start_date: Optional start date filter
        end_date: Optional end date filter

    Returns:
        Statistics including count, min, max, avg, stddev

    Raises:
        HTTPException: 400 if invalid date range, 500 if database error occurs
    """
    validate_date_range(start_date, end_date)

    if not vm or not vm.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="VM name cannot be empty"
        )
    if not metric or not metric.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Metric name cannot be empty"
        )

    try:
        crud = FactsCRUD(db)
        stats = crud.get_metrics_fact_statistics(vm.strip(), metric.strip(), start_date, end_date)
        return stats or {}
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        raise handle_database_error("retrieving statistics", e, f"VM: {vm}, Metric: {metric}")
    except Exception as e:
        logger.error(f"Unexpected error getting statistics: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while retrieving statistics"
        )


# ===========================================
# PREDICTIONS CRUD ENDPOINTS
# ===========================================

@router.post("/predictions", response_model=pydantic_models.MetricPrediction, status_code=status.HTTP_201_CREATED,
             tags=["Predictions"])
async def save_prediction(
        prediction: pydantic_models.MetricPredictionCreate,
        db: Session = Depends(get_db)
) -> pydantic_models.MetricPrediction:
    """
    Save a prediction (upsert operation).

    Args:
        prediction: Prediction data

    Returns:
        Created or updated prediction

    Raises:
        HTTPException: 400 if validation fails, 500 if database error occurs
    """
    try:
        crud = PredsCRUD(db)
        db_pred = crud.save_prediction(
            vm=prediction.vm.strip() if prediction.vm else prediction.vm,
            metric=prediction.metric.strip() if prediction.metric else prediction.metric,
            timestamp=prediction.timestamp,
            value=prediction.value_predicted,
            lower_bound=prediction.lower_bound,
            upper_bound=prediction.upper_bound
        )

        return db_prediction_to_schema(db_pred)
    except ValueError as e:
        logger.warning(f"Validation error saving prediction: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Validation error: {str(e)}"
        )
    except SQLAlchemyError as e:
        raise handle_database_error("saving prediction", e, f"VM: {prediction.vm}, Metric: {prediction.metric}")
    except Exception as e:
        logger.error(f"Unexpected error saving prediction: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while saving prediction"
        )


@router.post("/predictions/batch", response_model=pydantic_models.BatchCreateResponse, tags=["Predictions"])
async def save_predictions_batch(
        predictions: List[pydantic_models.MetricPredictionCreate],
        db: Session = Depends(get_db)
) -> pydantic_models.BatchCreateResponse:
    """
    Batch save predictions.

    Args:
        predictions: List of predictions to save (max recommended: 1000 per batch)

    Returns:
        Batch save statistics

    Raises:
        HTTPException: 400 if empty list, 500 if database error occurs
    """
    if not predictions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Predictions list cannot be empty"
        )

    if len(predictions) > 10000:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Batch size too large. Maximum 10000 predictions per batch"
        )

    try:
        crud = PredsCRUD(db)

        # Convert to dict format expected by save_predictions_batch
        # Note: PredsCRUD.save_predictions_batch expects 'lower' and 'upper' keys
        pred_dicts = []
        for pred in predictions:
            pred_dicts.append({
                'vm': pred.vm.strip() if pred.vm else pred.vm,
                'metric': pred.metric.strip() if pred.metric else pred.metric,
                'timestamp': pred.timestamp,
                'value': pred.value_predicted,
                'lower': pred.lower_bound,
                'upper': pred.upper_bound
            })

        saved_count = crud.save_predictions_batch(pred_dicts)
        failed_count = len(predictions) - saved_count

        logger.info(f"Batch save predictions completed: {saved_count}/{len(predictions)} predictions saved")

        return pydantic_models.BatchCreateResponse(
            created=saved_count,
            failed=failed_count,
            total=len(predictions)
        )
    except SQLAlchemyError as e:
        raise handle_database_error("saving predictions batch", e)
    except Exception as e:
        logger.error(f"Unexpected error saving predictions batch: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while saving predictions batch"
        )


@router.get("/predictions", response_model=List[pydantic_models.MetricPrediction], tags=["Predictions"])
async def get_predictions(
        vm: str = Query(..., description="Virtual machine name"),
        metric: str = Query(..., description="Metric name"),
        start_date: Optional[datetime] = Query(None, description="Start date (inclusive)"),
        end_date: Optional[datetime] = Query(None, description="End date (inclusive)"),
        db: Session = Depends(get_db)
) -> List[pydantic_models.MetricPrediction]:
    """
    Get predictions for a VM and metric.

    Args:
        vm: Virtual machine name
        metric: Metric name
        start_date: Optional start date filter
        end_date: Optional end date filter

    Returns:
        List of predictions (empty list if no predictions found)

    Raises:
        HTTPException: 400 if invalid date range, 500 if database error occurs
    """
    validate_date_range(start_date, end_date)

    if not vm or not vm.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="VM name cannot be empty"
        )
    if not metric or not metric.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Metric name cannot be empty"
        )

    try:
        crud = PredsCRUD(db)
        predictions = crud.get_predictions(vm.strip(), metric.strip(), start_date, end_date)

        return [db_prediction_to_schema(pred) for pred in predictions]
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        raise handle_database_error("retrieving predictions", e, f"VM: {vm}, Metric: {metric}")
    except Exception as e:
        logger.error(f"Unexpected error getting predictions: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while retrieving predictions"
        )


@router.get("/predictions/future", response_model=List[pydantic_models.MetricPrediction], tags=["Predictions"])
async def get_future_predictions(
        vm: str = Query(..., description="Virtual machine name"),
        metric: str = Query(..., description="Metric name"),
        db: Session = Depends(get_db)
) -> List[pydantic_models.MetricPrediction]:
    """
    Get future predictions (timestamp > now) for a VM and metric.

    Args:
        vm: Virtual machine name
        metric: Metric name

    Returns:
        List of future predictions (empty list if no future predictions found)

    Raises:
        HTTPException: 500 if database error occurs
    """
    if not vm or not vm.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="VM name cannot be empty"
        )
    if not metric or not metric.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Metric name cannot be empty"
        )

    try:
        crud = PredsCRUD(db)
        predictions = crud.get_future_predictions(vm.strip(), metric.strip())

        return [db_prediction_to_schema(pred) for pred in predictions]
    except SQLAlchemyError as e:
        raise handle_database_error("retrieving future predictions", e, f"VM: {vm}, Metric: {metric}")
    except Exception as e:
        logger.error(f"Unexpected error getting future predictions: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while retrieving future predictions"
        )


@router.get("/predictions/compare", response_model=List[pydantic_models.ActualVsPredictedResponse],
            tags=["Predictions"])
async def get_actual_vs_predicted(
        vm: str = Query(..., description="Virtual machine name"),
        metric: str = Query(..., description="Metric name"),
        hours: int = Query(DEFAULT_HOURS, ge=1, le=MAX_HOURS, description="Number of hours to compare"),
        db: Session = Depends(get_db)
) -> List[pydantic_models.ActualVsPredictedResponse]:
    """
    Compare actual values with predictions for a VM and metric.

    Args:
        vm: Virtual machine name
        metric: Metric name
        hours: Number of hours to compare (default: 24, max: 720)

    Returns:
        List of comparisons with actual vs predicted values and error metrics (empty list if no data)

    Raises:
        HTTPException: 500 if database error occurs
    """
    if not vm or not vm.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="VM name cannot be empty"
        )
    if not metric or not metric.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Metric name cannot be empty"
        )

    try:
        crud = PredsCRUD(db)
        comparisons = crud.get_actual_vs_predicted(vm.strip(), metric.strip(), hours)

        return [
            pydantic_models.ActualVsPredictedResponse(**comp)
            for comp in (comparisons or [])
        ]
    except SQLAlchemyError as e:
        raise handle_database_error("comparing actual vs predicted", e, f"VM: {vm}, Metric: {metric}")
    except Exception as e:
        logger.error(f"Unexpected error comparing actual vs predicted: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while comparing values"
        )


# ===========================================
# LEGACY ENDPOINTS (for backward compatibility)
# ===========================================

@router.get("/latest_metrics", response_model=List[Dict[str, Any]], tags=["Legacy"])
async def get_latest_metrics_legacy(
        vm: str = Query(..., description="Virtual machine name"),
        metric: str = Query(..., description="Metric name"),
        db: Session = Depends(get_db)
) -> List[Dict[str, Any]]:
    """
    [Legacy] Get latest metrics for the last 24 hours.

    This endpoint is kept for backward compatibility.
    Use /facts/latest instead.

    Args:
        vm: Virtual machine name
        metric: Metric name

    Returns:
        List of metric records with timestamp, value, and created_at

    Raises:
        HTTPException: 500 if database error occurs
    """
    if not vm or not vm.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="VM name cannot be empty"
        )
    if not metric or not metric.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Metric name cannot be empty"
        )

    try:
        crud = FactsCRUD(db)
        data = crud.get_latest_metrics(vm.strip(), metric.strip(), DEFAULT_HOURS)

        return [
            {
                "timestamp": record.timestamp,
                "value": float(record.value) if record.value is not None else 0.0,
                "created_at": record.created_at
            }
            for record in data
        ]
    except SQLAlchemyError as e:
        raise handle_database_error("retrieving latest metrics (legacy)", e, f"VM: {vm}, Metric: {metric}")
    except Exception as e:
        logger.error(f"Unexpected error getting latest metrics (legacy): {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while retrieving metrics"
        )


@router.get("/metrics", response_model=List[Dict[str, Any]], tags=["Legacy"])
async def get_metrics_legacy(
        vm: str = Query(..., description="Virtual machine name"),
        metric: str = Query(..., description="Metric name"),
        days: Optional[int] = Query(1, ge=1, le=30, description="Number of days"),
        start_date: Optional[datetime] = Query(None, description="Start date"),
        end_date: Optional[datetime] = Query(None, description="End date"),
        db: Session = Depends(get_db)
) -> List[Dict[str, Any]]:
    """
    [Legacy] Get metrics with flexible date range.

    This endpoint is kept for backward compatibility.
    Use /facts instead.

    You can specify either days or start_date/end_date, but not both.

    Args:
        vm: Virtual machine name
        metric: Metric name
        days: Number of days (default: 1, max: 30)
        start_date: Optional start date
        end_date: Optional end date

    Returns:
        List of metric records with timestamp, value, and created_at

    Raises:
        HTTPException: 400 if invalid parameters, 500 if database error occurs
    """
    if not vm or not vm.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="VM name cannot be empty"
        )
    if not metric or not metric.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Metric name cannot be empty"
        )

    if days and (start_date or end_date):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Specify either days or start_date/end_date, not both"
        )

    try:
        crud = FactsCRUD(db)

        if start_date and end_date:
            validate_date_range(start_date, end_date)
            data = crud.get_metrics_fact(vm.strip(), metric.strip(), start_date, end_date)
        else:
            hours = days * 24 if days else DEFAULT_HOURS
            data = crud.get_latest_metrics(vm.strip(), metric.strip(), hours)

        return [
            {
                "timestamp": record.timestamp,
                "value": float(record.value) if record.value is not None else 0.0,
                "created_at": record.created_at
            }
            for record in data
        ]
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        raise handle_database_error("retrieving metrics (legacy)", e, f"VM: {vm}, Metric: {metric}")
    except Exception as e:
        logger.error(f"Unexpected error getting metrics (legacy): {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while retrieving metrics"
        )
