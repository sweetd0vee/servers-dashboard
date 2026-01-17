from datetime import datetime, timedelta

from db_helper import get_session_local
from dbcrud import DBCRUD


def main() -> None:
    SessionLocal = get_session_local()
    session = SessionLocal()

    try:
        crud = DBCRUD(session)

        # 1. Получение всех VM в базе
        all_vms = crud.get_all_vms()
        print(f"Все VM в базе: {all_vms}")

        # 2. Получение списка метрик для конкретной VM
        vm = "DataLake-DBN1"
        metric = "cpu.usage.average"
        metrics = crud.get_metrics_for_vm(vm=vm)
        print(f"Метрики для {vm}: {metrics}")

        # 3. Получение временного диапазона данных
        dt_range = crud.get_data_time_range(vm=vm, metric=metric)
        print(f"Диапазон данных {vm}/{metric}: {dt_range}")

        # 4. Получение статистики базы
        db_stats = crud.get_database_stats()
        print(f"Статистика БД: {db_stats}")

        # 5. Проверка полноты данных за последние 7 дней
        end_date = datetime.now()
        start_date = end_date - timedelta(days=7)
        completeness = crud.calculate_data_completeness(
            vm=vm,
            metric=metric,
            start_date=start_date,
            end_date=end_date,
            expected_interval_minutes=30,
        )
        print(
            "Полнота данных: "
            f"{completeness['completeness_percentage']}% "
            f"(missing={completeness['missing_points']})"
        )

        # 6. Поиск пропусков
        missing = crud.detect_missing_data(
            vm=vm,
            metric=metric,
            start_date=start_date,
            end_date=end_date,
            expected_interval_minutes=30,
        )
        print(f"Пропущенные интервалы: {len(missing)}")
    finally:
        session.close()


if __name__ == "__main__":
    main()