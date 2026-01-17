<!--
README follows best practices: clear structure, launch steps,
transparent configuration, and links to deeper docs.
-->

# AIOps Dashboard

Monitoring and forecasting platform for server load: metrics collection,
analytics, and time-series prediction in one UI.

## Quick start

### Docker (recommended first run)
```bash
cd docker/all
docker-compose up -d
```

#### Docker for Windows/macOS
Windows (PowerShell/cmd):
```bat
docker\all\docker-compose-up.bat
docker\all\docker-compose-down.bat
```

macOS/Linux:
```bash
./docker/all/docker-compose-up.sh
./docker/all/docker-compose-down.sh
```

After startup:
- API: `http://localhost:8000` (Swagger: `/docs`, ReDoc: `/redoc`)
- UI: `http://localhost:8501`

### Local (without Docker)
```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

pip install -r src/app/requirements.txt
pip install -r src/ui/requirements.txt
```

```bash
cd src/app
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

```bash
cd ../ui
streamlit run main.py --server.port 8501
```

## Table of contents

- [Key features](#key-features)
- [Architecture](#architecture)
- [Requirements](#requirements)
- [Configuration](#configuration)
- [Run](#run)
- [API](#api)
- [Data workflows](#data-workflows)
- [Development](#development)
- [Testing](#testing)
- [Deployment](#deployment)
- [Best practices](#best-practices)
- [Troubleshooting](#troubleshooting)
- [Documentation](#documentation)
- [Contributing](#contributing)
- [License](#license)

## Key features

- Monitoring metrics (CPU, memory, disk, network) with historical visualization
- Time-series forecasting with Prophet and confidence intervals
- Server and metric analytics, actual vs predicted comparisons
- Optional Keycloak SSO integration for the UI

## Architecture

The system consists of three main parts:
- `src/app` — REST API (FastAPI)
- `src/ui` — web UI (Streamlit)
- `notebooks/forecast` — forecasting/ML utilities

Details: `docs/ARCHITECTURE.md` and `docs/ARCHITECTURE_SUMMARY.md`.

## Requirements

- Python 3.12+
- PostgreSQL 16+ (or Docker)
- Docker + Docker Compose (for containerized run)

## Configuration

### Environment variables (API)

The API reads DB settings from `.env` or environment variables:

```env
DB_HOST=localhost
DB_PORT=5432
DB_USER=postgres
DB_PASSWORD=postgres
DB_NAME=server_metrics
```

See `src/app/connection.py`.

### Keycloak (optional, UI)

```env
KEYCLOAK_URL=http://localhost:8087/keycloak
KEYCLOAK_URL_FOR_AUTH=http://localhost:8087/keycloak
KEYCLOAK_REDIRECT_URI=http://localhost:8501/dashboard
KEYCLOAK_REALM=srv
KEYCLOAK_CLIENT_ID=srv-keycloak-client
KEYCLOAK_CLIENT_SECRET=change-me
```

See `src/ui/auth.py`.

## Run

### Docker

Full stack:
```bash
cd docker/all
docker-compose up -d
```

Stop:
```bash
cd docker/all
docker-compose down
```

### Local

1) Start API:
```bash
cd src/app
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

2) Start UI:
```bash
cd src/ui
streamlit run main.py --server.port 8501
```

## API

Base URL: `http://localhost:8000/api/v1`

Key endpoints:
- `GET /vms` — list VMs
- `GET /facts` — actual metrics
- `GET /predictions` — forecasts
- `GET /predictions/compare` — actual vs predicted

Full list: `docs/API_ENDPOINTS.md`  
Interactive docs: `http://localhost:8000/docs`

## Data workflows

- Example data files live under `data/`
- ETL helpers live in `utils/` (see `utils/new_data.py` and `utils/prepare_data.py`)
- For large datasets, keep files outside Git and load via API or ETL

## Development

### Install dependencies

```bash
pip install -r src/app/requirements.txt
pip install -r src/ui/requirements.txt
pip install -r tests/requirements.txt
```

An aggregated list also exists: `reqirements.txt`.

### Code style

Recommended tools:
- `black` — formatting
- `flake8` — linting
- `mypy` — typing
- `isort` — import sorting (`pyproject.toml`)

```bash
black src/
flake8 src/
mypy src/
python -m isort src tests utils notebooks
```

## Testing

```bash
pytest
pytest --cov=src/app --cov-report=html
```

Windows helper: `run_tests.bat`  
Details: `docs/TESTING.md`

## Deployment

Production recommendations:
- Restrict CORS in `src/app/main.py`
- Use secrets via env/secret manager
- Set up HTTPS at the reverse proxy layer (`docker/httpd`)
- Enable centralized logging and metrics

## Best practices

- **Configuration**: keep secrets in env only
- **Data**: keep large files outside Git, load via API/ETL
- **Observability**: structured logs and metrics
- **Security**: minimize `allow_origins`, update dependencies regularly
- **Tests**: cover CRUD + forecasting scenarios, validate migrations

## Troubleshooting

- DB unavailable: verify `DB_*` and `postgres` availability
- API not responding: check container logs and port `8000`
- UI has no data: verify CORS and API availability

## Documentation

- `docs/ARCHITECTURE.md` — architecture
- `docs/API_ENDPOINTS.md` — API
- `docs/TESTING.md` — testing
- `docs/REVIEW_EN.md` — code review (EN)
- `docs/REVIEW_RU.md` — code review (RU)

## Contributing

1. Create a `feature/*` branch
2. Add tests and documentation
3. Open a Pull Request

## License

MIT — see `LICENSE`.

