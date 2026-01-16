<!--
README по лучшим практикам: структура, четкие шаги запуска,
прозрачные конфигурации и ссылки на подробную документацию.
-->

# AIOps Dashboard

Платформа мониторинга и прогнозирования нагрузки серверов: сбор метрик, аналитика и прогнозы временных рядов в одном интерфейсе.

## Быстрый старт

### Docker (рекомендуется для первого запуска)
```bash
cd docker/all
docker-compose up -d
```

#### Docker для Windows/macOS
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

После старта:
- API: `http://localhost:8000` (Swagger: `/docs`, ReDoc: `/redoc`)
- UI: `http://localhost:8501`

### Локально (без Docker)
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

## Содержание

- [Ключевые возможности](#ключевые-возможности)
- [Архитектура](#архитектура)
- [Требования](#требования)
- [Конфигурация](#конфигурация)
- [Запуск](#запуск)
- [API](#api)
- [Работа с данными](#работа-с-данными)
- [Разработка](#разработка)
- [Тестирование](#тестирование)
- [Деплой](#деплой)
- [Лучшие практики](#лучшие-практики)
- [Troubleshooting](#troubleshooting)
- [Документация](#документация)
- [Вклад в проект](#вклад-в-проект)
- [Лицензия](#лицензия)

## Ключевые возможности

- Мониторинг метрик (CPU, память, диск, сеть) и визуализация исторических данных
- Прогнозирование временных рядов (Prophet) с доверительными интервалами
- Аналитика по серверам и метрикам, сравнение факта и прогноза
- Интеграция с Keycloak (опционально) для SSO

## Архитектура

Сервис разделен на три основные части:
- `src/app` — REST API (FastAPI)
- `src/ui` — веб-интерфейс (Streamlit)
- `forecast` — прогнозирование и ML-логика

Подробности: `docs/ARCHITECTURE.md` и `docs/ARCHITECTURE_SUMMARY.md`.

## Требования

- Python 3.12+
- PostgreSQL 16+ (или Docker)
- Docker + Docker Compose (для контейнерного запуска)

## Конфигурация

### Переменные окружения (API)

API читает настройки БД из `.env` в корне проекта или из переменных окружения:

```env
DB_HOST=localhost
DB_PORT=5432
DB_USER=postgres
DB_PASSWORD=postgres
DB_NAME=server_metrics
```

См. `src/app/connection.py`.

### Keycloak (опционально, для UI)

Используются переменные:

```env
KEYCLOAK_URL=http://localhost:8087/keycloak
KEYCLOAK_URL_FOR_AUTH=http://localhost:8087/keycloak
KEYCLOAK_REDIRECT_URI=http://localhost:8501/dashboard
KEYCLOAK_REALM=srv
KEYCLOAK_CLIENT_ID=srv-keycloak-client
KEYCLOAK_CLIENT_SECRET=change-me
```

См. `src/ui/auth.py`.

## Запуск

### Docker

Полный стек:
```bash
cd docker/all
docker-compose up -d
```

Остановка:
```bash
cd docker/all
docker-compose down
```

### Локально

1) Запуск API:
```bash
cd src/app
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

2) Запуск UI:
```bash
cd src/ui
streamlit run main.py --server.port 8501
```

## API

Базовый URL: `http://localhost:8000/api/v1`

Основные эндпоинты:
- `GET /vms` — список ВМ
- `GET /facts` — фактические метрики
- `GET /predictions` — прогнозы
- `GET /predictions/compare` — сравнение факт/прогноз

Полный список: `docs/API_ENDPOINTS.md`.  
Интерактивная документация: `http://localhost:8000/docs`.

## Работа с данными

- Источники данных и примеры файлов лежат в `data/`
- Для загрузки данных из Excel/CSV используйте `utils/data_loader.py`
- Рекомендуется хранить большие датасеты вне репозитория и загружать через API

## Разработка

### Установка зависимостей

```bash
pip install -r src/app/requirements.txt
pip install -r src/ui/requirements.txt
pip install -r tests/requirements.txt
```

Также доступен общий файл зависимостей: `reqirements.txt`.

### Стиль и качество кода

Рекомендуемые инструменты:
- `black` — форматирование
- `flake8` — линтинг
- `mypy` — типизация

```bash
black src/
flake8 src/
mypy src/
```

## Тестирование

```bash
pytest
pytest --cov=src/app --cov-report=html
```

Для Windows: `run_tests.bat`.

Подробности: `docs/TESTING.md`.

## Деплой

Рекомендации для production:
- Ограничьте CORS в `src/app/main.py`
- Используйте секреты через переменные окружения/секреты контейнеров
- Настройте HTTPS на уровне reverse proxy (`docker/httpd`)
- Включите централизованный сбор логов

## Лучшие практики

- **Конфигурация**: храните секреты только в окружении, не в репозитории
- **Данные**: большие файлы держите вне git, загружайте через API/ETL
- **Наблюдаемость**: включайте структурированные логи и метрики
- **Безопасность**: минимизируйте `allow_origins`, регулярно обновляйте зависимости
- **Тесты**: покрывайте CRUD и сценарии прогнозирования, проверяйте миграции

## Troubleshooting

- БД недоступна: проверьте `DB_*` и доступность `postgres`
- API не отвечает: проверьте логи контейнера и порт `8000`
- UI без данных: проверьте CORS и доступность API

## Документация

- `docs/ARCHITECTURE.md` — архитектура
- `docs/API_ENDPOINTS.md` — API
- `docs/TESTING.md` — тестирование
- `docs/CODE_REVIEW.md` — обзор кода

## Вклад в проект

1. Создайте ветку `feature/*`
2. Добавьте тесты и документацию
3. Откройте Pull Request

## Лицензия

MIT — см. `LICENSE`.

