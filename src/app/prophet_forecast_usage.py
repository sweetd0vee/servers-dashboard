from db_helper import get_session_local
from dbcrud import DBCRUD
from prophet_forecaster import ProphetForecaster


def main() -> None:
    SessionLocal = get_session_local()
    session = SessionLocal()
    crud = DBCRUD(session)
    forecaster = ProphetForecaster(model_storage_path="./prophet_models")

    try:
        vm = "DataLake-DBN1"
        metric = "cpu.usage.average"

        # 1. Обучение или загрузка модели
        model = forecaster.train_or_load_model(
            db=session,
            crud=crud,
            vm=vm,
            metric=metric,
            retrain=False,
        )

        if model:
            print("✅ Модель успешно загружена/обучена")

            # 2. Генерация прогноза на 24 часа (48 периодов по 30 минут)
            forecast_result = forecaster.generate_forecast(
                db=session,
                crud=crud,
                vm=vm,
                metric=metric,
                periods=48,
                freq="30min",
                save_to_db=True,
            )

            if forecast_result["success"]:
                print(f"Сгенерировано {forecast_result['total_predictions']} прогнозов")
                for pred in forecast_result["predictions"][:5]:
                    print(
                        f"  {pred['timestamp']}: {pred['prediction']:.1f}% "
                        f"({pred['confidence_lower']:.1f}-{pred['confidence_upper']:.1f})"
                    )
            else:
                print(f"Ошибка: {forecast_result.get('error', 'Unknown error')}")

        # 3. Пакетное обучение моделей
        vm_metric_pairs = [
            (vm, metric),
            # (vm, "memory.usage.average"),
        ]
        batch_results = forecaster.batch_train_models(
            db=session,
            crud=crud,
            vm_metric_pairs=vm_metric_pairs,
        )
        print(
            f"\nПакетное обучение: {batch_results['successful']} успешно, "
            f"{batch_results['failed']} с ошибками"
        )

        # 4. Очистка старых моделей
        cleanup_stats = forecaster.cleanup_old_models(days_to_keep=30)
        if cleanup_stats["success"]:
            print(
                f"Очистка моделей: удалено {cleanup_stats['deleted_models']}, "
                f"оставлено {cleanup_stats['kept_models']}"
            )
    finally:
        session.close()


if __name__ == "__main__":
    main()