# Test Suite Documentation

This directory contains the test suite for the AIOps Dashboard project.

## Test Structure

```
tests/
├── __init__.py
├── conftest.py              # Pytest fixtures and configuration
├── test_dbcrud.py          # Unit tests for DBCRUD
├── test_factscrud.py       # Unit tests for FactsCRUD
├── test_predscrud.py       # Unit tests for PredsCRUD
├── test_api_endpoints.py   # Integration tests for API endpoints
└── requirements.txt        # Test-specific dependencies
```

## Running Tests

### Install Test Dependencies

```bash
# From project root
pip install -r tests/requirements.txt

# Or install all dependencies including tests
pip install -r src/app/requirements.txt
```

### Run All Tests

```bash
# From project root
pytest

# With coverage report
pytest --cov=src/app --cov-report=html

# Verbose output
pytest -v

# Run specific test.csv file
pytest tests/test_dbcrud.py

# Run specific test.csv class
pytest tests/test_dbcrud.py::TestDBCRUD

# Run specific test.csv function
pytest tests/test_dbcrud.py::TestDBCRUD::test_get_all_vms
```

### Run with Markers

```bash
# Run only unit tests
pytest -m unit

# Run only integration tests
pytest -m integration

# Skip slow tests
pytest -m "not slow"
```

## Test Coverage

Generate coverage reports:

```bash
# Terminal report
pytest --cov=src/app --cov-report=term-missing

# HTML report (opens in browser)
pytest --cov=src/app --cov-report=html
open htmlcov/index.html

# XML report (for CI/CD)
pytest --cov=src/app --cov-report=xml
```

## Test Database

Tests use an in-memory SQLite database (`sqlite:///:memory:`) to avoid requiring a running PostgreSQL instance. This is configured in `conftest.py`.

### Fixtures

Key fixtures available in `conftest.py`:

- `db_session`: Fresh database session for each test
- `override_get_db`: Override FastAPI dependency
- `sample_vm`: Sample VM name
- `sample_metric`: Sample metric name
- `sample_metric_fact`: Sample metric fact data
- `sample_metrics_data`: Pre-populated metrics in database
- `sample_predictions_data`: Pre-populated predictions in database

## Writing New Tests

### Unit Test Example

```python
def test_my_function(db_session):
    """Test description"""
    crud = DBCRUD(db_session)
    result = crud.my_function()
    assert result == expected_value
```

### Integration Test Example

```python
def test_api_endpoint(client, sample_metrics_data):
    """Test API endpoint"""
    response = client.get("/api/v1/vms")
    assert response.status_code == 200
    assert len(response.json()) > 0
```

## Test Categories

- **Unit Tests**: Test individual functions/classes in isolation
  - `test_dbcrud.py`
  - `test_factscrud.py`
  - `test_predscrud.py`

- **Integration Tests**: Test API endpoints with full request/response cycle
  - `test_api_endpoints.py`

## Best Practices

1. **Isolation**: Each test should be independent and not rely on other tests
2. **Fixtures**: Use fixtures for common setup/teardown
3. **Naming**: Use descriptive test names that explain what is being tested
4. **Assertions**: Use specific assertions with clear error messages
5. **Cleanup**: Tests automatically clean up (database is reset per test)

## Continuous Integration

Tests can be integrated into CI/CD pipelines:

```yaml
# Example GitHub Actions
- name: Run tests
  run: |
    pip install -r tests/requirements.txt
    pytest --cov=src/app --cov-report=xml
```

## Troubleshooting

### Import Errors

If you get import errors, ensure you're running from the project root:

```bash
cd /path/to/dashboard
pytest
```

### Database Errors

Tests use SQLite in-memory database. If you see PostgreSQL connection errors, check that `conftest.py` is properly overriding the database connection.

### Coverage Not Working

Ensure pytest-cov is installed:

```bash
pip install pytest-cov
```

## Current Test Coverage

Run tests with coverage to see current coverage:

```bash
pytest --cov=src/app --cov-report=term-missing
```

Target: 80%+ coverage for production-ready code.

---

*Last Updated: 2025-01-27*

