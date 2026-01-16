# API Endpoints Documentation

This document describes all available API endpoints for the AIOps Dashboard.

**Base URL:** `/api/v1`

All endpoints are organized by functionality and tagged for easy navigation in the OpenAPI documentation.

---

## Table of Contents

1. [Database Operations (DBCRUD)](#database-operations-dbcrud)
2. [Fact Metrics (FactsCRUD)](#fact-metrics-factscrud)
3. [Predictions (PredsCRUD)](#predictions-predscrud)
4. [Legacy Endpoints](#legacy-endpoints)

---

## Database Operations (DBCRUD)

### Get All VMs
**GET** `/vms`

Get list of all virtual machines in the database.

**Response:** `List[str]` - List of VM names

**Example:**
```bash
curl http://localhost:8000/api/v1/vms
```

---

### Get Metrics for VM
**GET** `/vms/{vm}/metrics`

Get list of available metrics for a specific VM.

**Parameters:**
- `vm` (path): Virtual machine name

**Response:** `List[str]` - List of metric names

**Example:**
```bash
curl http://localhost:8000/api/v1/vms/DataLake-DBN1/metrics
```

---

### Get Data Time Range
**GET** `/vms/{vm}/metrics/{metric}/time-range`

Get time range of available data for a VM and metric.

**Parameters:**
- `vm` (path): Virtual machine name
- `metric` (path): Metric name

**Response:** `TimeRangeResponse`
```json
{
  "first_timestamp": "2025-01-01T00:00:00",
  "last_timestamp": "2025-01-31T23:59:59",
  "total_hours": 744.0,
  "total_records": 1488
}
```

**Example:**
```bash
curl http://localhost:8000/api/v1/vms/DataLake-DBN1/metrics/cpu.usage.average/time-range
```

---

### Get Database Statistics
**GET** `/stats`

Get database statistics including record counts, unique VMs/metrics, and data volume.

**Response:** `DatabaseStatsResponse`
```json
{
  "fact_records": 10000,
  "prediction_records": 5000,
  "total_records": 15000,
  "unique_vms": 20,
  "unique_metrics": 5,
  "data_volume_mb": 1.5,
  "oldest_record": "2025-01-01T00:00:00",
  "newest_record": "2025-01-31T23:59:59",
  "collection_period_days": 31
}
```

**Example:**
```bash
curl http://localhost:8000/api/v1/stats
```

---

### Cleanup Old Data
**POST** `/cleanup`

Clean up old data from database.

**Request Body:**
```json
{
  "days_to_keep": 90
}
```

**Parameters:**
- `days_to_keep` (body): Number of days to keep (1-365, default: 90)

**Response:**
```json
{
  "fact_records_deleted": 1000,
  "prediction_records_deleted": 500,
  "cutoff_date": "2024-10-01T00:00:00"
}
```

**Example:**
```bash
curl -X POST http://localhost:8000/api/v1/cleanup \
  -H "Content-Type: application/json" \
  -d '{"days_to_keep": 90}'
```

---

### Get Data Completeness
**GET** `/vms/{vm}/metrics/{metric}/completeness`

Calculate data completeness for a VM and metric.

**Parameters:**
- `vm` (path): Virtual machine name
- `metric` (path): Metric name
- `start_date` (query): Start date (required)
- `end_date` (query): End date (required)
- `expected_interval_minutes` (query): Expected interval in minutes (default: 30)

**Response:** `DataCompletenessResponse`
```json
{
  "expected_points": 1440,
  "actual_points": 1380,
  "completeness_percentage": 95.83,
  "missing_points": 60,
  "missing_intervals": [...],
  "missing_intervals_count": 3
}
```

**Example:**
```bash
curl "http://localhost:8000/api/v1/vms/DataLake-DBN1/metrics/cpu.usage.average/completeness?start_date=2025-01-01T00:00:00&end_date=2025-01-31T23:59:59&expected_interval_minutes=30"
```

---

### Get Missing Data
**GET** `/vms/{vm}/metrics/{metric}/missing-data`

Detect missing data intervals for a VM and metric.

**Parameters:**
- `vm` (path): Virtual machine name
- `metric` (path): Metric name
- `start_date` (query): Start date (required)
- `end_date` (query): End date (required)
- `expected_interval_minutes` (query): Expected interval in minutes (default: 30)

**Response:** `List[Dict]` - List of missing intervals

**Example:**
```bash
curl "http://localhost:8000/api/v1/vms/DataLake-DBN1/metrics/cpu.usage.average/missing-data?start_date=2025-01-01T00:00:00&end_date=2025-01-31T23:59:59"
```

---

## Fact Metrics (FactsCRUD)

### Create Metric Fact
**POST** `/facts`

Create or update a metric fact (upsert operation).

**Request Body:** `MetricFactCreate`
```json
{
  "vm": "DataLake-DBN1",
  "timestamp": "2025-01-27T12:00:00",
  "metric": "cpu.usage.average",
  "value": 45.5
}
```

**Response:** `MetricFact` (201 Created)

**Example:**
```bash
curl -X POST http://localhost:8000/api/v1/facts \
  -H "Content-Type: application/json" \
  -d '{
    "vm": "DataLake-DBN1",
    "timestamp": "2025-01-27T12:00:00",
    "metric": "cpu.usage.average",
    "value": 45.5
  }'
```

---

### Batch Create Metric Facts
**POST** `/facts/batch`

Batch create or update metric facts.

**Request Body:** `List[MetricFactCreate]`
```json
[
  {
    "vm": "DataLake-DBN1",
    "timestamp": "2025-01-27T12:00:00",
    "metric": "cpu.usage.average",
    "value": 45.5
  },
  {
    "vm": "DataLake-DBN1",
    "timestamp": "2025-01-27T12:30:00",
    "metric": "cpu.usage.average",
    "value": 46.2
  }
]
```

**Response:** `BatchCreateResponse`
```json
{
  "created": 2,
  "failed": 0,
  "total": 2
}
```

**Example:**
```bash
curl -X POST http://localhost:8000/api/v1/facts/batch \
  -H "Content-Type: application/json" \
  -d '[{...}, {...}]'
```

---

### Get Metrics Fact
**GET** `/facts`

Get historical metric facts with optional date filtering.

**Parameters:**
- `vm` (query): Virtual machine name (required)
- `metric` (query): Metric name (required)
- `start_date` (query): Start date (optional)
- `end_date` (query): End date (optional)
- `limit` (query): Maximum records (1-10000, default: 5000)

**Response:** `List[MetricFact]`

**Example:**
```bash
curl "http://localhost:8000/api/v1/facts?vm=DataLake-DBN1&metric=cpu.usage.average&start_date=2025-01-01T00:00:00&end_date=2025-01-31T23:59:59"
```

---

### Get Latest Metrics Fact
**GET** `/facts/latest`

Get latest metric facts for the last N hours.

**Parameters:**
- `vm` (query): Virtual machine name (required)
- `metric` (query): Metric name (required)
- `hours` (query): Number of hours (1-720, default: 24)

**Response:** `List[MetricFact]`

**Example:**
```bash
curl "http://localhost:8000/api/v1/facts/latest?vm=DataLake-DBN1&metric=cpu.usage.average&hours=48"
```

---

### Get Metrics Fact Statistics
**GET** `/facts/statistics`

Get aggregated statistics for a metric.

**Parameters:**
- `vm` (query): Virtual machine name (required)
- `metric` (query): Metric name (required)
- `start_date` (query): Start date (optional)
- `end_date` (query): End date (optional)

**Response:**
```json
{
  "count": 1440,
  "min": 10.5,
  "max": 95.2,
  "avg": 45.8,
  "stddev": 15.3,
  "period": {
    "start": "2025-01-01T00:00:00",
    "end": "2025-01-31T23:59:59"
  }
}
```

**Example:**
```bash
curl "http://localhost:8000/api/v1/facts/statistics?vm=DataLake-DBN1&metric=cpu.usage.average"
```

---

## Predictions (PredsCRUD)

### Save Prediction
**POST** `/predictions`

Save a prediction (upsert operation).

**Request Body:** `MetricPredictionCreate`
```json
{
  "vm": "DataLake-DBN1",
  "timestamp": "2025-01-28T12:00:00",
  "metric": "cpu.usage.average",
  "value_predicted": 48.5,
  "lower_bound": 45.0,
  "upper_bound": 52.0
}
```

**Response:** `MetricPrediction` (201 Created)

**Example:**
```bash
curl -X POST http://localhost:8000/api/v1/predictions \
  -H "Content-Type: application/json" \
  -d '{
    "vm": "DataLake-DBN1",
    "timestamp": "2025-01-28T12:00:00",
    "metric": "cpu.usage.average",
    "value_predicted": 48.5,
    "lower_bound": 45.0,
    "upper_bound": 52.0
  }'
```

---

### Batch Save Predictions
**POST** `/predictions/batch`

Batch save predictions.

**Request Body:** `List[MetricPredictionCreate]`

**Response:** `BatchCreateResponse`

**Example:**
```bash
curl -X POST http://localhost:8000/api/v1/predictions/batch \
  -H "Content-Type: application/json" \
  -d '[{...}, {...}]'
```

---

### Get Predictions
**GET** `/predictions`

Get predictions for a VM and metric.

**Parameters:**
- `vm` (query): Virtual machine name (required)
- `metric` (query): Metric name (required)
- `start_date` (query): Start date (optional)
- `end_date` (query): End date (optional)

**Response:** `List[MetricPrediction]`

**Example:**
```bash
curl "http://localhost:8000/api/v1/predictions?vm=DataLake-DBN1&metric=cpu.usage.average&start_date=2025-01-28T00:00:00"
```

---

### Get Future Predictions
**GET** `/predictions/future`

Get future predictions (timestamp > now) for a VM and metric.

**Parameters:**
- `vm` (query): Virtual machine name (required)
- `metric` (query): Metric name (required)

**Response:** `List[MetricPrediction]`

**Example:**
```bash
curl "http://localhost:8000/api/v1/predictions/future?vm=DataLake-DBN1&metric=cpu.usage.average"
```

---

### Compare Actual vs Predicted
**GET** `/predictions/compare`

Compare actual values with predictions for a VM and metric.

**Parameters:**
- `vm` (query): Virtual machine name (required)
- `metric` (query): Metric name (required)
- `hours` (query): Number of hours to compare (1-720, default: 24)

**Response:** `List[ActualVsPredictedResponse]`
```json
[
  {
    "timestamp": "2025-01-27T12:00:00",
    "actual_value": 45.5,
    "predicted_value": 46.2,
    "error": 0.7,
    "relative_error": 1.54,
    "lower_bound": 43.0,
    "upper_bound": 49.4
  }
]
```

**Example:**
```bash
curl "http://localhost:8000/api/v1/predictions/compare?vm=DataLake-DBN1&metric=cpu.usage.average&hours=24"
```

---

## Legacy Endpoints

These endpoints are kept for backward compatibility. It's recommended to use the new endpoints above.

### Get Latest Metrics (Legacy)
**GET** `/latest_metrics`

Get latest metrics for the last 24 hours.

**Parameters:**
- `vm` (query): Virtual machine name (required)
- `metric` (query): Metric name (required)

**Response:** `List[dict]`

**Note:** Use `/facts/latest` instead.

---

### Get Metrics (Legacy)
**GET** `/metrics`

Get metrics with flexible date range.

**Parameters:**
- `vm` (query): Virtual machine name (required)
- `metric` (query): Metric name (required)
- `days` (query): Number of days (1-30, default: 1)
- `start_date` (query): Start date (optional)
- `end_date` (query): End date (optional)

**Response:** `List[dict]`

**Note:** Use `/facts` instead.

---

## Error Responses

All endpoints may return the following error responses:

### 400 Bad Request
```json
{
  "detail": "Error message describing the issue"
}
```

### 404 Not Found
```json
{
  "detail": "Resource not found"
}
```

### 500 Internal Server Error
```json
{
  "detail": "Internal server error message"
}
```

---

## OpenAPI Documentation

Interactive API documentation is available at:
- **Swagger UI:** `http://localhost:8000/docs`
- **ReDoc:** `http://localhost:8000/redoc`

---

## Notes

1. All timestamps are in UTC timezone
2. All date parameters should be in ISO 8601 format: `YYYY-MM-DDTHH:MM:SS`
3. Value fields are validated to be between 0 and 100
4. Batch operations may partially succeed - check the response for created/failed counts
5. Upsert operations (create endpoints) will update existing records if they match on (vm, metric, timestamp)

---

*Last Updated: 2025-01-27*

