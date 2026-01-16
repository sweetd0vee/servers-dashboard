# Code Review (2026-01-16)

## Scope
- `src/app` (FastAPI, SQLAlchemy CRUD, schemas, DB connection)
- `forecast` (Prophet training, prediction, storage)
- `src/ui` (Streamlit UI)
- `tests`, `docs`, root config files

## Grading
Scale: A (excellent) → F (critical issues / not production-ready)

- **API & DB Layer (`src/app`) — B-**
  - Solid separation between endpoints and CRUD, reasonable validation, clear response models.
  - Weaknesses: batch operations and data completeness logic can be incorrect at scale, production concerns around auto table creation.
- **Forecasting / ML (`forecast`) — D**
  - Good structure (tuning, training, storage, prediction), but core data prep integration is broken and will fail at runtime.
- **UI (`src/ui`) — C**
  - Clean component layout, but a runtime error prevents loading styles.
- **Testing (`tests`) — C-**
  - CRUD coverage exists, but missing regression tests for batch predictions and forecasting flow.
- **Docs & Ops (`docs`, Docker configs) — B**
  - Good launch docs, architecture summary, testing guide.
  - Missing detailed code review doc (this file fills the gap).
- **Security & Config — C**
  - Defaults and CORS are permissive; acceptable for local but risky for production without guardrails.

## Findings (Ordered by Severity)

### Critical
1) **Batch predictions API crashes on every call**  
   - `src/app/preds_crud.py` → `save_predictions_batch()` passes `lower`/`upper` keyword args to `save_prediction()` which expects `lower_bound`/`upper_bound`.  
   - Result: `TypeError` at runtime; batch endpoint `/predictions/batch` is effectively broken.

2) **Forecast training path cannot run**  
   - `forecast/forecaster.py` builds dicts with `timestamp`/`value`, but `forecast/utils.py::prepare_data()` expects `ds`/`y`.  
   - Result: `KeyError` in data preparation, so training never succeeds.

### High
3) **Data completeness / missing-data analysis can be wrong on long ranges**  
   - `src/app/dbcrud.py` → `detect_missing_data()` and `calculate_data_completeness()` rely on `get_historical_metrics()` with default `limit=5000`.  
   - Result: missing intervals or completeness can be computed from a truncated dataset.

4) **Streamlit UI crashes in `main.py` when loading styles**  
   - `src/ui/main.py` uses `os.path` but `os` is not imported.  
   - Result: `NameError` before UI renders.

### Medium
5) **Batch writes are slow and partially applied**  
   - `FactsCRUD.create_metrics_fact_batch()` commits per record; failures are ignored.  
   - `PredsCRUD.save_predictions_batch()` also loops without transaction.  
   - Result: low throughput and inconsistent batches under failure.

6) **Predictions retrieval has no limit or pagination**  
   - `PredsCRUD.get_predictions()` can return unbounded rows; endpoints have no limit.  
   - Result: large responses and slow queries for long history.

7) **Value constraints may be too strict for non-percent metrics**  
   - Pydantic schemas constrain `value` and `value_predicted` to 0–100.  
   - Result: disk, network, or other metrics outside that range will 422.

### Low
8) **Auto table creation at import time**  
   - `src/app/main.py` calls `Base.metadata.create_all()` on import.  
   - Result: unexpected schema creation in production; migrations should own schema.

9) **Mixed logging practices**  
   - `dbcrud.py` uses `print()` in exception handling.  
   - Result: errors bypass structured logging.

10) **Security defaults are permissive**  
   - CORS allows `*` in API; default DB password is `postgres`.  
   - Result: unsafe for production if not overridden.

## Recommendations & Fixes

### Immediate fixes (should be applied next)
1) **Fix batch predictions keyword bug**  
   - Update `PredsCRUD.save_predictions_batch()` to call `save_prediction(..., lower_bound=..., upper_bound=...)`.  
   - Add regression test in `tests/test_predscrud.py` for batch input.

2) **Fix forecast data preparation**  
   - In `forecast/forecaster.py`, rename keys to `ds` and `y` (or update `prepare_data()` to accept `timestamp`/`value`).  
   - Add a test that runs `ProphetForecaster.train_or_load_model()` on a small fixture.

3) **Import `os` in Streamlit main**  
   - Add `import os` at top of `src/ui/main.py`.

### Short-term improvements (next iteration)
4) **Remove or raise limits for completeness detection**  
   - Add `limit=None` option in `get_historical_metrics()` and pass full range for completeness analysis.  
   - For large datasets, compute missing intervals in SQL or by windowed processing.

5) **Batch write performance**  
   - Use SQLAlchemy bulk insert/update or at least a single transaction per batch.  
   - Return per-item failures to clients for observability.

6) **Pagination and limits for predictions**  
   - Add `limit` (and optionally `offset`/cursor) to `/predictions` endpoint.

7) **Metric value ranges**  
   - Relax `Field(..., ge=0, le=100)` for metrics that are not percentages.  
   - Option: introduce per-metric validation based on `MetricType`.

### Long-term / production hardening
8) **Migrations over auto schema creation**  
   - Introduce Alembic and remove `Base.metadata.create_all()` from runtime.

9) **Security baseline**  
   - Restrict CORS to known UI origins.  
   - Require environment-specific DB credentials.

10) **Observability**  
   - Standardize logging, add request IDs, and surface failures in metrics.

## Testing Gaps
- No regression tests for batch predictions or forecast training.
- No tests for completeness/missing-data logic across large time windows.
- Consider basic load tests for endpoints returning large datasets.

## Summary
The API and DB layers are solid and well-structured, but the forecasting pipeline and batch prediction endpoint have blocking runtime bugs. Fixing these critical issues and improving batch processing and pagination will substantially improve reliability and scalability.
