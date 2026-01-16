from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timedelta
import pandas as pd
from dbcrud import DBCRUD

# Создание сессии
engine = create_engine('postgresql://postgres:postgres@localhost:5432/server_metrics')
SessionLocal = sessionmaker(bind=engine)
session = SessionLocal()

# Создание CRUD объекта
crud = DBCRUD(session)

# 1. Получение всех VM в базе
all_vms = crud.get_all_vms()
print(f"Все VM в базе: {all_vms}")

# 2. Получения спесика метрик из БД для конкретной vm
metrics = crud.get_metrics_for_vm(vm='DataLake-DBN1')

# 2. Получение временного промежутка для
dt_range = crud.get_data_time_range(vm='DataLake-DBN1',metric='cpu.usage.average')
print(dt_range)

# 3. Получение статистики базы
db_stats = crud.get_database_stats()
print(f"Статистика БД: {db_stats}")

# 2. Проверка полноты данных
# completeness = crud.calculate_data_completeness(
#     vm='DataLake-DBN1',
#     metric='cpu.usage.average',
#     start_date=pd.to_datetime('2025-11-25 17:00:00', format='%Y-%m-%d %h:%M:%S'),
#     end_date=pd.to_datetime('2025-12-01 12:30:00', format='%Y-%m-%d %h:%M:%S'),
#     expected_interval_minutes=30
# )
# print(f"Полнота данных: {completeness['completeness_percentage']}%")

# # 6. Очистка старых данных
# cleanup_stats = crud.cleanup_old_data(days_to_keep=30)
# print(f"Удалено записей: {cleanup_stats}")
#
# # 7. Получение статистики базы
# db_stats = crud.get_database_stats()
# print(f"Статистика БД: {db_stats}")
#
# # 8. Сравнение фактических значений с предсказанными
# comparison = crud.get_actual_vs_predicted(vm, metric, hours=48)
# for item in comparison[:5]:
#     print(f"Время: {item['timestamp']}, Факт: {item['actual_value']}, Прогноз: {item['predicted_value']}, Ошибка: {item['error']:.2f}")

# Закрытие сессии
session.close()