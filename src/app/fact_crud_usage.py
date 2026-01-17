from datetime import datetime, timedelta

from db_helper import get_session_local
from facts_crud import FactsCRUD
from schemas import MetricFact


def main() -> None:
    SessionLocal = get_session_local()
    session = SessionLocal()

    try:
        crud = FactsCRUD(session)

        vm = "DataLake-DBN1"
        metric = "cpu.usage.average"

        # 1. Получение последних 24 часов данных
        latest_data = crud.get_latest_metrics(vm, metric, hours=24)
        print(f"Получено {len(latest_data)} записей за последние 24 часа")

        # 2. Получение статистики за 7 дней
        end_date = datetime.now()
        start_date = end_date - timedelta(days=7)
        stats = crud.get_metrics_fact_statistics(
            vm=vm,
            metric=metric,
            start_date=start_date,
            end_date=end_date,
        )
        print(
            "Статистика за 7 дней: "
            f"avg={stats['avg']:.2f}, min={stats['min']:.2f}, max={stats['max']:.2f}"
        )

        # 3. Создание или обновление метрики
        new_fact = MetricFact(
            vm=vm,
            timestamp=datetime.now(),
            metric=metric,
            value=42.5,
            created_at=datetime.now(),
        )
        saved_fact = crud.create_metric_fact(new_fact)
        print(
            "Сохранена запись: "
            f"{saved_fact.vm}/{saved_fact.metric} at {saved_fact.timestamp}"
        )
    finally:
        session.close()


if __name__ == "__main__":
    main()