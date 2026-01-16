from sqlalchemy.orm import Session
from sqlalchemy import desc, and_, func
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Tuple
import models as db_models
import schemas as pydantic_models


class PredsCRUD:
    def __init__(self, db: Session):
        self.db = db

    # ================================ ПРЕДСКАЗАНИЯ =====================================

    def save_prediction(
            self,
            vm: str,
            metric: str,
            timestamp: datetime,
            value: float,
            lower_bound: Optional[float] = None,
            upper_bound: Optional[float] = None
    ) -> db_models.ServerMetricsPredictions:
        """
        Сохранение предсказания

        Args:
            vm: Имя виртуальной машины
            metric: Тип метрики
            timestamp: Время предсказания
            value: Предсказанное значение
            lower_bound: Нижняя граница доверительного интервала
            upper_bound: Верхняя граница доверительного интервала

        Returns:
            Созданная запись предсказания
        """
        # Проверяем, существует ли уже предсказание для этого времени
        existing = self.db.query(db_models.ServerMetricsPredictions).filter(
            db_models.ServerMetricsPredictions.vm == vm,
            db_models.ServerMetricsPredictions.metric == metric,
            db_models.ServerMetricsPredictions.timestamp == timestamp
        ).first()

        if existing:
            # Обновляем существующее предсказание
            existing.value_predicted = value
            existing.lower_bound = lower_bound
            existing.upper_bound = upper_bound
            existing.created_at = datetime.now()
            self.db.commit()
            self.db.refresh(existing)
            return existing

        # Создаем новое предсказание
        prediction = db_models.ServerMetricsPredictions(
            vm=vm,
            metric=metric,
            timestamp=timestamp,
            value_predicted=value,
            lower_bound=lower_bound,
            upper_bound=upper_bound,
            created_at=datetime.now() #,
            # updated_at=datetime.now()
        )
        self.db.add(prediction)
        self.db.commit()
        self.db.refresh(prediction)
        return prediction

    def save_predictions_batch(
            self,
            predictions: List[Dict]
    ) -> int:
        """
        Пакетное сохранение предсказаний

        Args:
            predictions: Список предсказаний в формате:
                {
                    'vm': 'server1',
                    'metric': 'cpu.usage.average',
                    'timestamp': datetime,
                    'value': 45.6,
                    'lower': 40.1,
                    'upper': 50.2
                }

        Returns:
            Количество сохраненных предсказаний
        """
        saved_count = 0
        for pred in predictions:
            try:
                self.save_prediction(
                    vm=pred['vm'],
                    metric=pred['metric'],
                    timestamp=pred['timestamp'],
                    value=pred['value'],
                    lower=pred.get('lower'),
                    upper=pred.get('upper')
                )
                saved_count += 1
            except Exception as e:
                print(f"Error saving prediction {pred}: {e}")

        return saved_count

    def get_predictions(
            self,
            vm: str,
            metric: str,
            start_date: Optional[datetime] = None,
            end_date: Optional[datetime] = None
    ) -> List[db_models.ServerMetricsPredictions]:
        """
        Получение предсказаний

        Args:
            vm: Имя виртуальной машины
            metric: Тип метрики
            start_date: Начальная дата
            end_date: Конечная дата

        Returns:
            Список предсказаний
        """
        query = self.db.query(db_models.ServerMetricsPredictions).filter(
            db_models.ServerMetricsPredictions.vm == vm,
            db_models.ServerMetricsPredictions.metric == metric
        )

        if start_date:
            query = query.filter(db_models.ServerMetricsPredictions.timestamp >= start_date)
        if end_date:
            query = query.filter(db_models.ServerMetricsPredictions.timestamp <= end_date)

        return query.order_by(db_models.ServerMetricsPredictions.timestamp).all()

    def get_future_predictions(self, vm: str, metric: str) -> List[db_models.ServerMetricsPredictions]:
        """
        Получение будущих предсказаний (timestamp > now)

        Args:
            vm: Имя виртуальной машины
            metric: Тип метрики

        Returns:
            Список будущих предсказаний
        """
        return self.db.query(db_models.ServerMetricsPredictions).filter(
            db_models.ServerMetricsPredictions.vm == vm,
            db_models.ServerMetricsPredictions.metric == metric,
            db_models.ServerMetricsPredictions.timestamp > datetime.now()
        ).order_by(db_models.ServerMetricsPredictions.timestamp).all()

    def get_actual_vs_predicted(
            self,
            vm: str,
            metric: str,
            hours: int = 24
    ) -> List[Dict]:
        """
        Сопоставление фактических значений с предсказанными

        Args:
            vm: Имя виртуальной машины
            metric: Тип метрики
            hours: Количество часов для сравнения

        Returns:
            Список сопоставленных значений
        """
        cutoff_time = datetime.now() - timedelta(hours=hours)

        # Получаем фактические значения
        actual = self.db.query(db_models.ServerMetricsFact).filter(
            db_models.ServerMetricsFact.vm == vm,
            db_models.ServerMetricsFact.metric == metric,
            db_models.ServerMetricsFact.timestamp >= cutoff_time
        ).order_by(db_models.ServerMetricsFact.timestamp).all()

        # Получаем предсказания
        predictions = self.db.query(db_models.ServerMetricsPredictions).filter(
            db_models.ServerMetricsPredictions.vm == vm,
            db_models.ServerMetricsPredictions.metric == metric,
            db_models.ServerMetricsPredictions.timestamp >= cutoff_time
        ).order_by(db_models.ServerMetricsPredictions.timestamp).all()

        # Создаем словарь предсказаний для быстрого поиска
        pred_dict = {p.timestamp: p for p in predictions}

        # Сопоставляем значения
        comparison = []
        for actual_record in actual:
            pred_record = pred_dict.get(actual_record.timestamp)
            if pred_record:
                comparison.append({
                    'timestamp': actual_record.timestamp,
                    'actual_value': actual_record.value,
                    'predicted_value': pred_record.value_predicted,
                    'error': abs(actual_record.value - pred_record.value_predicted),
                    'relative_error': abs(
                        actual_record.value - pred_record.value_predicted) / actual_record.value * 100 if actual_record.value > 0 else 0,
                    'lower_bound': pred_record.lower_bound,
                    'upper_bound': pred_record.upper_bound
                })

        return comparison
