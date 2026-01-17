from datetime import datetime, timedelta
from typing import Dict, List, Optional

import models as db_models
import schemas as pydantic_models
from sqlalchemy import and_, desc, func
from sqlalchemy.orm import Session

from base_logger import logger


class FactsCRUD:
    def __init__(self, db: Session):
        self.db = db

    # =================================== ФАКТИЧЕСКИЕ МЕТРИКИ =====================================

    def create_metric_fact(self, metric: pydantic_models.MetricFact) -> db_models.ServerMetricsFact:
        """
        Создание или обновление записи фактической метрики (upsert по vm + metric + timestamp)

        Args:
            metric: Данные метрики

        Returns:
            Созданная или обновлённая запись
        """
        existing = self.db.query(db_models.ServerMetricsFact).filter(
            db_models.ServerMetricsFact.vm == metric.vm,
            db_models.ServerMetricsFact.metric == metric.metric,
            db_models.ServerMetricsFact.timestamp == metric.timestamp
        ).first()

        if existing:
            existing.value = metric.value
            self.db.commit()
            self.db.refresh(existing)
            return existing

        db_metric = db_models.ServerMetricsFact(
            vm=metric.vm,
            timestamp=metric.timestamp,
            metric=metric.metric,
            value=metric.value
        )
        self.db.add(db_metric)
        self.db.commit()
        self.db.refresh(db_metric)
        return db_metric

    def create_metrics_fact_batch(self, metrics: List[pydantic_models.MetricFact]) -> int:
        """
        Пакетное создание/обновление фактических метрик

        Args:
            metrics: Список метрик

        Returns:
            Количество успешно обработанных записей
        """
        created_count = 0
        for metric in metrics:
            try:
                self.create_metric_fact(metric)
                created_count += 1
            except Exception as e:
                logger.error(f"Error creating metric {metric.vm}/{metric.metric} at {metric.timestamp}: {e}")
        return created_count

    def get_metrics_fact(
        self,
        vm: str,
        metric: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 5000
    ) -> List[db_models.ServerMetricsFact]:
        """
        Получение исторических метрик с фильтрацией по времени

        Args:
            vm: Имя виртуальной машины
            metric: Тип метрики
            start_date: Начальная дата (включительно)
            end_date: Конечная дата (включительно)
            limit: Максимальное количество записей

        Returns:
            Список записей, отсортированных по времени (ASC)
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

    def get_latest_metrics(self, vm: str, metric: str, hours: int = 24) -> List[db_models.ServerMetricsFact]:
        """
        Получить данные за последние N часов

        Args:
            vm: Имя виртуальной машины
            metric: Тип метрики
            hours: Количество часов (по умолчанию 24)

        Returns:
            Список записей, отсортированных по времени (ASC)
        """
        cutoff_time = datetime.now() - timedelta(hours=hours)
        return self.get_metrics_fact(vm, metric, start_date=cutoff_time)

    def get_metrics_as_dataframe(
        self,
        vm: str,
        metric: str,
        start_date: datetime,
        end_date: datetime
    ) -> Optional[Dict[str, List]]:
        """
        Получение метрик в формате, совместимом с Prophet ({'ds': [...], 'y': [...]})

        Args:
            vm: Имя виртуальной машины
            metric: Тип метрики
            start_date: Начальная дата
            end_date: Конечная дата

        Returns:
            Словарь с ключами 'ds' (список datetime) и 'y' (список float) или None
        """
        metrics = self.get_metrics_fact(vm, metric, start_date, end_date)

        if not metrics:
            return None

        return {
            'ds': [record.timestamp for record in metrics],
            'y': [float(record.value) for record in metrics]
        }

    def get_metrics_fact_statistics(
        self,
        vm: str,
        metric: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict:
        """
        Получение агрегированной статистики по метрике

        Returns:
            Словарь: count, min, max, avg, stddev, period
        """
        query = self.db.query(
            func.count(db_models.ServerMetricsFact.id).label('count'),
            func.min(db_models.ServerMetricsFact.value).label('min'),
            func.max(db_models.ServerMetricsFact.value).label('max'),
            func.avg(db_models.ServerMetricsFact.value).label('avg'),
            func.stddev(db_models.ServerMetricsFact.value).label('stddev')
        ).filter(
            db_models.ServerMetricsFact.vm == vm,
            db_models.ServerMetricsFact.metric == metric
        )

        if start_date:
            query = query.filter(db_models.ServerMetricsFact.timestamp >= start_date)
        if end_date:
            query = query.filter(db_models.ServerMetricsFact.timestamp <= end_date)

        result = query.first()

        if not result or result.count == 0:
            return {
                'count': 0,
                'min': 0.0,
                'max': 0.0,
                'avg': 0.0,
                'stddev': 0.0,
                'period': {
                    'start': start_date.isoformat() if start_date else None,
                    'end': end_date.isoformat() if end_date else None
                }
            }

        return {
            'count': result.count,
            'min': float(result.min) if result.min is not None else 0.0,
            'max': float(result.max) if result.max is not None else 0.0,
            'avg': float(result.avg) if result.avg is not None else 0.0,
            'stddev': float(result.stddev) if result.stddev is not None else 0.0,
            'period': {
                'start': start_date.isoformat() if start_date else None,
                'end': end_date.isoformat() if end_date else None
            }
        }
