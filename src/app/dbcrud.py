from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import models as db_models
import schemas as pydantic_models
from sqlalchemy import and_, desc, func
from sqlalchemy.orm import Session


class DBCRUD:
    def __init__(self, db: Session):
        self.db = db

    # ================================= ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ ==================================

    def get_all_vms(self) -> List[str]:
        """
        Получить список всех виртуальных машин в базе

        Returns:
            Список имен VM
        """
        result = self.db.query(db_models.ServerMetricsFact.vm).distinct().all()
        return [row[0] for row in result]

    def get_metrics_for_vm(self, vm: str) -> List[str]:
        """
        Получить список метрик для конкретной VM

        Args:
            vm: Имя виртуальной машины

        Returns:
            Список метрик
        """
        result = self.db.query(db_models.ServerMetricsFact.metric).filter(
            db_models.ServerMetricsFact.vm == vm
        ).distinct().all()
        return [row[0] for row in result]

    def get_data_time_range(self, vm: str, metric: str) -> Dict:
        """
        Получить временной диапазон данных для VM и метрики

        Args:
            vm: Имя виртуальной машины
            metric: Тип метрики

        Returns:
            Словарь с датами начала и конца
        """
        first_record = self.db.query(db_models.ServerMetricsFact).filter(
            db_models.ServerMetricsFact.vm == vm,
            db_models.ServerMetricsFact.metric == metric
        ).order_by(db_models.ServerMetricsFact.timestamp).first()

        last_record = self.db.query(db_models.ServerMetricsFact).filter(
            db_models.ServerMetricsFact.vm == vm,
            db_models.ServerMetricsFact.metric == metric
        ).order_by(desc(db_models.ServerMetricsFact.timestamp)).first()

        if not first_record or not last_record:
            return {}

        return {
            'first_timestamp': first_record.timestamp,
            'last_timestamp': last_record.timestamp,
            'total_hours': (last_record.timestamp - first_record.timestamp).total_seconds() / 3600,
            'total_records': self.db.query(db_models.ServerMetricsFact).filter(
                db_models.ServerMetricsFact.vm == vm,
                db_models.ServerMetricsFact.metric == metric
            ).count()
        }

    def cleanup_old_data(self, days_to_keep: int = 90) -> Dict:
        """
        Очистка старых данных

        Args:
            days_to_keep: Количество дней для хранения

        Returns:
            Статистика удаления
        """
        cutoff_date = datetime.now() - timedelta(days=days_to_keep)

        # Удаляем старые фактические данные
        fact_deleted = self.db.query(db_models.ServerMetricsFact).filter(
            db_models.ServerMetricsFact.timestamp < cutoff_date
        ).delete(synchronize_session=False)

        # Удаляем старые предсказания
        pred_deleted = self.db.query(db_models.ServerMetricsPredictions).filter(
            db_models.ServerMetricsPredictions.timestamp < cutoff_date
        ).delete(synchronize_session=False)

        self.db.commit()

        return {
            'fact_records_deleted': fact_deleted,
            'prediction_records_deleted': pred_deleted,
            'cutoff_date': cutoff_date
        }

    def get_database_stats(self) -> Dict:
        """
        Получение статистики базы данных

        Returns:
            Словарь со статистикой
        """
        try:
            # Подсчет записей в таблицах
            fact_count = self.db.query(db_models.ServerMetricsFact).count()
            prediction_count = self.db.query(db_models.ServerMetricsPredictions).count()

            # Подсчет уникальных VM и метрик
            vm_count = self.db.query(db_models.ServerMetricsFact.vm).distinct().count()
            metric_count = self.db.query(db_models.ServerMetricsFact.metric).distinct().count()

            # Временной диапазон данных
            oldest_record = self.db.query(db_models.ServerMetricsFact).order_by(
                db_models.ServerMetricsFact.timestamp
            ).first()

            newest_record = self.db.query(db_models.ServerMetricsFact).order_by(
                desc(db_models.ServerMetricsFact.timestamp)
            ).first()

            stats = {
                'fact_records': fact_count,
                'prediction_records': prediction_count,
                'total_records': fact_count + prediction_count,
                'unique_vms': vm_count,
                'unique_metrics': metric_count,
                'data_volume_mb': self._estimate_data_volume(),
                'oldest_record': oldest_record.timestamp if oldest_record else None,
                'newest_record': newest_record.timestamp if newest_record else None,
                'collection_period_days': (
                    (newest_record.timestamp - oldest_record.timestamp).days
                    if oldest_record and newest_record else 0
                )
            }

            return stats

        except Exception as e:
            print(f"Error getting database stats: {e}")
            return {}

    def _estimate_data_volume(self) -> float:
        """
        Оценка объема данных в базе (в МБ)

        Returns:
            Примерный объем в мегабайтах
        """
        # Примерная оценка: каждая запись ~ 100 байт
        fact_count = self.db.query(db_models.ServerMetricsFact).count()
        pred_count = self.db.query(db_models.ServerMetricsPredictions).count()

        total_bytes = (fact_count + pred_count) * 100
        return round(total_bytes / (1024 * 1024), 2)

    # ================================== МЕТОДЫ ДЛЯ АНАЛИЗА ====================================

    def detect_missing_data(
            self,
            vm: str,
            metric: str,
            start_date: datetime,
            end_date: datetime,
            expected_interval_minutes: int = 30
    ) -> List[Dict]:
        """
        Обнаружение пропущенных данных

        Args:
            vm: Имя виртуальной машины
            metric: Тип метрики
            start_date: Начальная дата
            end_date: Конечная дата
            expected_interval_minutes: Ожидаемый интервал между записями

        Returns:
            Список пропущенных интервалов
        """
        # Получаем все записи в периоде
        records = self.get_historical_metrics(vm, metric, start_date, end_date)

        if len(records) < 2:
            return []

        missing_intervals = []
        expected_interval = timedelta(minutes=expected_interval_minutes)

        for i in range(len(records) - 1):
            current_time = records[i].timestamp
            next_time = records[i + 1].timestamp
            actual_interval = next_time - current_time

            # Если интервал больше ожидаемого более чем в 1.5 раза
            if actual_interval > expected_interval * 1.5:
                missing_intervals.append({
                    'gap_start': current_time,
                    'gap_end': next_time,
                    'gap_duration_minutes': actual_interval.total_seconds() / 60,
                    'expected_interval_minutes': expected_interval_minutes,
                    'missing_points': int((actual_interval.total_seconds() / 60) / expected_interval_minutes) - 1
                })

        return missing_intervals

    def calculate_data_completeness(
            self,
            vm: str,
            metric: str,
            start_date: datetime,
            end_date: datetime,
            expected_interval_minutes: int = 30
    ) -> Dict:
        """
        Расчет полноты данных

        Args:
            vm: Имя виртуальной машины
            metric: Тип метрики
            start_date: Начальная дата
            end_date: Конечная дата
            expected_interval_minutes: Ожидаемый интервал

        Returns:
            Словарь с метриками полноты
        """
        total_minutes = (end_date - start_date).total_seconds() / 60
        expected_points = int(total_minutes / expected_interval_minutes) + 1

        actual_points = self.db.query(db_models.ServerMetricsFact).filter(
            db_models.ServerMetricsFact.vm == vm,
            db_models.ServerMetricsFact.metric == metric,
            db_models.ServerMetricsFact.timestamp >= start_date,
            db_models.ServerMetricsFact.timestamp <= end_date
        ).count()

        completeness_percentage = (actual_points / expected_points * 100) if expected_points > 0 else 0

        missing_intervals = self.detect_missing_data(vm, metric, start_date, end_date, expected_interval_minutes)

        return {
            'expected_points': expected_points,
            'actual_points': actual_points,
            'completeness_percentage': round(completeness_percentage, 2),
            'missing_points': expected_points - actual_points,
            'missing_intervals': missing_intervals,
            'missing_intervals_count': len(missing_intervals)
        }

    # ================================== МЕТОДЫ ДЛЯ МЕТРИК ====================================

    def get_historical_metrics(
            self,
            vm: str,
            metric: str,
            start_date: Optional[datetime] = None,
            end_date: Optional[datetime] = None,
            limit: int = 5000
    ) -> List[db_models.ServerMetricsFact]:
        """
        Получение исторических метрик

        Args:
            vm: Имя виртуальной машины
            metric: Тип метрики
            start_date: Начальная дата
            end_date: Конечная дата
            limit: Максимальное количество записей

        Returns:
            Список записей метрик
        """
        query = self.db.query(db_models.ServerMetricsFact).filter(
            db_models.ServerMetricsFact.vm == vm,
            db_models.ServerMetricsFact.metric == metric
        )

        if start_date:
            query = query.filter(db_models.ServerMetricsFact.timestamp >= start_date)
        if end_date:
            query = query.filter(db_models.ServerMetricsFact.timestamp <= end_date)

        return query.order_by(db_models.ServerMetricsFact.timestamp).limit(limit).all()

    def get_metrics_by_date_range(
            self,
            vm: str,
            metric: str,
            start_date: datetime,
            end_date: datetime,
            limit: int = 5000
    ) -> List[db_models.ServerMetricsFact]:
        """
        Получение метрик по диапазону дат

        Args:
            vm: Имя виртуальной машины
            metric: Тип метрики
            start_date: Начальная дата
            end_date: Конечная дата
            limit: Максимальное количество записей

        Returns:
            Список записей метрик
        """
        return self.get_historical_metrics(vm, metric, start_date, end_date, limit)

    def get_latest_metrics(
            self,
            vm: str,
            metric: str,
            hours: int = 24
    ) -> List[db_models.ServerMetricsFact]:
        """
        Получение последних N часов метрик

        Args:
            vm: Имя виртуальной машины
            metric: Тип метрики
            hours: Количество часов

        Returns:
            Список записей метрик
        """
        cutoff_time = datetime.now() - timedelta(hours=hours)
        return self.get_historical_metrics(vm, metric, start_date=cutoff_time)
