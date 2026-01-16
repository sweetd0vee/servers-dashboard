# Полное код-ревью проекта AIOps Dashboard

Дата: 2026-01-16  
Репозиторий: `servers-dashboard`

## Область и подход
- Просмотрены ключевые модули `src/app`, `src/ui`, `forecast`, `utils`, `tests`, `docker`, `docs`.
- Фокус: дефекты, безопасность, устойчивость, поддерживаемость, тестируемость.

## Краткая оценка проекта
Проект функционально цельный: есть API, UI, модуль прогнозирования, тесты и доки. Архитектура читаема, но есть критические дефекты в прогнозировании и batch-предсказаниях, а также риски безопасности/конфигурации и платформенной совместимости (жесткие пути Windows). Требуется исправление нескольких багов, иначе часть функционала ломается при реальном запуске.

---

## Критические дефекты (нужно исправить в первую очередь)

### 1) Batch-сохранение прогнозов падает из-за неверных аргументов
В `PredsCRUD.save_predictions_batch` вызывается `save_prediction` с параметрами `lower`/`upper`, но метод ожидает `lower_bound`/`upper_bound`. Это вызовет `TypeError` при любом batch-запросе.

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

**Как исправить**
- Заменить аргументы на `lower_bound=...`, `upper_bound=...`.
- Добавить тест на `/predictions/batch` с реальной валидацией сохранения.

### 2) Обучение модели прогнозирования ломается из-за формата данных
`forecast/utils.prepare_data` ожидает `ds`/`y`, а `forecast/forecaster.py` передает `timestamp`/`value`. Это вызывает `KeyError` и делает прогнозирование неработающим.

```48:50:forecast/forecaster.py
        data_dicts = [{'timestamp': r.timestamp, 'value': float(r.value)} for r in data_records]
        df = prepare_data(data_dicts)
```

```29:41:forecast/utils.py
def prepare_data(data: List[Dict]) -> pd.DataFrame:
    if not data:
        raise ValueError("No data provided for preparation")

    df = pd.DataFrame(data)
    df['ds'] = pd.to_datetime(df['ds'], utc=True)
    ...
    if df['y'].isnull().any():
```

**Как исправить**
- В `forecaster.py` формировать `{'ds': ..., 'y': ...}`.
- Добавить unit-тест на `prepare_data` и e2e-тест на `train_or_load_model`.

### 3) UI-прогноз падает при ошибке импорта
Если импорт в `src/ui/pages/forecast.py` падает до создания `logger`, в `except` используется неинициализированная переменная.

```21:27:src/ui/pages/forecast.py
try:
    from utils.data_loader import load_data_from_database, generate_server_data
    from utils.base_logger import logger
    from app.prophet_forecaster import ProphetForecaster
except ImportError as e:
    logger.info(f"Ошибка импорта: {e}")
```

**Как исправить**
- Вынести `logger` выше, либо заменить `logger.info` на `st.warning`/`print`.
- Добавить smoke-тест запуска UI без модулей БД.

### 4) UI-прогноз может падать из-за неинициализированной переменной `data`
Если `load_data_from_database` не определён/False, переменная `data` не задаётся, но используется ниже.

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

**Как исправить**
- Задавать `data = generate_server_data()` как дефолт перед веткой.
- Либо `return` при недоступности загрузчика.

---

## Высокая важность

### 1) Утечка секретов: логируется полный `DATABASE_URL` с паролем

```19:22:src/app/connection.py
DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
logger.info(f"DATABASE_URL: {DATABASE_URL}")
```

**Как исправить**
- Логировать только `DB_HOST`, `DB_PORT`, `DB_NAME`.
- Пароль скрывать маской `***`.

### 2) CORS с `allow_credentials=True` и `allow_origins=["*"]`
Это нарушает спецификацию CORS и может приводить к блокировке запросов браузером. Также это риск безопасности.

```26:32:src/app/main.py
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**Как исправить**
- Для production: указать список доменов.
- Для dev: `allow_credentials=False` при `["*"]`.

---

## Средняя важность

### 1) Баг в `__repr__` модели прогнозов
Используется несуществующее поле `predicted_value` вместо `value_predicted`.

```172:178:src/app/models.py
    def __repr__(self):
        return (
            f"<ServerMetricsPrediction(vm='{self.vm}', "
            f"timestamp='{self.timestamp}', "
            f"metric='{self.metric}', "
            f"predicted_value={self.predicted_value}"
        )
