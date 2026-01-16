# Full Code Review — AIOps Dashboard

Date: 2026-01-16  
Repository: `servers-dashboard`  
Reviewer: Senior software engineer + ML engineer

## Overall Rating
**7.1 / 10**  
Solid architecture and functional scope, but several critical defects in forecasting and batch predictions, plus security and portability issues. Good foundation, needs targeted fixes.

---

## Scope and Method
- Reviewed core modules: `src/app`, `src/ui`, `forecast`, `utils`, `tests`, `docker`, `docs`.
- Focus: correctness, security, reliability, performance, testability, and ML concerns.

---

## High‑Impact Findings (Critical)

### 1) Batch predictions crash due to incorrect parameters
`PredsCRUD.save_predictions_batch` calls `save_prediction` with `lower`/`upper`, but the method expects `lower_bound`/`upper_bound`.

```71:102:src/app/preds_crud.py
    def save_predictions_batch(
            self,
            predictions: List[Dict]
    ) -> int:
        ...
            try:
                self.save_prediction(
                    vm=pred['vm'],
                    metric=pred['metric'],
                    timestamp=pred['timestamp'],
                    value=pred['value'],
                    lower=pred.get('lower'),
                    upper=pred.get('upper')
                )
```

**Fix**
- Rename arguments to `lower_bound` and `upper_bound`.
- Add an API test for `/predictions/batch` that asserts successful persistence.

### 2) Forecast training fails due to mismatched data format
`forecast/utils.prepare_data` expects `ds`/`y`, but `forecast/forecaster.py` passes `timestamp`/`value`.

```48:50:forecast/forecaster.py
        data_dicts = [{'timestamp': r.timestamp, 'value': float(r.value)} for r in data_records]
        df = prepare_data(data_dicts)
```

```29:41:forecast/utils.py
def prepare_data(data: List[Dict]) -> pd.DataFrame:
    ...
    df = pd.DataFrame(data)
    df['ds'] = pd.to_datetime(df['ds'], utc=True)
    ...
    if df['y'].isnull().any():
```

**Fix**
- Convert records to `{'ds': ..., 'y': ...}` in the forecaster.
- Add a unit test for `prepare_data` and an integration test for training.

### 3) UI forecast can crash on import error
If the import fails before `logger` is defined, the `except` block uses an undefined variable.

```21:27:src/ui/pages/forecast.py
try:
    from utils.data_loader import load_data_from_database, generate_server_data
    from utils.base_logger import logger
    from app.prophet_forecaster import ProphetForecaster
except ImportError as e:
    logger.info(f"Ошибка импорта: {e}")
```

**Fix**
- Initialize `logger` before the try/except or replace with `st.warning`/`print`.
- Add a UI smoke test with missing DB modules.

### 4) UI forecast can crash due to uninitialized `data`
If `load_data_from_database` is falsy, `data` is never assigned but used later.

```80:114:src/ui/pages/forecast.py
        if load_data_from_database:
            try:
                data = load_data_from_database(start_date=start_date, end_date=end_date)
                st.success(f"Загружено {len(data)} записей из БД")
            except Exception as db_error:
                st.warning(f"Ошибка загрузки из БД: {db_error}")
                
        # Фильтруем по серверам этой АС
        if 'server' in data.columns and 'as_name' not in data.columns:
            data['as_name'] = data['server'].map(as_mapping)
```

**Fix**
- Initialize `data = generate_server_data()` before the branch or return early when loader is unavailable.

---

## High Severity

### 1) Database URL with password is logged

```19:22:src/app/connection.py
DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
logger.info(f"DATABASE_URL: {DATABASE_URL}")
```

**Fix**
- Log only host/port/db name.
- Mask the password if needed.

### 2) CORS configuration is insecure and invalid for credentials

```26:32:src/app/main.py
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**Fix**
- For production: allow specific origins.
- For development: set `allow_credentials=False` when using `["*"]`.

---

## Medium Severity

### 1) `__repr__` uses a non‑existent attribute
`ServerMetricsPredictions.__repr__` references `predicted_value`, but the field is `value_predicted`.

```172:178:src/app/models.py
    def __repr__(self):
        return (
            f"<ServerMetricsPrediction(vm='{self.vm}', "
            f"timestamp='{self.timestamp}', "
            f"metric='{self.metric}', "
            f"predicted_value={self.predicted_value}"
        )
```

**Fix**
- Replace with `self.value_predicted`.

### 2) Hardcoded Windows paths in UI
Found in `src/ui/main.py` and `src/ui/pages/forecast.py` (mapping file).
This breaks on macOS/Linux and in containers.

**Fix**
- Use `Path(__file__).parent` and build relative paths.
- Provide clear fallback and error messaging.

---

## Low Severity / Tech Debt

- Duplicate loggers (`base_logger.py` in root and `src/ui/utils/base_logger.py`).
- Typo in root `reqirements.txt`.
- Heavy use of `sys.path` manipulation in UI instead of packaging.
- Tests rely on SQLite while production uses PostgreSQL (UUID/type constraints may differ).

---

## Component‑level Assessment

### Backend API (`src/app`)
**Strengths**
- Clear separation of endpoints, CRUD, models, schemas.
- Good validation and error handling patterns.

**Weaknesses**
- Logging secrets, insecure CORS.
- Some duplicated logic across CRUD classes.

**Recommendations**
- Add service layer to centralize validations and business logic.
- Introduce repository patterns and standardize error mapping.

### Frontend UI (`src/ui`)
**Strengths**
- Rich visualizations, structured page layout.
- Effective use of `st.cache_data`.

**Weaknesses**
- Direct DB access bypasses API.
- Import/path handling is fragile and OS‑specific.

**Recommendations**
- Use API for data retrieval.
- Consolidate path handling and logging.

### Forecasting (`forecast/`)
**Strengths**
- Dedicated forecasting module, with model storage and metrics.

**Weaknesses**
- Critical data‑format bug.
- No tests, limited validation of input quality.

**Recommendations**
- Fix `ds/y` format and add tests.
- Add explicit minimum data checks, logging of data coverage.

### ETL / Utils (`utils/`)
**Strengths**
- Useful scripts for data load and preparation.

**Weaknesses**
- No CLI and no clear data pipeline orchestration.

**Recommendations**
- Provide CLI wrappers or Makefile tasks for repeatable loading.

### Tests (`tests/`)
**Strengths**
- CRUD and API coverage exists.

**Weaknesses**
- No tests for `forecast` or UI modules.
- Edge cases (large batch sizes, empty data, DB down) are missing.

**Recommendations**
- Add forecast unit/integration tests.
- Include negative tests and DB‑down scenarios.

### Docker (`docker/`, `docker-macos/`)
**Strengths**
- Clear separation of services.

**Weaknesses**
- Duplicated configs across OS folders.

**Recommendations**
- Consolidate via env‑specific overrides.

---

## Priority Fix Plan (1–2 days)
1) Fix batch prediction arguments.
2) Fix forecast data format (`ds/y`).
3) Fix UI forecast import and `data` initialization.
4) Remove password logging; fix CORS.
5) Replace hardcoded paths with relative paths.

---

## Final Notes
The project is very close to production readiness once the critical defects are fixed and security posture is improved. From an ML perspective, reliability in model training and prediction storage needs immediate attention.

