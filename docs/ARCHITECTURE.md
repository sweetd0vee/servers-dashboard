# Architecture Documentation
## AIOps Dashboard Project

This document describes the system architecture, components, data flow, and deployment structure of the AIOps Dashboard application.

**Last Updated:** 2025-01-27  
**Version:** 2.0

---

## Table of Contents

1. [System Overview](#system-overview)
2. [High-Level Architecture](#high-level-architecture)
3. [Component Architecture](#component-architecture)
4. [Data Flow Diagrams](#data-flow-diagrams)
5. [Database Schema](#database-schema)
6. [Deployment Architecture](#deployment-architecture)
7. [Technology Stack](#technology-stack)
8. [Testing Architecture](#testing-architecture)
9. [Error Handling Architecture](#error-handling-architecture)

---

## System Overview

The AIOps Dashboard is a full-stack application for monitoring and forecasting server metrics. It consists of:

- **Backend API**: FastAPI-based REST API with comprehensive error handling and validation
- **Frontend UI**: Streamlit-based interactive dashboard with database integration
- **Database**: PostgreSQL for time-series metrics storage
- **Forecasting Engine**: Prophet-based time series forecasting
- **Testing Suite**: Comprehensive pytest-based test coverage
- **Authentication**: Keycloak integration (configured but not fully implemented)
- **Reverse Proxy**: Apache HTTPd for routing and SSL termination

---

## High-Level Architecture

```mermaid
graph TB
    subgraph "Client Layer"
        Browser[Web Browser]
    end
    
    subgraph "Reverse Proxy Layer"
        HTTPd[Apache HTTPd<br/>Port 80/443]
    end
    
    subgraph "Application Layer"
        API[FastAPI Backend<br/>Port 8000<br/>Enhanced Error Handling]
        UI[Streamlit Frontend<br/>Port 8501<br/>Database Integration]
    end
    
    subgraph "Service Layer"
        Auth[Keycloak<br/>Port 8087]
        LLM[LLaMA Server<br/>Port 8080]
    end
    
    subgraph "Data Layer"
        DB[(PostgreSQL<br/>Port 5432)]
        Models[Model Storage<br/>File System]
    end
    
    subgraph "Testing Layer"
        Tests[Pytest Test Suite<br/>Unit & Integration Tests]
    end
    
    Browser -->|HTTPS/HTTP| HTTPd
    HTTPd -->|/api/*| API
    HTTPd -->|/dashboard-ui/*| UI
    HTTPd -->|/keycloak/*| Auth
    
    API -->|Read/Write| DB
    API -->|Load/Save| Models
    UI -->|API Calls| API
    UI -->|Direct| DB
    
    Auth -->|User Data| DB
    API -.->|Auth Check| Auth
    
    Tests -->|Test| API
    Tests -->|Test| DB
    
    style Browser fill:#e1f5ff
    style HTTPd fill:#fff4e1
    style API fill:#e8f5e9
    style UI fill:#e8f5e9
    style DB fill:#f3e5f5
    style Models fill:#f3e5f5
    style Auth fill:#fff9c4
    style LLM fill:#fff9c4
    style Tests fill:#ffebee
```

---

## Component Architecture

### Backend API Components

```mermaid
graph LR
    subgraph "API Layer"
        Main[main.py<br/>FastAPI App]
        Router[api/endpoints.py<br/>REST Routes<br/>Error Handling<br/>Validation]
    end
    
    subgraph "Business Logic"
        CRUD[dbcrud.py<br/>Data Access]
        FactsCRUD[facts_crud.py<br/>Fact Metrics]
        PredsCRUD[preds_crud.py<br/>Predictions]
        Forecaster[forecaster.py<br/>Prophet ML]
        Anomaly[anomaly_detector.py<br/>Anomaly Detection]
    end
    
    subgraph "Data Models"
        Models[models.py<br/>SQLAlchemy ORM]
        Schemas[schemas.py<br/>Pydantic Models]
    end
    
    subgraph "Infrastructure"
        Conn[connection.py<br/>DB Connection]
        Logger[base_logger.py<br/>Logging]
    end
    
    subgraph "API Helpers"
        Helpers[Helper Functions<br/>db_metric_to_schema<br/>validate_date_range<br/>handle_database_error]
        Constants[Constants<br/>DEFAULT_LIMIT<br/>MAX_HOURS<br/>etc.]
    end
    
    Main --> Router
    Router --> CRUD
    Router --> FactsCRUD
    Router --> PredsCRUD
    Router --> Forecaster
    Router --> Anomaly
    Router --> Helpers
    Router --> Constants
    CRUD --> Models
    FactsCRUD --> Models
    PredsCRUD --> Models
    CRUD --> Conn
    Forecaster --> Models
    Forecaster --> Conn
    Models --> Conn
    Main --> Logger
    
    style Main fill:#4caf50
    style Router fill:#81c784
    style CRUD fill:#66bb6a
    style FactsCRUD fill:#66bb6a
    style PredsCRUD fill:#66bb6a
    style Forecaster fill:#ff9800
    style Anomaly fill:#ff9800
    style Models fill:#2196f3
    style Schemas fill:#2196f3
    style Conn fill:#9e9e9e
    style Logger fill:#9e9e9e
    style Helpers fill:#9ccc65
    style Constants fill:#9ccc65
```

### Frontend UI Components

```mermaid
graph TB
    subgraph "UI Entry Point"
        MainUI[main.py<br/>Streamlit App]
    end
    
    subgraph "Pages"
        Fact[pages/fact.py<br/>Fact Metrics<br/>Database Loaded]
        Forecast[pages/forecast.py<br/>Forecasting<br/>Database Loaded]
        Analysis[pages/analysis.py<br/>Analysis<br/>Database Loaded]
    end
    
    subgraph "Components"
        Header[components/header.py]
        Sidebar[components/sidebar.py]
        Footer[components/footer.py]
    end
    
    subgraph "Utilities"
        DataLoader[utils/data_loader.py<br/>Database Integration]
        DataGen[utils/data_generator.py<br/>Fallback Generator]
        Alerts[utils/alert_rules.py]
        Analyzer[utils/alert_analyzer.py]
    end
    
    MainUI --> Fact
    MainUI --> Forecast
    MainUI --> Analysis
    MainUI --> Header
    MainUI --> Sidebar
    MainUI --> Footer
    
    Fact --> DataLoader
    Fact --> Alerts
    Forecast --> DataLoader
    Forecast --> DataGen
    Analysis --> DataLoader
    Analysis --> Analyzer
    
    DataLoader -->|Primary| DB[(PostgreSQL)]
    DataGen -->|Fallback| MockData[Mock Data]
    
    style MainUI fill:#ff6b6b
    style Fact fill:#ff8787
    style Forecast fill:#ff8787
    style Analysis fill:#ff8787
    style Header fill:#ffa8a8
    style Sidebar fill:#ffa8a8
    style Footer fill:#ffa8a8
    style DataLoader fill:#51cf66
    style DataGen fill:#ffd43b
    style DB fill:#2196f3
```

### Testing Architecture

```mermaid
graph TB
    subgraph "Test Suite"
        TestMain[tests/<br/>Test Suite Root]
        
        subgraph "Unit Tests"
            TestDB[test_dbcrud.py<br/>DBCRUD Tests]
            TestFacts[test_factscrud.py<br/>FactsCRUD Tests]
            TestPreds[test_predscrud.py<br/>PredsCRUD Tests]
        end
        
        subgraph "Integration Tests"
            TestAPI[test_api_endpoints.py<br/>API Endpoint Tests]
        end
        
        subgraph "Test Infrastructure"
            Conftest[conftest.py<br/>Fixtures & Config]
            TestDB_Instance[(SQLite<br/>In-Memory<br/>Test DB)]
        end
    end
    
    TestMain --> TestDB
    TestMain --> TestFacts
    TestMain --> TestPreds
    TestMain --> TestAPI
    
    TestDB --> Conftest
    TestFacts --> Conftest
    TestPreds --> Conftest
    TestAPI --> Conftest
    
    Conftest --> TestDB_Instance
    
    style TestMain fill:#ffebee
    style TestDB fill:#ffcdd2
    style TestFacts fill:#ffcdd2
    style TestPreds fill:#ffcdd2
    style TestAPI fill:#ef9a9a
    style Conftest fill:#e1bee7
    style TestDB_Instance fill:#ce93d8
```

---

## Data Flow Diagrams

### Metrics Retrieval Flow (Enhanced)

```mermaid
sequenceDiagram
    participant User
    participant UI as Streamlit UI
    participant DataLoader as data_loader.py
    participant API as FastAPI
    participant CRUD as FactsCRUD
    participant DB as PostgreSQL
    
    User->>UI: Select VM & Metric
    UI->>DataLoader: load_data_from_db()
    
    alt Database Available
        DataLoader->>CRUD: get_metrics_fact()
        CRUD->>DB: SELECT query with validation
        DB-->>CRUD: Result set
        CRUD-->>DataLoader: List[ServerMetricsFact]
        DataLoader->>DataLoader: Transform to DataFrame
        DataLoader-->>UI: DataFrame
    else Database Unavailable
        DataLoader->>DataLoader: Fallback to generator
        DataLoader-->>UI: Mock DataFrame
    end
    
    UI->>UI: Render charts/graphs
    UI-->>User: Display metrics
```

### API Request Flow with Error Handling

```mermaid
sequenceDiagram
    participant Client
    participant API as FastAPI Endpoint
    participant Validator as Input Validation
    participant Helper as Helper Functions
    participant CRUD as CRUD Layer
    participant DB as PostgreSQL
    participant Logger as Logger
    
    Client->>API: HTTP Request
    API->>Validator: Validate input (Pydantic)
    
    alt Validation Failed
        Validator-->>API: 400 Bad Request
        API-->>Client: Error Response
    else Validation Passed
        API->>Helper: validate_date_range()
        Helper-->>API: OK
        
        API->>CRUD: Business Logic Call
        CRUD->>DB: Database Query
        
        alt Database Error
            DB-->>CRUD: SQLAlchemyError
            CRUD-->>API: Exception
            API->>Helper: handle_database_error()
            Helper->>Logger: Log error with context
            Helper-->>API: HTTPException
            API-->>Client: 500/409 Error Response
        else Success
            DB-->>CRUD: Result
            CRUD-->>API: Data Model
            API->>Helper: db_metric_to_schema()
            Helper-->>API: Pydantic Schema
            API-->>Client: 200 OK Response
        end
    end
```

### Forecasting Flow

```mermaid
sequenceDiagram
    participant User
    participant UI as Streamlit UI
    participant API as FastAPI
    participant Forecaster as ProphetForecaster
    participant CRUD as DBCRUD
    participant DB as PostgreSQL
    participant Storage as Model Storage
    
    User->>UI: Request Forecast
    UI->>API: POST /api/v1/predict
    API->>Forecaster: generate_forecast(vm, metric)
    
    alt Model Exists
        Forecaster->>Storage: load_model(vm, metric)
        Storage-->>Forecaster: Prophet Model
    else Model Not Found
        Forecaster->>CRUD: get_historical_metrics()
        CRUD->>DB: SELECT historical data
        DB-->>CRUD: Time series data
        CRUD-->>Forecaster: DataFrame
        Forecaster->>Forecaster: train_model()
        Forecaster->>Storage: save_model()
    end
    
    Forecaster->>Forecaster: predict(periods=48)
    Forecaster->>CRUD: save_prediction()
    CRUD->>DB: INSERT predictions
    DB-->>CRUD: Success
    CRUD-->>Forecaster: Confirmation
    Forecaster-->>API: Forecast results
    API-->>UI: JSON with predictions
    UI->>UI: Render forecast chart
    UI-->>User: Display forecast
```

### Data Ingestion Flow

```mermaid
sequenceDiagram
    participant External as External System
    participant API as FastAPI
    participant Validator as Pydantic Validator
    participant CRUD as FactsCRUD
    participant DB as PostgreSQL
    participant Anomaly as AnomalyDetector
    participant Logger as Logger
    
    External->>API: POST /api/v1/facts/batch
    API->>Validator: Validate input (Pydantic)
    
    alt Validation Failed
        Validator-->>API: ValidationError
        API-->>External: 400 Bad Request
    else Validation Passed
        API->>CRUD: create_metrics_fact_batch()
        
        loop For each metric
            CRUD->>DB: INSERT INTO server_metrics_fact
            alt Integrity Error
                DB-->>CRUD: IntegrityError
                CRUD->>Logger: Log error
                CRUD-->>API: Continue (skip duplicate)
            else Success
                DB-->>CRUD: Success
            end
        end
        
        CRUD-->>API: Created count
        API->>Anomaly: detect_realtime_anomaly()
        Anomaly->>CRUD: get_latest_metrics()
        CRUD->>DB: SELECT recent data
        DB-->>CRUD: Historical values
        CRUD-->>Anomaly: Data
        Anomaly->>Anomaly: Calculate anomaly score
        alt Anomaly Detected
            Anomaly-->>API: Alert
            API->>Logger: Log alert
        end
        API-->>External: 201 Created + BatchCreateResponse
    end
```

---

## Database Schema

### Entity Relationship Diagram

```mermaid
erDiagram
    ServerMetricsFact ||--o{ ServerMetricsPredictions : "related"
    
    ServerMetricsFact {
        uuid id PK
        string vm
        datetime timestamp
        string metric
        decimal value
        datetime created_at
    }
    
    ServerMetricsPredictions {
        uuid id PK
        string vm
        datetime timestamp
        string metric
        decimal value_predicted
        decimal lower_bound
        decimal upper_bound
        datetime created_at
    }
```

### Table Structure

#### server_metrics_fact
- **Purpose**: Stores actual/historical server metrics
- **Primary Key**: `id` (UUID)
- **Unique Constraint**: `(vm, timestamp, metric)`
- **Indexes**: 
  - `idx_vm_timestamp_metric` on `(vm, timestamp, metric)`
  - Individual indexes on `vm`, `timestamp`, `value`
- **Constraints**: 
  - `chk_timestamp_not_future`: Ensures timestamps are not in the future
  - `chk_value_range`: Ensures values are between 0 and 100

#### server_metrics_predictions
- **Purpose**: Stores forecasted/predicted metrics
- **Primary Key**: `id` (UUID)
- **Unique Constraint**: `(vm, timestamp, metric)`
- **Indexes**: 
  - `idx_vm_timestamp_metric_pred` on `(vm, timestamp, metric)`
  - Individual indexes on `vm`, `timestamp`
- **Fields**: Includes confidence intervals (`lower_bound`, `upper_bound`)

---

## Deployment Architecture

### Docker Compose Deployment

```mermaid
graph TB
    subgraph "Docker Network: servers-network"
        subgraph "Web Layer"
            HTTPd[Apache HTTPd<br/>Container: httpd-proxy<br/>Ports: 80, 443]
        end
        
        subgraph "Application Containers"
            API_Container[FastAPI App<br/>Container: dashboard<br/>Port: 8000<br/>Enhanced Error Handling]
            UI_Container[Streamlit UI<br/>Container: dashboard-ui<br/>Port: 8501<br/>Database Integration]
        end
        
        subgraph "Service Containers"
            Keycloak[Keycloak<br/>Container: keycloak<br/>Port: 8087]
            LLaMA[LLaMA Server<br/>Container: llama-server<br/>Port: 8080]
        end
        
        subgraph "Data Containers"
            Postgres[PostgreSQL<br/>Container: postgres<br/>Port: 5432<br/>Volume: postgres-data]
        end
    end
    
    subgraph "Host Volumes"
        ModelStorage[Model Storage<br/>./notebooks/models]
        PostgresData[Postgres Data<br/>~/docker-share/postgres-data-server]
        SSL_Certs[SSL Certificates<br/>./docker/httpd/data/letsencrypt]
    end
    
    HTTPd -->|Route /api/*| API_Container
    HTTPd -->|Route /dashboard-ui/*| UI_Container
    HTTPd -->|Route /keycloak/*| Keycloak
    
    API_Container -->|Connect| Postgres
    UI_Container -->|API Calls| API_Container
    UI_Container -->|Direct| Postgres
    Keycloak -->|Connect| Postgres
    
    API_Container -->|Read/Write| ModelStorage
    Postgres -->|Persist| PostgresData
    HTTPd -->|SSL Certs| SSL_Certs
    
    style HTTPd fill:#ff9800
    style API_Container fill:#4caf50
    style UI_Container fill:#4caf50
    style Postgres fill:#2196f3
    style Keycloak fill:#ffc107
    style LLaMA fill:#ffc107
```

---

## Technology Stack

### Backend Stack
```
┌─────────────────────────────────────┐
│         FastAPI 0.104.1            │
│  - REST API Framework               │
│  - Async support                    │
│  - Auto-generated OpenAPI docs      │
│  - Enhanced error handling          │
│  - Input validation (Pydantic)      │
└─────────────────────────────────────┘
           │
           ├─── SQLAlchemy 2.0.23
           │    - ORM for PostgreSQL
           │    - Error handling (SQLAlchemyError)
           │
           ├─── Pydantic 2.5.0
           │    - Data validation
           │    - Type safety
           │
           ├─── Prophet 1.1.5
           │    - Time series forecasting
           │
           └─── Uvicorn 0.24.0
                - ASGI server
```

### Frontend Stack
```
┌─────────────────────────────────────┐
│      Streamlit 1.29.0               │
│  - Interactive dashboard             │
│  - Real-time updates                 │
│  - Database integration              │
│  - Data caching (@st.cache_data)     │
└─────────────────────────────────────┘
           │
           ├─── Plotly 5.18.0
           │    - Interactive charts
           │
           ├─── Pandas 2.1.4
           │    - Data manipulation
           │
           └─── NumPy 1.26.2
                - Numerical operations
```

### Testing Stack
```
┌─────────────────────────────────────┐
│         Pytest 7.4.3                │
│  - Unit testing                      │
│  - Integration testing               │
│  - Fixture management                │
└─────────────────────────────────────┘
           │
           ├─── pytest-cov
           │    - Coverage reporting
           │
           ├─── httpx
           │    - HTTP client for testing
           │
           └─── SQLite (in-memory)
                - Test database
```

### Infrastructure Stack
```
┌─────────────────────────────────────┐
│         Docker & Docker Compose     │
│  - Containerization                  │
│  - Multi-service orchestration       │
└─────────────────────────────────────┘
           │
           ├─── PostgreSQL 16.9
           │    - Time-series database
           │
           ├─── Apache HTTPd 2.4
           │    - Reverse proxy
           │    - SSL termination
           │
           ├─── Keycloak 26.4.6
           │    - Identity management
           │
           └─── LLaMA Server
                - AI/ML capabilities
```

---

## Testing Architecture

### Test Structure

```
tests/
├── __init__.py
├── conftest.py              # Pytest fixtures and configuration
├── test_dbcrud.py          # Unit tests for DBCRUD
├── test_factscrud.py       # Unit tests for FactsCRUD
├── test_predscrud.py       # Unit tests for PredsCRUD
├── test_api_endpoints.py   # Integration tests for API
├── requirements.txt        # Test dependencies
└── README.md               # Test documentation
```

### Test Coverage

- **Unit Tests**: Test individual CRUD operations in isolation
- **Integration Tests**: Test API endpoints with test database
- **Fixtures**: Reusable test data and database sessions
- **Test Database**: In-memory SQLite for fast, isolated tests

### Test Execution

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src/app --cov-report=html

# Run specific test.csv file
pytest tests/test_api_endpoints.py

# Run with verbose output
pytest -v
```

---

## Error Handling Architecture

### Error Handling Layers

```mermaid
graph TB
    subgraph "API Layer"
        Endpoint[API Endpoint]
        Validator[Input Validation<br/>Pydantic]
    end
    
    subgraph "Helper Layer"
        DateValidator[validate_date_range]
        ErrorHandler[handle_database_error]
        SchemaConverter[db_metric_to_schema<br/>db_prediction_to_schema]
    end
    
    subgraph "Business Logic Layer"
        CRUD[CRUD Operations]
    end
    
    subgraph "Database Layer"
        DB[(PostgreSQL)]
    end
    
    subgraph "Logging Layer"
        Logger[base_logger.py]
    end
    
    Endpoint --> Validator
    Validator -->|Valid| DateValidator
    DateValidator -->|Valid| CRUD
    CRUD --> DB
    
    CRUD -->|Error| ErrorHandler
    DB -->|Error| ErrorHandler
    ErrorHandler --> Logger
    ErrorHandler -->|HTTPException| Endpoint
    
    CRUD -->|Success| SchemaConverter
    SchemaConverter --> Endpoint
    
    style Endpoint fill:#4caf50
    style Validator fill:#81c784
    style ErrorHandler fill:#ff9800
    style Logger fill:#9e9e9e
```

### Error Types and Handling

1. **Validation Errors (400 Bad Request)**
   - Empty VM/metric names
   - Invalid date ranges
   - Value out of range (0-100)
   - Missing required parameters

2. **Database Errors**
   - **IntegrityError (409 Conflict)**: Duplicate records, constraint violations
   - **SQLAlchemyError (500 Internal Server Error)**: Connection issues, query errors

3. **Not Found Errors (404)**
   - VM/metric not found
   - No data for time range

4. **Unexpected Errors (500)**
   - Caught with full stack trace logging
   - Generic error message to client

### Constants and Configuration

The API uses constants for limits and defaults:

```python
DEFAULT_LIMIT = 5000          # Default query limit
MAX_LIMIT = 10000             # Maximum query limit
DEFAULT_HOURS = 24            # Default hours for latest queries
MAX_HOURS = 720               # Maximum hours (30 days)
DEFAULT_DAYS_TO_KEEP = 90     # Default cleanup retention
MAX_DAYS_TO_KEEP = 365        # Maximum cleanup retention
MIN_INTERVAL_MINUTES = 1      # Minimum interval for completeness
MAX_INTERVAL_MINUTES = 1440   # Maximum interval (24 hours)
DEFAULT_INTERVAL_MINUTES = 30 # Default interval
```

---

## Module Dependencies

### Backend Dependencies Graph

```mermaid
graph TD
    main[main.py] --> endpoints[api/endpoints.py]
    main --> connection[connection.py]
    main --> models[models.py]
    
    endpoints --> dbcrud[dbcrud.py]
    endpoints --> facts_crud[facts_crud.py]
    endpoints --> preds_crud[preds_crud.py]
    endpoints --> connection
    endpoints --> helpers[Helper Functions]
    endpoints --> constants[Constants]
    
    dbcrud --> models
    dbcrud --> connection
    facts_crud --> models
    facts_crud --> connection
    preds_crud --> models
    preds_crud --> connection
    
    forecaster[forecaster.py] --> dbcrud
    forecaster --> connection
    forecaster --> storage[storage.py]
    
    anomaly[anomaly_detector.py] --> dbcrud
    
    models --> connection
    
    style main fill:#4caf50
    style endpoints fill:#81c784
    style dbcrud fill:#66bb6a
    style facts_crud fill:#66bb6a
    style preds_crud fill:#66bb6a
    style forecaster fill:#ff9800
    style models fill:#2196f3
    style connection fill:#9e9e9e
    style helpers fill:#9ccc65
    style constants fill:#9ccc65
```

---

## API Endpoints Structure

```mermaid
graph LR
    API[FastAPI App<br/>/api/v1] --> Database[Database Operations<br/>/vms, /stats, /cleanup]
    API --> Facts[Fact Metrics<br/>/facts, /facts/batch<br/>/facts/latest]
    API --> Predictions[Predictions<br/>/predictions, /predictions/batch<br/>/predictions/future]
    API --> Legacy[Legacy Endpoints<br/>/metrics, /latest_metrics]
    
    Database --> Validation[Input Validation<br/>Error Handling]
    Facts --> Validation
    Predictions --> Validation
    Legacy --> Validation
    
    style API fill:#4caf50
    style Database fill:#81c784
    style Facts fill:#81c784
    style Predictions fill:#81c784
    style Legacy fill:#ff9800
    style Validation fill:#ffeb3b
```

**Current Endpoints:**
- **Database Operations**: `/vms`, `/vms/{vm}/metrics`, `/stats`, `/cleanup`, `/completeness`, `/missing-data`
- **Fact Metrics**: `/facts`, `/facts/batch`, `/facts/latest`, `/facts/statistics`
- **Predictions**: `/predictions`, `/predictions/batch`, `/predictions/future`, `/predictions/compare`
- **Legacy**: `/metrics`, `/latest_metrics` (for backward compatibility)

---

## Data Processing Pipeline

```mermaid
graph LR
    Raw[Raw Data<br/>CSV/Excel] --> Prep[Data Preparation<br/>utils/prepare_data.py]
    Prep --> Load[Data Loader<br/>utils/data_loader.py<br/>Primary Source]
    Load --> DB[(PostgreSQL<br/>server_metrics_fact)]
    DB --> Query[CRUD Operations<br/>dbcrud.py, facts_crud.py]
    Query --> Forecast[Forecasting<br/>forecaster.py]
    Forecast --> Predictions[(Predictions<br/>server_metrics_predictions)]
    Predictions --> UI[Dashboard<br/>Streamlit<br/>data_loader.py]
    
    Fallback[Data Generator<br/>utils/data_generator.py<br/>Fallback] -.->|If DB unavailable| UI
    
    style Raw fill:#ffeb3b
    style Prep fill:#ffc107
    style Load fill:#ff9800
    style DB fill:#2196f3
    style Query fill:#4caf50
    style Forecast fill:#9c27b0
    style Predictions fill:#2196f3
    style UI fill:#f44336
    style Fallback fill:#ffd43b
```

---

## Security Architecture (Planned)

```mermaid
graph TB
    Client[Client Browser] --> HTTPd[Apache HTTPd]
    HTTPd -->|SSL/TLS| HTTPS[HTTPS Termination]
    HTTPS --> Auth[Keycloak<br/>Authentication]
    Auth -->|JWT Token| API[FastAPI API]
    API -->|Validate Token| Auth
    API -->|Authorized Request| DB[(Database)]
    
    style Client fill:#e1f5ff
    style HTTPd fill:#fff4e1
    style Auth fill:#fff9c4
    style API fill:#e8f5e9
    style DB fill:#f3e5f5
```

**Note:** Authentication is configured but not fully implemented in the current codebase.

---

## File Structure Overview

```
dashboard/
├── src/
│   ├── app/              # FastAPI Backend
│   │   ├── api/         # API endpoints
│   │   │   └── endpoints.py  # Enhanced with error handling
│   │   ├── models.py    # Database models
│   │   ├── schemas.py   # Pydantic schemas
│   │   ├── dbcrud.py    # Database operations
│   │   ├── facts_crud.py # Fact metrics CRUD
│   │   ├── preds_crud.py # Predictions CRUD
│   │   └── main.py      # FastAPI app
│   │
│   └── ui/              # Streamlit Frontend
│       ├── pages/       # Page components
│       │   ├── fact.py      # Database integrated
│       │   ├── forecast.py  # Database integrated
│       │   └── analysis.py  # Database integrated
│       ├── components/  # UI components
│       └── utils/       # UI utilities
│           ├── data_loader.py   # Primary data source
│           └── data_generator.py # Fallback generator
│
├── forecast/            # Forecasting module
│   ├── forecaster.py    # Main interface
│   ├── model_training.py
│   ├── model_tuning.py
│   └── ...
│
├── tests/               # Test suite
│   ├── conftest.py      # Test fixtures
│   ├── test_dbcrud.py   # Unit tests
│   ├── test_factscrud.py
│   ├── test_predscrud.py
│   ├── test_api_endpoints.py  # Integration tests
│   └── README.md
│
├── docker/              # Docker configurations
│   ├── app/            # API container
│   ├── ui/             # UI container
│   ├── postgres/       # Database container
│   └── httpd/          # Reverse proxy
│
├── notebooks/          # Jupyter notebooks
└── data/              # Data files
    ├── source/        # Raw data
    └── processed/     # Processed data
```

---

## Performance Considerations

### Current Architecture
- **Synchronous database operations** (SQLAlchemy ORM)
- **No caching layer** (Redis/Memcached)
- **Direct database queries** from UI (with fallback to generator)
- **File-based model storage** (could use object storage)
- **Streamlit caching** (`@st.cache_data`) for UI performance

### Recommended Improvements
1. **Add Redis** for caching frequently accessed data
2. **Implement async database operations** (async SQLAlchemy)
3. **Add API gateway** for rate limiting
4. **Use object storage** (S3/MinIO) for model files
5. **Implement connection pooling** optimization
6. **Add database read replicas** for scaling
7. **Implement response caching** for API endpoints

---

## Monitoring & Observability (Planned)

```mermaid
graph TB
    App[Application] --> Logs[Logging<br/>base_logger.py<br/>Enhanced Error Logging]
    App --> Metrics[Prometheus<br/>Metrics]
    Metrics --> Grafana[Grafana<br/>Dashboards]
    Logs --> ELK[ELK Stack<br/>Log Aggregation]
    
    style App fill:#4caf50
    style Logs fill:#ff9800
    style Metrics fill:#2196f3
    style Grafana fill:#9c27b0
    style ELK fill:#f44336
```

**Current State:**
- Enhanced file-based logging with error context
- Structured error logging with stack traces
- No metrics collection
- No distributed tracing

---

## Conclusion

This architecture provides a solid foundation for an AIOps dashboard with time-series forecasting capabilities. The modular design allows for independent scaling of components and clear separation of concerns.

**Key Strengths:**
- Clear separation between frontend and backend
- Modular forecasting engine
- Containerized deployment
- Well-structured database schema
- Comprehensive error handling
- Input validation and type safety
- Test coverage with unit and integration tests
- Database integration in UI with fallback mechanism

**Areas for Improvement:**
- Add caching layer (Redis)
- Implement full authentication
- Add comprehensive monitoring
- Optimize for async operations
- Add API versioning
- Implement rate limiting

---

*Last Updated: 2025-01-27*  
*Version: 2.0*
