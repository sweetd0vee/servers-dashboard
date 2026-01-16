# Data Loader Module

Этот модуль отвечает за загрузку данных для дашборда из базы данных.

## Файлы

- **`data_loader.py`** - Основной модуль для загрузки данных из базы данных
- **`data_generator.py`** - Генератор тестовых данных (fallback, если база недоступна)

## Использование

### Загрузка данных из базы

```python
from utils.data_loader import generate_server_data

# Загружает данные за последние 30 дней (720 часов)
df = generate_server_data()
```

### Загрузка с параметрами

```python
from utils.data_loader import load_data_from_database
from datetime import datetime, timedelta

start_date = datetime.now() - timedelta(days=7)
end_date = datetime.now()

# Загрузка за последние 7 дней
df = load_data_from_database(
    start_date=start_date,
    end_date=end_date,
    vms=['DataLake-DBN1'],  # Опционально: конкретные VM
    metrics=['cpu.usage.average']  # Опционально: конкретные метрики
)
```

## Формат данных

Функция возвращает DataFrame со следующими колонками:

- `server` - название сервера (VM)
- `timestamp` - временная метка
- `load_percentage` - процент нагрузки (обычно = cpu.usage.average)
- `cpu.usage.average` - использование CPU
- `mem.usage.average` - использование памяти
- `net.usage.average` - использование сети
- `cpu.ready.summation` - время готовности CPU
- `disk.usage.average` - использование диска
- `errors` - количество ошибок
- `server_type` - тип сервера (извлечен из имени)
- `weekday` - день недели (0-6)
- `hour_of_day` - час дня (0-23)
- `is_business_hours` - рабочие часы (1/0)
- `is_weekend` - выходной день (1/0)
- `load_ma_6h` - скользящее среднее за 6 часов
- `load_ma_24h` - скользящее среднее за 24 часа

## Конфигурация базы данных

Модуль использует настройки из `src/app/connection.py`:
- Переменные окружения: `DB_HOST`, `DB_USER`, `DB_PASSWORD`, `DB_PORT`, `DB_NAME`
- Или значения по умолчанию

## Fallback режим

Если база данных недоступна, модуль автоматически переключается на генерацию тестовых данных из `data_generator.py`.

## Зависимости

- `pandas` - для работы с данными
- `sqlalchemy` - для подключения к базе данных
- `numpy` - для вычислений (fallback режим)

## Примечания

- Данные загружаются из таблицы `server_metrics_fact`
- Используется `FactsCRUD` для доступа к данным
- Данные преобразуются из long format (vm, timestamp, metric, value) в wide format (pivot)
- Если метрика отсутствует, используется значение по умолчанию 0.0

