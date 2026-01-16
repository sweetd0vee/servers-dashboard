# Architecture Summary - Quick Reference

## System Overview Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                        Web Browser                           │
└───────────────────────────┬─────────────────────────────────┘
                            │ HTTPS/HTTP
                            ▼
┌─────────────────────────────────────────────────────────────┐
│              Apache HTTPd (Reverse Proxy)                    │
│                    Port 80/443                                │
└───────┬──────────────┬──────────────┬───────────────────────┘
        │              │              │
        │ /api/*       │ /dashboard-ui/* │ /keycloak/*
        ▼              ▼              ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│  FastAPI     │  │  Streamlit    │  │  Keycloak    │
│  Backend     │  │  Frontend     │  │  Auth        │
│  :8000       │  │  :8501        │  │  :8087       │
└──────┬───────┘  └──────┬───────┘  └──────┬───────┘
       │                 │                  │
       └─────────────────┼──────────────────┘
                         │
                         ▼
              ┌──────────────────────┐
              │    PostgreSQL        │
              │    :5432             │
              └──────────────────────┘
```

## Component Layers

### Layer 1: Presentation
- **Streamlit UI** - Interactive dashboard
- **Components**: Header, Sidebar, Footer
- **Pages**: Fact, Forecast, Analysis

### Layer 2: API Gateway
- **Apache HTTPd** - Routing and SSL termination
- **Keycloak** - Authentication (configured)

### Layer 3: Application
- **FastAPI** - REST API endpoints
- **Business Logic**: CRUD operations, Forecasting, Anomaly Detection

### Layer 4: Data
- **PostgreSQL** - Time-series metrics storage
- **File System** - Model storage

## Data Flow Summary

```
External Data → Data Preparation → PostgreSQL
                                      │
                                      ├──→ API → UI (Display)
                                      │
                                      └──→ Forecasting Engine → Predictions → UI
```

## Key Technologies

| Layer | Technology | Version |
|-------|-----------|---------|
| Frontend | Streamlit | 1.29.0 |
| Backend | FastAPI | 0.104.1 |
| Database | PostgreSQL | 16.9 |
| ML | Prophet | 1.1.5 |
| Proxy | Apache HTTPd | 2.4 |
| Auth | Keycloak | 26.4.6 |
| Container | Docker | Latest |

## Database Tables

1. **server_metrics_fact** - Historical metrics
2. **server_metrics_predictions** - Forecasted metrics

## API Endpoints

- `GET /api/v1/metrics` - Retrieve metrics
- `GET /api/v1/latest_metrics` - Latest 24h metrics

## Docker Services

1. **httpd-proxy** - Reverse proxy
2. **postgres** - Database
3. **keycloak** - Authentication
4. **llama-server** - AI/ML service
5. **dashboard** - API (commented)
6. **dashboard-ui** - UI (commented)

## Network

- **Network Name**: servers-network
- **Type**: Bridge network
- **All services** communicate within this network

