from datetime import datetime, timedelta

from facts_crud import FactsCRUD
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Создание сессии
engine = create_engine('postgresql://postgres:postgres@localhost:5432/server_metrics')
SessionLocal = sessionmaker(bind=engine)
session = SessionLocal()

# Создание CRUD объекта
crud = FactsCRUD(session)

# 1. Получение последних 24 часов данных
vm = "DataLake-DBN1"
metric = "cpu.usage.average"

latest_data = crud.get_latest_metrics(vm, metric, hours=2000)
print(f"Получено {len(latest_data)} записей за последние 2000 часов")

# 2. Получение статистики
stats = crud.get_historical_metrics_statistics(vm, metric)
print(f"Статистика: среднее={stats['avg']:.2f}, минимум={stats['min']:.2f}, максимум={stats['max']:.2f}")

# Закрытие сессии
session.close()