```

**Как исправить**
- Заменить на `self.value_predicted`.

### 2) Жестко заданные пути Windows в UI
В `src/ui/main.py` и `src/ui/pages/forecast.py` используются абсолютные Windows-пути. На macOS/Linux это приводит к ошибкам и неработающим стилям/маппингу.

```28:33:src/ui/main.py
def apply_custom_styles():
    """Применение кастомных стилей"""
    try:
        with open(r"C:\Users\audit\Work\Arina\Servers\dashboard\src\ui\assets\style.css", encoding='utf-8') as f:
            css_content = f.read()
```

**Как исправить**
- Использовать относительные пути от `Path(__file__)`.
- Добавить fallback, если файл не найден.

---

## Низкая важность и техдолг

- Дублирование логгеров (`base_logger.py` в корне и `src/ui/utils/base_logger.py`) вызывает путаницу и повторные хендлеры.
- `reqirements.txt` в корне с опечаткой осложняет установку зависимостей.
- Много прямых `sys.path`-манипуляций в UI, сложнее поддерживать; лучше оформить как пакет или использовать относительные импорты.
- Тестовая БД на SQLite с PostgreSQL-типами (UUID) может вести себя иначе, чем в проде; возможны скрытые несовместимости.

---

## Оценка по частям проекта и рекомендации

### Backend API (`src/app`)
**Сильные стороны**
- Хорошая структура CRUD и endpoint-ов.
- Валидация входных параметров, внятные схемы.

**Проблемы**
- CORS и логирование секрета.
- Дублирование логики в `DBCRUD`/`FactsCRUD` без единого слоя репозитория.

**Рекомендации**
- Вынести общую логику и унифицировать обработку ошибок.
- Добавить сервисный слой для прогнозов/аномалий.

### Frontend UI (`src/ui`)
**Сильные стороны**
- Богатый интерфейс, есть аналитика и экспорт.
- Грамотное использование `st.cache_data`.

**Проблемы**
- Жесткие пути, нестабильные импорты.
- Прямой доступ к БД из UI обходя API.

**Рекомендации**
- Перевести загрузку данных на API.
- Нормализовать пути и логирование.

### Forecasting (`forecast/`)
**Сильные стороны**
- Отдельный модуль с настройками и метриками качества.
- Есть хранение моделей.

**Проблемы**
- Критический дефект формата данных.
- Нет fallback при недостаточных данных, нет тестов.

**Рекомендации**
- Исправить формат `ds/y`.
- Добавить тесты на подготовку данных и прогноз.

### Utils/ETL (`utils/`)
**Сильные стороны**
- Скрипты для подготовки и загрузки данных.

**Проблемы**
- Нет явного CLI или контейнеризации для batch-ETL.

**Рекомендации**
- Добавить CLI или makefile-сценарии.

### Tests (`tests/`)
**Сильные стороны**
- Есть покрытие CRUD и API.

**Проблемы**
- Нет тестов UI и модуля прогнозирования.
- Не проверяются edge cases (пустые данные, большие batch).

**Рекомендации**
- Добавить тесты на `forecast` и UI smoke.
- Проверить совместимость с PostgreSQL.

### Docker (`docker/`, `docker-macos/`)
**Сильные стороны**
- Разделение стеков по компонентам.

**Проблемы**
- Дублирование конфигураций Windows/macOS.

**Рекомендации**
- Консолидировать в один compose с параметрами окружения.

### Docs (`docs/`)
**Сильные стороны**
- Достаточно хорошее описание архитектуры и API.

**Рекомендации**
- Добавить раздел “Known issues” и “Upgrade notes”.

---

## Приоритетный план фиксов (1–2 дня)
1) Исправить batch-предсказания (`lower_bound`/`upper_bound`).
2) Исправить формат данных в `forecast`.
3) Починить импорт/`data` в UI-прогнозах.
4) Удалить логирование пароля и поправить CORS.
5) Заменить жесткие пути на относительные.

