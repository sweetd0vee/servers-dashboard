# Testing Guide

## Overview

A comprehensive test suite has been implemented for the AIOps Dashboard project, addressing the critical testing gap identified in the code review (previously graded 2/10).

## Test Structure

```
tests/
├── __init__.py                 # Package initialization
├── conftest.py                # Pytest fixtures and configuration
├── test_dbcrud.py             # Unit tests for DBCRUD (15 tests)
├── test_factscrud.py          # Unit tests for FactsCRUD (12 tests)
├── test_predscrud.py          # Unit tests for PredsCRUD (10 tests)
├── test_api_endpoints.py      # Integration tests for API (25+ tests)
├── requirements.txt           # Test-specific dependencies
└── README.md                  # Detailed test documentation
```

## Quick Start

### 1. Install Dependencies

```bash
# Install test.csv dependencies
pip install -r tests/requirements.txt

# Or install all dependencies (including tests)
pip install -r src/app/requirements.txt
```

### 2. Run Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src/app --cov-report=html

# Use the test.csv runner script
./run_tests.sh --coverage
```

## Test Coverage

### Unit Tests

#### DBCRUD Tests (`test_dbcrud.py`)
- ✅ Get all VMs
- ✅ Get metrics for VM
- ✅ Get data time range
- ✅ Get historical metrics
- ✅ Get latest metrics
- ✅ Get metrics by date range
- ✅ Database statistics
- ✅ Cleanup old data
- ✅ Detect missing data
- ✅ Calculate data completeness

#### FactsCRUD Tests (`test_factscrud.py`)
- ✅ Create metric fact
- ✅ Upsert behavior
- ✅ Batch create metrics
- ✅ Get metrics fact
- ✅ Get latest metrics
- ✅ Get metrics as DataFrame (Prophet format)
- ✅ Get metrics statistics
- ✅ Statistics with date range

#### PredsCRUD Tests (`test_predscrud.py`)
- ✅ Save prediction
- ✅ Upsert behavior
- ✅ Batch save predictions
- ✅ Get predictions
- ✅ Get future predictions
- ✅ Compare actual vs predicted
- ✅ Edge cases (no matches, etc.)

### Integration Tests

#### API Endpoints Tests (`test_api_endpoints.py`)

**Database Endpoints:**
- ✅ GET /vms
- ✅ GET /vms/{vm}/metrics
- ✅ GET /vms/{vm}/metrics/{metric}/time-range
- ✅ GET /stats
- ✅ POST /cleanup
- ✅ GET /vms/{vm}/metrics/{metric}/completeness
- ✅ GET /vms/{vm}/metrics/{metric}/missing-data

**Facts Endpoints:**
- ✅ POST /facts
- ✅ POST /facts/batch
- ✅ GET /facts
- ✅ GET /facts/latest
- ✅ GET /facts/statistics

**Predictions Endpoints:**
- ✅ POST /predictions
- ✅ POST /predictions/batch
- ✅ GET /predictions
- ✅ GET /predictions/future
- ✅ GET /predictions/compare

**Legacy Endpoints:**
- ✅ GET /latest_metrics
- ✅ GET /metrics

## Test Features

### 1. **Isolated Test Database**
- Uses SQLite in-memory database
- Each test gets a fresh database session
- No need for running PostgreSQL during tests
- Automatic cleanup after each test

### 2. **Comprehensive Fixtures**
- `db_session`: Fresh database session
- `sample_metrics_data`: Pre-populated metrics
- `sample_predictions_data`: Pre-populated predictions
- `sample_vm`, `sample_metric`: Test data constants
- `client`: FastAPI test client with overridden dependencies

### 3. **Error Handling Tests**
- Invalid input validation
- Missing data scenarios
- Edge cases (empty results, etc.)
- HTTP status code verification

### 4. **Coverage Reporting**
- Terminal output with missing lines
- HTML report for detailed analysis
- XML report for CI/CD integration

## Running Tests

### Basic Commands

```bash
# Run all tests
pytest

# Run specific test.csv file
pytest tests/test_dbcrud.py

# Run specific test.csv class
pytest tests/test_dbcrud.py::TestDBCRUD

# Run specific test.csv function
pytest tests/test_dbcrud.py::TestDBCRUD::test_get_all_vms

# Verbose output
pytest -v

# Show print statements
pytest -s
```

### With Coverage

```bash
# Terminal coverage report
pytest --cov=src/app --cov-report=term-missing

# HTML coverage report
pytest --cov=src/app --cov-report=html
open htmlcov/index.html

# XML coverage report (for CI)
pytest --cov=src/app --cov-report=xml
```

### Using Test Runner Script

```bash
# Run all tests
./run_tests.sh

# With coverage
./run_tests.sh --coverage

# Verbose output
./run_tests.sh --verbose

# Run only unit tests
./run_tests.sh --unit

# Run only integration tests
./run_tests.sh --integration

# Help
./run_tests.sh --help
```

## Test Configuration

### pytest.ini

Located at project root, contains:
- Test discovery patterns
- Coverage settings
- Markers for test categorization
- Output formatting options

### Key Settings

```ini
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
```

## Writing New Tests

### Example: Unit Test

```python
def test_my_function(db_session):
    """Test description"""
    crud = DBCRUD(db_session)
    result = crud.my_function()
    assert result == expected_value
```

### Example: Integration Test

```python
def test_api_endpoint(client, sample_metrics_data):
    """Test API endpoint"""
    response = client.get("/api/v1/vms")
    assert response.status_code == 200
    assert len(response.json()) > 0
```

## Best Practices

1. **Test Isolation**: Each test is independent
2. **Use Fixtures**: Leverage existing fixtures for setup
3. **Clear Assertions**: Use specific assertions with messages
4. **Descriptive Names**: Test names should explain what's tested
5. **Coverage**: Aim for 80%+ coverage on critical paths

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
        with:
          python-version: '3.12'
      - name: Install dependencies
        run: |
          pip install -r tests/requirements.txt
          pip install -r src/app/requirements.txt
      - name: Run tests
        run: pytest --cov=src/app --cov-report=xml
      - name: Upload coverage
        uses: codecov/codecov-action@v2
```

## Troubleshooting

### Import Errors

Ensure you're running from project root:
```bash
cd /path/to/dashboard
pytest
```

### Database Errors

Tests use SQLite in-memory. If you see PostgreSQL errors, check `conftest.py` is properly overriding connections.

### Coverage Not Working

Install pytest-cov:
```bash
pip install pytest-cov
```

## Test Statistics

- **Total Tests**: 60+ tests
- **Unit Tests**: 37 tests
- **Integration Tests**: 25+ tests
- **Coverage Target**: 80%+
- **Test Execution Time**: < 30 seconds

## Next Steps

1. ✅ Test suite created
2. ✅ Unit tests implemented
3. ✅ Integration tests implemented
4. ✅ Coverage reporting configured
5. ⏳ Add tests for forecasting module
6. ⏳ Add tests for anomaly detection
7. ⏳ Performance/load tests
8. ⏳ CI/CD pipeline integration

## Resources

- [Pytest Documentation](https://docs.pytest.org/)
- [FastAPI Testing](https://fastapi.tiangolo.com/tutorial/testing/)
- [Test Coverage Best Practices](https://coverage.readthedocs.io/)

---

*Last Updated: 2025-01-27*

