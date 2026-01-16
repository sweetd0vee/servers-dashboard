# Архитектура проекта и диаграммы

Документ описывает архитектуру AIOps Dashboard и содержит диаграммы для быстрого понимания компонентов, потоков данных и развертывания.

## Обзор системы

Проект состоит из:
- **Backend API**: FastAPI (`src/app`)
- **UI**: Streamlit (`src/ui`)
- **Forecasting**: Prophet и вспомогательные модули (`forecast`)
- **БД**: PostgreSQL
- **Инфраструктура**: Docker Compose, опционально HTTPd и Keycloak

## Высокоуровневая архитектура

```mermaid
graph TB
  Browser[Пользовательский браузер] --> UI[Streamlit UI]
  UI --> API[FastAPI API]
  API --> DB[(PostgreSQL)]
  API --> Models[(Model Storage)]
  UI --> DB
  API --> Forecast[Forecasting]
```

## Архитектура backend (FastAPI)

```mermaid
graph LR
  Main[main.py] --> Router[endpoints.py]
  Router --> DBCRUD[dbcrud.py]
  Router --> FactsCRUD[facts_crud.py]
  Router --> PredsCRUD[preds_crud.py]
  DBCRUD --> Models[models.py]
  FactsCRUD --> Models
  PredsCRUD --> Models
  Models --> Conn[connection.py]
```

## Архитектура UI (Streamlit)

```mermaid
graph TB
  MainUI[main.py] --> Pages[pages/*]
  Pages --> DataLoader[utils/data_loader.py]
  Pages --> Components[components/*]
  DataLoader --> API
  DataLoader --> DB
```

## Поток данных (фактические метрики)

```mermaid
sequenceDiagram
  participant U as User
  participant UI as Streamlit UI
  participant API as FastAPI
  participant CRUD as FactsCRUD
  participant DB as PostgreSQL

  U->>UI: Выбор VM/метрики
  UI->>API: GET /api/v1/facts
  API->>CRUD: get_metrics_fact()
  CRUD->>DB: SELECT
  DB-->>CRUD: rows
  CRUD-->>API: records
  API-->>UI: JSON
  UI-->>U: График/таблица
```

## Поток прогнозирования

```mermaid
sequenceDiagram
  participant U as User
  participant UI as Streamlit UI
  participant API as FastAPI
  participant F as ProphetForecaster
  participant CRUD as PredsCRUD
  participant DB as PostgreSQL
  participant FS as Model Storage

  U->>UI: Запрос прогноза
  UI->>API: POST /api/v1/predict
  API->>F: generate_forecast()
  alt Модель есть
    F->>FS: load_model()
  else Нет модели
    F->>CRUD: get_historical_metrics()
    CRUD->>DB: SELECT
    DB-->>CRUD: rows
    CRUD-->>F: data
    F->>FS: save_model()
  end
  F->>CRUD: save_prediction()
  CRUD->>DB: INSERT
  API-->>UI: прогноз
```

## Развертывание (Docker Compose)

```mermaid
graph TB
  subgraph Docker Network
    UI[dashboard-ui]
    API[dashboard-be]
    DB[(postgres)]
    LLM[llama-server]
    HTTPD[httpd-proxy]
  end

  UI --> API
  API --> DB
  UI --> DB
  HTTPD --> UI
  HTTPD --> API
  LLM --> API
```

## Хранилища и данные

```mermaid
graph LR
  Raw[Excel/CSV] --> Loader[utils/data_loader.py]
  Loader --> DB[(PostgreSQL)]
  DB --> UI
  DB --> Forecast[Forecasting]
  Forecast --> Preds[(Predictions)]
```

## Примечания
- Диаграммы отражают текущую структуру репозитория, без учета внешних интеграций, не включенных в запуск.
- Детальное описание и расширенные диаграммы есть в `docs/ARCHITECTURE.md`.
