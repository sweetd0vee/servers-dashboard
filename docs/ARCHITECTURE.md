# Архитектура проекта
## AIOps Dashboard - Система мониторинга и прогнозирования нагрузки серверов

Документация описывает архитектуру системы, компоненты, потоки данных и структуру развертывания приложения для мониторинга и прогнозирования метрик серверов.

**Последнее обновление:** 2026-01-19  
**Версия:** 3.0

---

## Содержание

1. [Обзор системы](#обзор-системы)
2. [Высокоуровневая архитектура](#высокоуровневая-архитектура)
3. [Архитектура компонентов](#архитектура-компонентов)
4. [Диаграммы потоков данных](#диаграммы-потоков-данных)
5. [Схема базы данных](#схема-базы-данных)
6. [Архитектура развертывания](#архитектура-развертывания)
7. [Технологический стек](#технологический-стек)
8. [Архитектура тестирования](#архитектура-тестирования)
9. [Обработка ошибок](#обработка-ошибок)
10. [Модуль прогнозирования](#модуль-прогнозирования)

---

## Обзор системы

AIOps Dashboard - полнофункциональное приложение для мониторинга и прогнозирования метрик серверов с использованием машинного обучения.

### Основные компоненты

- **Backend API**: REST API на базе FastAPI с обработкой ошибок и валидацией
- **Frontend UI**: Интерактивный дашборд на Streamlit с прямым доступом к БД
- **База данных**: PostgreSQL для хранения временных рядов метрик
- **Forecasting Engine**: Модуль прогнозирования на базе Prophet
- **Testing Suite**: Комплексное тестовое покрытие на pytest
- **ETL Pipeline**: Инструменты для загрузки и подготовки данных
- **Reverse Proxy**: Apache HTTPd для маршрутизации и SSL

---

## Высокоуровневая архитектура

```mermaid
graph TB
    subgraph "Клиентский слой"
        Browser[Веб-браузер]
    end
    
    subgraph "Reverse Proxy"
        HTTPd[Apache HTTPd<br/>Порт 80/443]
    end
    
    subgraph "Слой приложений"
        API[FastAPI Backend<br/>Порт 8000<br/>REST API]
        UI[Streamlit UI<br/>Порт 8501<br/>Интерактивный дашборд]
    end
    
    subgraph "Слой сервисов"
        Auth[Keycloak<br/>Порт 8087<br/>Опционально]
        Forecast[Prophet Forecaster<br/>ML прогнозирование]
    end
    
    subgraph "Слой данных"
        DB[(PostgreSQL<br/>Порт 5432<br/>Временные ряды)]
        Models[Хранилище моделей<br/>Файловая система]
    end
    
    subgraph "ETL Pipeline"
        ETL[Загрузка данных<br/>prepare_data.py<br/>data_loader.py]
    end
    
    Browser -->|HTTPS/HTTP| HTTPd
    HTTPd -->|/api/*| API
    HTTPd -->|/dashboard-ui/*| UI
    HTTPd -.->|/keycloak/*| Auth
    
    API -->|Чтение/Запись| DB
    UI -->|Прямой доступ| DB
    UI -->|API вызовы| API
    
    API -->|Использует| Forecast
    Forecast -->|Загрузка/Сохранение| Models
    Forecast -->|Чтение данных| DB
    
    ETL -->|Загрузка метрик| DB
    
    style Browser fill:#e1f5ff
    style HTTPd fill:#fff4e1
    style API fill:#e8f5e9
    style UI fill:#ffe6cc
    style DB fill:#f3e5f5
    style Forecast fill:#fff9c4
    style ETL fill:#e0f2f1
```

---

## Архитектура компонентов

### Backend API (FastAPI)

```mermaid
graph LR
    subgraph "API слой"
        Main[main.py<br/>FastAPI приложение]
        Endpoints[endpoints.py<br/>REST эндпоинты<br/>Валидация]
    end
    
    subgraph "Бизнес-логика"
        DBCRUD[dbcrud.py<br/>Базовый CRUD]
        FactsCRUD[facts_crud.py<br/>Фактические метрики]
        PredsCRUD[preds_crud.py<br/>Прогнозы]
        Anomaly[anomaly_detector.py<br/>Детектор аномалий]
    end
    
    subgraph "Модели данных"
        Models[models.py<br/>SQLAlchemy ORM<br/>ServerMetricsFact<br/>ServerMetricsPredictions]
        Schemas[schemas.py<br/>Pydantic схемы<br/>Валидация]
    end
    
    subgraph "Инфраструктура"
        Conn[connection.py<br/>Подключение к БД<br/>SessionLocal]
        Logger[base_logger.py<br/>Логирование]
    end
    
    Main --> Endpoints
    Endpoints --> FactsCRUD
    Endpoints --> PredsCRUD
    Endpoints --> DBCRUD
    Endpoints --> Anomaly
    
    FactsCRUD --> Models
    PredsCRUD --> Models
    DBCRUD --> Models
    
    Models --> Conn
    FactsCRUD --> Conn
    
    Endpoints --> Schemas
    Main --> Logger
    
    style Main fill:#4caf50
    style Endpoints fill:#81c784
    style Models fill:#2196f3
    style Conn fill:#9e9e9e
```

### Frontend UI (Streamlit)

```mermaid
graph TB
    subgraph "UI точка входа"
        MainUI[main.py<br/>Streamlit приложение<br/>Табы]
    end
    
    subgraph "Страницы"
        Fact[fact.py<br/>Фактические метрики<br/>Визуализация]
        Forecast[forecast.py<br/>Прогнозирование<br/>Prophet интеграция]
        Analysis[analysis.py<br/>Анализ по серверам]
        ASAnalysis[as_analysis.py<br/>Анализ по АС]
    end
    
    subgraph "Компоненты"
        Header[header.py<br/>Заголовок]
        Sidebar[sidebar.py<br/>Боковая панель]
        Footer[footer.py<br/>Подвал]
        HeatmapCPU[heatmap_as_cpu.py<br/>Тепловая карта CPU]
        HeatmapMem[heatmap_as_mem.py<br/>Тепловая карта RAM]
    end
    
    subgraph "Утилиты"
        DataLoader[data_loader.py<br/>Загрузка из БД<br/>Основной источник]
        DataGen[data_generator.py<br/>Генератор данных<br/>Fallback]
        AlertRules[alert_rules.py<br/>Правила алертов]
        AlertAnalyzer[alert_analyzer.py<br/>Анализатор алертов]
    end
    
    MainUI --> Fact
    MainUI --> Forecast
    MainUI --> Analysis
    MainUI --> ASAnalysis
    
    MainUI --> Header
    MainUI --> Sidebar
    MainUI --> Footer
    
    Fact --> DataLoader
    Forecast --> DataLoader
    Analysis --> DataLoader
    ASAnalysis --> HeatmapCPU
    ASAnalysis --> HeatmapMem
    
    Fact --> AlertRules
    Analysis --> AlertAnalyzer
    
    DataLoader -->|Приоритет| DB[(PostgreSQL)]
    DataLoader -.->|Fallback| DataGen
    
    style MainUI fill:#ff6b6b
    style Forecast fill:#ffa8a8
    style DataLoader fill:#51cf66
    style DataGen fill:#ffd43b
```

### Модуль прогнозирования (Prophet)

```mermaid
graph TB
    subgraph "Forecaster модуль"
        Forecaster[forecaster.py<br/>ProphetForecaster<br/>Главный интерфейс]
        
        Training[model_training.py<br/>Обучение моделей<br/>Валидация]
        Tuning[model_tuning.py<br/>Подбор гиперпараметров<br/>Cross-validation]
        Prediction[model_prediction.py<br/>Генерация прогнозов]
        
        Storage[storage.py<br/>Сохранение/загрузка<br/>моделей]
        Utils[utils.py<br/>Подготовка данных<br/>Метрики качества]
        Config[config.py<br/>Конфигурация<br/>Параметры]
        
        DBUtils[db_utils.py<br/>Работа с БД<br/>CRUD операции]
        Evaluation[evaluation.py<br/>Оценка качества<br/>MAPE, MAE, RMSE]
    end
    
    Forecaster --> Training
    Forecaster --> Tuning
    Forecaster --> Prediction
    Forecaster --> Storage
    
    Training --> Utils
    Tuning --> Utils
    Prediction --> Utils
    
    Forecaster --> Config
    Forecaster --> DBUtils
    
    Training --> Evaluation
    Tuning --> Evaluation
    
    DBUtils --> DB[(PostgreSQL)]
    Storage --> FileSystem[Файловая система]
    
    style Forecaster fill:#ff9800
    style Training fill:#ffb74d
    style Tuning fill:#ffb74d
    style Prediction fill:#ffb74d
    style Storage fill:#9e9e9e
```

---

## Диаграммы потоков данных

### Загрузка метрик (Fact Metrics)

```mermaid
sequenceDiagram
    participant User as Пользователь
    participant UI as Streamlit UI
    participant Loader as data_loader.py
    participant CRUD as FactsCRUD
    participant DB as PostgreSQL
    
    User->>UI: Выбирает VM и метрику
    UI->>Loader: load_data_from_database()
    
    alt База данных доступна
        Loader->>CRUD: get_metrics_fact(vm, metric, dates)
        CRUD->>DB: SELECT запрос
        DB-->>CRUD: Результаты
        CRUD-->>Loader: List[ServerMetricsFact]
        Loader->>Loader: Преобразование в DataFrame
        Loader-->>UI: DataFrame
    else База недоступна
        Loader->>Loader: generate_server_data()
        Loader-->>UI: Mock DataFrame
    end
    
    UI->>UI: Визуализация (Plotly)
    UI-->>User: Графики метрик
```

### Генерация прогноза

```mermaid
sequenceDiagram
    participant User as Пользователь
    participant UI as Forecast Page
    participant Forecaster as ProphetForecaster
    participant Training as model_training
    participant Tuning as model_tuning
    participant Storage as storage
    participant DB as PostgreSQL
    
    User->>UI: Выбирает АС, метрику, период
    UI->>UI: Загружает маппинг серверов на АС
    UI->>DB: Загружает исторические данные
    DB-->>UI: DataFrame метрик
    
    loop Для каждого сервера в АС
        UI->>UI: prepare_data_for_prophet()
        UI->>Forecaster: generate_forecast_for_server()
        
        Forecaster->>Tuning: tune_hyperparameters()
        Tuning->>Tuning: Cross-validation / Holdout
        Tuning-->>Forecaster: best_params
        
        Forecaster->>Training: train_model(data, params)
        Training->>Training: Prophet.fit()
        Training-->>Forecaster: trained_model, metrics
        
        Forecaster->>Forecaster: predict(periods, freq)
        Forecaster->>Storage: save_model()
        
        Forecaster-->>UI: forecast_df, quality_metrics
        UI->>UI: Визуализация (Plotly)
    end
    
    UI->>UI: Агрегация прогнозов по АС
    UI->>UI: Анализ рисков
    UI-->>User: Графики + Рекомендации
```

### ETL Pipeline

```mermaid
sequenceDiagram
    participant Source as Источник данных<br/>(Excel/CSV)
    participant Prep as prepare_data.py
    participant Loader as data_loader.py
    participant API as FastAPI
    participant CRUD as FactsCRUD
    participant DB as PostgreSQL
    
    Source->>Prep: Чтение файла
    Prep->>Prep: Валидация и трансформация
    Prep->>Prep: Обработка timestamp
    Prep-->>Loader: DataFrame
    
    Loader->>API: POST /api/v1/facts/batch
    API->>API: Валидация (Pydantic)
    
    API->>CRUD: create_metrics_fact_batch()
    
    loop Для каждой метрики
        CRUD->>DB: INSERT INTO server_metrics_fact
        alt Дубликат
            DB-->>CRUD: IntegrityError
            CRUD->>CRUD: Пропуск (skip)
        else Успех
            DB-->>CRUD: Success
        end
    end
    
    CRUD-->>API: created_count
    API-->>Loader: BatchCreateResponse
    Loader-->>Source: Статус загрузки
```

---

## Схема базы данных

### ER-диаграмма

```mermaid
erDiagram
    ServerMetricsFact ||--o{ ServerMetricsPredictions : "связаны по vm+metric"
    
    ServerMetricsFact {
        uuid id PK "Уникальный идентификатор"
        string vm "Имя виртуальной машины"
        datetime timestamp "Временная метка (UTC)"
        string metric "Название метрики"
        decimal value "Значение метрики (0-100)"
        datetime created_at "Время создания записи"
    }
    
    ServerMetricsPredictions {
        uuid id PK "Уникальный идентификатор"
        string vm "Имя виртуальной машины"
        datetime timestamp "Временная метка прогноза"
        string metric "Название метрики"
        decimal value_predicted "Прогнозное значение"
        decimal lower_bound "Нижняя граница (80% CI)"
        decimal upper_bound "Верхняя граница (80% CI)"
        datetime created_at "Время создания прогноза"
    }
```

### Таблицы и индексы

#### server_metrics_fact

**Назначение**: Хранение фактических метрик серверов (CPU, RAM, Disk, Network)

**Структура**:
- `id` (UUID) - первичный ключ
- `vm` (VARCHAR 255) - имя виртуальной машины, индексировано
- `timestamp` (TIMESTAMP WITH TIMEZONE) - временная метка, индексировано
- `metric` (VARCHAR 255) - название метрики (cpu.usage.average, mem.usage.average)
- `value` (DECIMAL 20,5) - значение метрики, индексировано
- `created_at` (TIMESTAMP WITH TIMEZONE) - время создания записи

**Ограничения**:
- `UNIQUE (vm, timestamp, metric)` - уникальная комбинация
- `CHECK (timestamp <= CURRENT_TIMESTAMP)` - метка не из будущего
- Составной индекс: `idx_vm_timestamp_metric (vm, timestamp, metric)`

#### server_metrics_predictions

**Назначение**: Хранение прогнозов метрик

**Структура**:
- `id` (UUID) - первичный ключ
- `vm` (VARCHAR 255) - имя виртуальной машины, индексировано
- `timestamp` (TIMESTAMP WITH TIMEZONE) - временная метка прогноза, индексировано
- `metric` (VARCHAR 255) - название метрики
- `value_predicted` (DECIMAL 20,5) - прогнозное значение
- `lower_bound` (DECIMAL 20,5) - нижняя граница доверительного интервала
- `upper_bound` (DECIMAL 20,5) - верхняя граница доверительного интервала
- `created_at` (TIMESTAMP WITH TIMEZONE) - время создания прогноза

**Ограничения**:
- `UNIQUE (vm, timestamp, metric)` - уникальная комбинация прогноза
- Составной индекс: `idx_vm_timestamp_metric_pred (vm, timestamp, metric)`

---

## Архитектура развертывания

### Docker Compose конфигурация

```mermaid
graph TB
    subgraph "Docker Network: servers-network"
        subgraph "Веб-слой"
            HTTPd[Apache HTTPd<br/>Контейнер: httpd-proxy<br/>Порты: 80, 443<br/>SSL терминация]
        end
        
        subgraph "Контейнеры приложений"
            API[FastAPI App<br/>Контейнер: dashboard<br/>Порт: 8000<br/>uvicorn]
            UI[Streamlit UI<br/>Контейнер: dashboard-ui<br/>Порт: 8501<br/>streamlit]
        end
        
        subgraph "Сервисы"
            Keycloak[Keycloak<br/>Контейнер: keycloak<br/>Порт: 8087<br/>Опционально]
        end
        
        subgraph "База данных"
            Postgres[PostgreSQL 16.9<br/>Контейнер: postgres<br/>Порт: 5432]
        end
    end
    
    subgraph "Хост томы"
        ModelStorage[Хранилище моделей<br/>./notebooks/models]
        PostgresData[Данные PostgreSQL<br/>~/docker-share/postgres-data-server]
        SSL[SSL сертификаты<br/>./docker/httpd/data/letsencrypt]
    end
    
    HTTPd -->|/api/*| API
    HTTPd -->|/dashboard-ui/*| UI
    HTTPd -.->|/keycloak/*| Keycloak
    
    API -->|Подключение| Postgres
    UI -->|Прямое подключение| Postgres
    UI -->|API вызовы| API
    
    API -->|Чтение/Запись| ModelStorage
    Postgres -->|Persist| PostgresData
    HTTPd -->|SSL Certs| SSL
    
    style HTTPd fill:#ff9800
    style API fill:#4caf50
    style UI fill:#2196f3
    style Postgres fill:#9c27b0
```

### Переменные окружения

#### Backend API (.env)
```env
DB_HOST=postgres
DB_PORT=5432
DB_USER=postgres
DB_PASSWORD=secure_password
DB_NAME=server_metrics

# Опционально
LOG_LEVEL=INFO
CORS_ORIGINS=*
```

#### Frontend UI (.env)
```env
# Подключение к БД (прямое)
DB_HOST=postgres
DB_PORT=5432
DB_USER=postgres
DB_PASSWORD=secure_password
DB_NAME=server_metrics

# API Backend (для некоторых операций)
API_URL=http://dashboard:8000

# Keycloak (опционально)
KEYCLOAK_URL=http://keycloak:8087/keycloak
KEYCLOAK_REALM=srv
KEYCLOAK_CLIENT_ID=srv-keycloak-client
KEYCLOAK_CLIENT_SECRET=change-me
```

---

## Технологический стек

### Backend

| Компонент | Технология | Версия | Назначение |
|-----------|-----------|--------|------------|
| Framework | FastAPI | 0.104.1 | REST API, асинхронная обработка |
| ORM | SQLAlchemy | 2.0.23 | Работа с PostgreSQL |
| Валидация | Pydantic | 2.5.0 | Схемы данных, валидация |
| ASGI Server | Uvicorn | 0.24.0 | Запуск FastAPI приложения |
| База данных | PostgreSQL | 16.9 | Хранение временных рядов |

### Frontend

| Компонент | Технология | Версия | Назначение |
|-----------|-----------|--------|------------|
| Framework | Streamlit | 1.29.0 | Интерактивный дашборд |
| Визуализация | Plotly | 5.18.0 | Графики и диаграммы |
| Данные | Pandas | 2.1.4 | Обработка DataFrame |
| Вычисления | NumPy | 1.26.2 | Численные операции |

### Machine Learning

| Компонент | Технология | Версия | Назначение |
|-----------|-----------|--------|------------|
| Прогнозирование | Prophet | 1.1.5 | Временные ряды, тренды, сезонность |
| Оптимизация | scikit-learn | - | Метрики качества (MAPE, MAE, RMSE) |

### Testing

| Компонент | Технология | Версия | Назначение |
|-----------|-----------|--------|------------|
| Test Framework | Pytest | 7.4.3 | Unit и интеграционные тесты |
| Coverage | pytest-cov | - | Покрытие кода тестами |
| HTTP Client | httpx | - | Тестирование API |
| Test DB | SQLite | - | In-memory база для тестов |

### Infrastructure

| Компонент | Технология | Назначение |
|-----------|-----------|------------|
| Containerization | Docker + Docker Compose | Контейнеризация сервисов |
| Reverse Proxy | Apache HTTPd 2.4 | Маршрутизация, SSL |
| Auth (опционально) | Keycloak 26.4.6 | SSO, управление доступом |

---

## Архитектура тестирования

### Структура тестов

```
tests/
├── __init__.py
├── conftest.py              # Фикстуры pytest
├── test_dbcrud.py          # Unit-тесты DBCRUD
├── test_factscrud.py       # Unit-тесты FactsCRUD
├── test_predscrud.py       # Unit-тесты PredsCRUD
├── test_api_endpoints.py   # Интеграционные тесты API
├── test_anomaly_detector.py
├── test_prophet_forecaster_prepare.py
├── test_ui_alert_analyzer.py
├── test_ui_alert_rules.py
├── test_ui_data_loader.py
├── test_utils_prepare_data.py
├── requirements.txt
└── README.md
```

### Покрытие тестами

```mermaid
graph TB
    subgraph "Unit Tests"
        TestCRUD[test_dbcrud.py<br/>Тесты CRUD операций]
        TestFacts[test_factscrud.py<br/>Тесты фактических метрик]
        TestPreds[test_predscrud.py<br/>Тесты прогнозов]
        TestAnomaly[test_anomaly_detector.py<br/>Тесты детектора аномалий]
    end
    
    subgraph "Integration Tests"
        TestAPI[test_api_endpoints.py<br/>Тесты REST API<br/>Эндпоинты]
    end
    
    subgraph "UI Tests"
        TestAlerts[test_ui_alert_*.py<br/>Тесты алертов]
        TestLoader[test_ui_data_loader.py<br/>Тесты загрузчика данных]
    end
    
    subgraph "Test Infrastructure"
        Conftest[conftest.py<br/>Фикстуры<br/>TestDB SessionLocal]
        TestDB[(SQLite In-Memory<br/>Тестовая БД)]
    end
    
    TestCRUD --> Conftest
    TestFacts --> Conftest
    TestPreds --> Conftest
    TestAPI --> Conftest
    
    Conftest --> TestDB
    
    style TestAPI fill:#ef9a9a
    style Conftest fill:#e1bee7
    style TestDB fill:#ce93d8
```

### Запуск тестов

```bash
# Все тесты
pytest

# С покрытием
pytest --cov=src/app --cov-report=html

# Конкретный файл
pytest tests/test_api_endpoints.py

# Verbose режим
pytest -v

# Windows
run_tests.bat
```

---

## Обработка ошибок

### Уровни обработки

```mermaid
graph TB
    subgraph "API слой"
        Endpoint[API Endpoint]
        Validator[Pydantic валидация]
    end
    
    subgraph "Helper слой"
        DateVal[validate_date_range<br/>Валидация дат]
        ErrorHandler[handle_database_error<br/>Обработка ошибок БД]
        SchemaConv[db_metric_to_schema<br/>Конвертация схем]
    end
    
    subgraph "Бизнес-логика"
        CRUD[CRUD операции]
    end
    
    subgraph "База данных"
        DB[(PostgreSQL)]
    end
    
    subgraph "Логирование"
        Logger[base_logger.py<br/>Структурированные логи]
    end
    
    Endpoint --> Validator
    Validator -->|Valid| DateVal
    DateVal -->|Valid| CRUD
    CRUD --> DB
    
    CRUD -->|SQLAlchemyError| ErrorHandler
    DB -->|IntegrityError| ErrorHandler
    ErrorHandler --> Logger
    ErrorHandler -->|HTTPException| Endpoint
    
    CRUD -->|Success| SchemaConv
    SchemaConv --> Endpoint
    
    style Endpoint fill:#4caf50
    style Validator fill:#81c784
    style ErrorHandler fill:#ff9800
    style Logger fill:#9e9e9e
```

### Типы ошибок

| HTTP Code | Тип ошибки | Причина | Обработка |
|-----------|-----------|---------|-----------|
| 400 | Bad Request | Невалидные параметры, пустые значения | Pydantic валидация |
| 404 | Not Found | VM/метрика не найдена | CRUD слой |
| 409 | Conflict | Дубликаты, нарушение уникальности | IntegrityError обработка |
| 500 | Internal Server Error | Ошибки БД, непредвиденные исключения | handle_database_error() |

### Константы и лимиты

```python
# Из endpoints.py
DEFAULT_LIMIT = 5000          # Лимит по умолчанию
MAX_LIMIT = 10000             # Максимальный лимит
DEFAULT_HOURS = 24            # Часы по умолчанию
MAX_HOURS = 720               # Макс часы (30 дней)
DEFAULT_DAYS_TO_KEEP = 90     # Хранение данных
MAX_DAYS_TO_KEEP = 365        # Максимальное хранение
MIN_INTERVAL_MINUTES = 1      # Минимальный интервал
MAX_INTERVAL_MINUTES = 1440   # Макс интервал (24 часа)
DEFAULT_INTERVAL_MINUTES = 30 # Интервал по умолчанию
```

---

## Модуль прогнозирования

### Архитектура ProphetForecaster

#### Основные возможности

1. **Обучение моделей** с кросс-валидацией
2. **Подбор гиперпараметров** (Grid Search с параллелизацией)
3. **Временные признаки**: час, день недели, месяц, квартал, выходные и т.д.
4. **Оценка качества**: MAPE, MAE, RMSE
5. **Сохранение/загрузка** обученных моделей
6. **Генерация прогнозов** с доверительными интервалами

#### Гиперпараметры для подбора

```python
# Из forecast.py
param_grid = {
    'seasonality_mode': ['additive', 'multiplicative'],
    'changepoint_prior_scale': [0.01, 0.05, 0.1, 0.2],
    'seasonality_prior_scale': [3.0, 5.0, 10.0, 15.0],
    'holidays_prior_scale': [5.0, 10.0],
    'changepoint_range': [0.8, 0.9, 0.95],
    'n_changepoints': [15, 25, 35],
    'daily_seasonality': True,
    'weekly_seasonality': True
}
```

#### Временные признаки (Регрессоры)

- `hour` - час дня (0-23)
- `day_of_week` - день недели (0-6)
- `day_of_month` - день месяца (1-31)
- `week_of_year` - неделя года (1-52)
- `month` - месяц (1-12)
- `quarter` - квартал (1-4)
- `is_weekend` - выходной день (0/1)
- `is_month_start` - начало месяца (0/1)
- `is_month_end` - конец месяца (0/1)
- `is_quarter_start` - начало квартала (0/1)
- `is_quarter_end` - конец квартала (0/1)
- `is_year_start` - начало года (0/1)
- `is_year_end` - конец года (0/1)

#### Процесс прогнозирования

```mermaid
sequenceDiagram
    participant UI as Forecast UI
    participant Forecaster as generate_forecast_for_server
    participant Tuning as Hyperparameter Tuning
    participant Prophet as Prophet Model
    participant Evaluation as Evaluation
    
    UI->>Forecaster: prophet_df, forecast_days
    Forecaster->>Forecaster: add_time_features()
    
    alt Достаточно данных для CV
        Forecaster->>Tuning: evaluate_with_cv(param_grid)
        Tuning->>Tuning: Cross-validation (n_splits)
        loop Для каждой комбинации параметров
            Tuning->>Prophet: train(params)
            Prophet-->>Tuning: model
            Tuning->>Evaluation: calculate_mape()
            Evaluation-->>Tuning: score
        end
        Tuning-->>Forecaster: best_params, best_score
    else Мало данных
        Forecaster->>Tuning: evaluate_with_holdout()
        Tuning->>Prophet: train(params)
        Prophet-->>Tuning: model
        Tuning->>Evaluation: calculate_mape(val_data)
        Evaluation-->>Tuning: score
        Tuning-->>Forecaster: best_params, best_score
    end
    
    Forecaster->>Prophet: train(all_data, best_params)
    Prophet-->>Forecaster: final_model
    
    Forecaster->>Prophet: make_future_dataframe(periods)
    Prophet->>Forecaster: future_df
    Forecaster->>Prophet: predict(future_df + features)
    Prophet-->>Forecaster: forecast
    
    Forecaster->>Evaluation: quality_metrics(history)
    Evaluation-->>Forecaster: MAPE, MAE, RMSE
    
    Forecaster-->>UI: forecast, metrics
```

### Метрики качества

#### MAPE (Mean Absolute Percentage Error)

```python
MAPE = mean(|actual - predicted| / actual) × 100%
```

**Интерпретация**:
- MAPE < 10% - отличное качество (зеленый)
- MAPE 10-20% - хорошее качество (желтый)
- MAPE 20-30% - среднее качество (оранжевый)
- MAPE > 30% - низкое качество (красный)

#### MAE (Mean Absolute Error)

```python
MAE = mean(|actual - predicted|)
```

#### RMSE (Root Mean Squared Error)

```python
RMSE = sqrt(mean((actual - predicted)²))
```

### Анализ рисков

Автоматическая оценка уровня риска на основе прогнозной нагрузки:

| Уровень риска | Диапазон нагрузки | Рекомендации |
|--------------|-------------------|--------------|
| 🟩 Низкий | < 50% | Система стабильна, плановое обслуживание |
| 🟨 Средний | 50-70% | Мониторинг, подготовка к масштабированию |
| 🟧 Высокий | 70-85% | Планирование ресурсов, настройка алертов |
| 🟥 Критический | > 85% | Срочное масштабирование, балансировка нагрузки |

---

## API Endpoints

### Основные группы

```mermaid
graph LR
    API[FastAPI App<br/>/api/v1] --> DB_Ops[Database Ops<br/>/vms, /stats, /cleanup]
    API --> Facts[Fact Metrics<br/>/facts, /facts/batch]
    API --> Preds[Predictions<br/>/predictions, /predictions/batch]
    API --> Legacy[Legacy<br/>/metrics, /latest_metrics]
    
    style API fill:#4caf50
    style DB_Ops fill:#81c784
    style Facts fill:#81c784
    style Preds fill:#81c784
    style Legacy fill:#ff9800
```

### Ключевые эндпоинты

| Метод | Путь | Назначение |
|-------|------|-----------|
| GET | `/api/v1/vms` | Список всех VM |
| GET | `/api/v1/vms/{vm}/metrics` | Метрики конкретной VM |
| GET | `/api/v1/facts` | Фактические метрики с фильтрами |
| POST | `/api/v1/facts/batch` | Массовая загрузка метрик |
| GET | `/api/v1/facts/latest` | Последние метрики |
| GET | `/api/v1/predictions` | Прогнозы с фильтрами |
| POST | `/api/v1/predictions/batch` | Массовая загрузка прогнозов |
| GET | `/api/v1/predictions/future` | Будущие прогнозы |
| GET | `/api/v1/predictions/compare` | Сравнение факт vs прогноз |
| GET | `/api/v1/stats` | Статистика БД |
| DELETE | `/api/v1/cleanup` | Очистка старых данных |

**Документация**: `http://localhost:8000/docs` (Swagger UI)

---

## Структура файлов проекта

```
servers-dashboard/
├── src/
│   ├── app/                          # FastAPI Backend
│   │   ├── main.py                   # Точка входа FastAPI
│   │   ├── endpoints.py              # REST API эндпоинты
│   │   ├── models.py                 # SQLAlchemy модели
│   │   ├── schemas.py                # Pydantic схемы
│   │   ├── connection.py             # Подключение к БД
│   │   ├── dbcrud.py                 # Базовый CRUD
│   │   ├── facts_crud.py             # CRUD фактических метрик
│   │   ├── preds_crud.py             # CRUD прогнозов
│   │   ├── anomaly_detector.py       # Детектор аномалий
│   │   ├── base_logger.py            # Логирование
│   │   └── requirements.txt
│   │
│   └── ui/                           # Streamlit Frontend
│       ├── main.py                   # Точка входа Streamlit
│       ├── pages/                    # Страницы дашборда
│       │   ├── fact.py               # Фактические метрики
│       │   ├── forecast.py           # Прогнозирование
│       │   ├── analysis.py           # Анализ по серверам
│       │   └── as_analysis.py        # Анализ по АС
│       ├── components/               # UI компоненты
│       │   ├── header.py
│       │   ├── sidebar.py
│       │   ├── footer.py
│       │   ├── heatmap_as_cpu.py
│       │   └── heatmap_as_mem.py
│       ├── utils/                    # Утилиты UI
│       │   ├── data_loader.py        # Загрузка данных из БД
│       │   ├── data_generator.py     # Генератор моков
│       │   ├── alert_rules.py        # Правила алертов
│       │   ├── alert_analyzer.py     # Анализатор алертов
│       │   └── base_logger.py
│       ├── assets/
│       │   └── style.css             # Стили
│       └── requirements.txt
│
├── notebooks/
│   └── forecast/                     # Модуль прогнозирования
│       ├── forecaster.py             # Главный интерфейс
│       ├── model_training.py         # Обучение моделей
│       ├── model_tuning.py           # Подбор гиперпараметров
│       ├── model_prediction.py       # Генерация прогнозов
│       ├── storage.py                # Сохранение/загрузка
│       ├── evaluation.py             # Оценка качества
│       ├── utils.py                  # Утилиты
│       ├── config.py                 # Конфигурация
│       └── db_utils.py               # Работа с БД
│
├── ETL/                              # ETL Pipeline
│   ├── prepare_data.py               # Подготовка данных
│   ├── data_loader.py                # Загрузчик данных
│   └── new_data.py
│
├── tests/                            # Тесты
│   ├── conftest.py                   # Фикстуры pytest
│   ├── test_dbcrud.py
│   ├── test_factscrud.py
│   ├── test_predscrud.py
│   ├── test_api_endpoints.py
│   ├── test_anomaly_detector.py
│   ├── test_prophet_forecaster_prepare.py
│   └── test_ui_*.py
│
├── docker/                           # Docker конфигурация
│   └── all/
│       └── docker-compose.yml        # Полный стек
│
├── data/                             # Данные
│   ├── source/                       # Исходные файлы
│   │   ├── all_vm.xlsx               # Маппинг серверов на АС
│   │   └── data.xlsx
│   ├── dbdata/                       # Данные для загрузки
│   ├── dbextract/                    # Экспорты из БД
│   └── graphics/                     # Сохраненные графики
│
├── docs/                             # Документация
│   ├── ARCHITECTURE.md               # Этот файл
│   ├── API_ENDPOINTS.md              # API документация
│   ├── TESTING.md                    # Тестирование
│   └── PROJECT_SUMMARY_RU.md         # Краткое описание
│
├── README.md                         # Главный README
├── requirements.txt                  # Общие зависимости
├── pytest.ini                        # Конфигурация pytest
├── pyproject.toml                    # Конфигурация проекта
└── LICENSE
```

---

## Рекомендации по улучшению

### Производительность

1. **Кэширование** - добавить Redis для кэширования запросов
2. **Асинхронность** - перейти на async SQLAlchemy
3. **Connection Pooling** - оптимизация пула подключений
4. **Read Replicas** - реплики БД для чтения
5. **API Gateway** - rate limiting, throttling

### Безопасность

1. **CORS** - ограничить origins в продакшене
2. **Аутентификация** - завершить интеграцию Keycloak
3. **Secrets Management** - использовать vault для секретов
4. **HTTPS** - включить SSL в production
5. **Input Sanitization** - дополнительная валидация входных данных

### Мониторинг

1. **Prometheus** - сбор метрик
2. **Grafana** - визуализация метрик
3. **ELK Stack** - централизованное логирование
4. **Distributed Tracing** - OpenTelemetry
5. **Health Checks** - эндпоинты health и readiness

### Scalability

1. **Horizontal Scaling** - масштабирование API и UI
2. **Load Balancer** - балансировка нагрузки
3. **Database Sharding** - шардирование БД по VM
4. **Object Storage** - S3/MinIO для моделей
5. **Message Queue** - RabbitMQ/Kafka для асинхронных задач

---

## Заключение

Архитектура AIOps Dashboard обеспечивает:

✅ **Модульность** - четкое разделение компонентов  
✅ **Масштабируемость** - готовность к горизонтальному масштабированию  
✅ **Надежность** - обработка ошибок, валидация, тестирование  
✅ **Производительность** - оптимизация запросов, индексы БД  
✅ **Удобство** - интерактивный UI, REST API, документация  
✅ **ML/AI** - прогнозирование с Prophet, подбор гиперпараметров  

### Ключевые преимущества

- Прямое подключение UI к БД для минимальной латентности
- Модуль прогнозирования с автоматическим подбором гиперпараметров
- Комплексная обработка ошибок и валидация данных
- Анализ по Автоматизированным Системам (АС)
- Docker-based развертывание для всех сред

---

**Версия документа**: 3.0  
**Дата**: 2026-01-19  
**Автор**: AIOps Dashboard Team
