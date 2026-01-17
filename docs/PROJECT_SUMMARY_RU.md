# Саммари проекта

Ниже — краткое, но полное описание проекта, архитектуры, структуры кода, ключевых пакетов и основных классов. Также указано количество строк кода в `src/` и место для скриншотов UI.

## Назначение

**AIOps Dashboard** — платформа мониторинга и прогнозирования нагрузки серверов: сбор метрик, аналитика, сравнение факта и прогноза, визуализации, прогнозы временных рядов (Prophet).

## Архитектура (высокоуровнево)

1) **Backend API (FastAPI)**  
   Пакет: `src/app`  
   Отвечает за CRUD‑операции метрик, статистику, прогнозы, проверки полноты данных, обработку ошибок.

2) **UI (Streamlit)**  
   Пакет: `src/ui`  
   Визуализации, аналитические страницы, сценарии для факта/прогноза/АС‑анализа, компоненты интерфейса.

3) **Forecasting/ML**  
   Пакет: `src/app` (runtime) и `notebooks/forecast` (исследования/утилиты)  
   Prophet‑модель, тюнинг параметров, сохранение моделей, метрики качества.

4) **Data/ETL utils**  
   Папки: `utils/`, `data/`  
   Подготовка данных, обработка Excel/CSV, преобразования и загрузка.

## Структура кода (основные каталоги)

```
src/
├── app/                # Backend API (FastAPI)
│   ├── main.py
│   ├── endpoints.py
│   ├── models.py
│   ├── schemas.py
│   ├── dbcrud.py
│   ├── facts_crud.py
│   ├── preds_crud.py
│   ├── prophet_forecaster.py
│   └── ...
├── ui/                 # UI (Streamlit)
│   ├── main.py
│   ├── pages/          # страницы: fact/analysis/forecast/as_analysis
│   ├── components/     # header/sidebar/footer/heatmaps
│   └── utils/          # data_loader/alerts/logging
```

Дополнительно:
- `notebooks/forecast/` — исследовательские модули для прогнозирования.
- `tests/` — unit/integration тесты CRUD и API.
- `docker/` — инфраструктурные конфиги.

## Пакеты (ключевые внутренние)

- **`src/app`**: FastAPI, SQLAlchemy, модели, CRUD, прогнозирование.
- **`src/ui`**: Streamlit UI, страницы, компоненты, загрузчики данных.
- **`notebooks/forecast`**: вспомогательные модули для обучения/оценки моделей.
- **`tests`**: тесты CRUD и API.

## Количество строк кода (только `src/`)

По текущему состоянию файловой системы:

- **Всего строк в `src/`**: **31,144**
  - `src/app`: **5,921**
  - `src/ui`: **23,529**
  - `src/logs`: **1,694** *(генерируемые/служебные файлы, могут быть в `.gitignore`)*

> Примечание: подсчёт выполнялся по всем файлам под `src/`. Если требуется исключить лог‑файлы, можно пересчитать с исключением `src/logs`.

## Основные классы (по репозиторию)

### Backend (`src/app`)
- **`DBCRUD`** — общие операции по метрикам/статистике.
- **`FactsCRUD`** — CRUD для фактических метрик.
- **`PredsCRUD`** — CRUD для прогнозов.
- **`ProphetForecaster`** — обучение/загрузка/прогнозирование моделей.
- **`AnomalyDetector`** — алгоритмы обнаружения аномалий.
- **`ServerMetricsFact`, `ServerMetricsPredictions`** — ORM модели БД.
- **`MetricFact`, `MetricPrediction`, ...** — Pydantic‑схемы API.

### UI (`src/ui`)
- **`AlertSystem`, `AlertRule`, `AlertSeverity`, `ServerStatus`** — логика алертов.
- **`Alert`** (в `alert_analyzer.py`) — модель алерта/уведомления.

### Notebooks (`notebooks/forecast`)
- **`DatabaseExtractor`** — извлечение данных.
- **`ProphetForecaster`** — исследовательская версия прогнозировщика.

## Скриншоты приложения

В этой среде скриншоты не были автоматически сгенерированы.  
Рекомендуемые страницы для снимков:

1) **Главная** — вкладки: Fact / Forecast / AS Analysis / Server Analysis.
2) **Forecast** — график прогноза + интервалы.
3) **Analysis / AS Analysis** — тепловые карты или сводные таблицы.

**Как сделать:**
1. Запуск Docker: `cd docker/all && docker-compose up -d`
2. Открыть UI: `http://localhost:8501`
3. Сохранить изображения и добавить в `docs/screenshots/`

После добавления снимков сюда можно вставить:

```
![UI - Overview](screenshots/ui-overview.png)
![UI - Forecast](screenshots/ui-forecast.png)
![UI - Analysis](screenshots/ui-analysis.png)
```

