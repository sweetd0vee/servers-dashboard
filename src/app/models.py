"""
Модели для хранения метрик серверов и прогнозов.
Соответствующие таблицам server_metrics_fact и server_metrics_predictions в PostgreSQL.
"""

import uuid

from connection import Base, engine
from sqlalchemy import (DECIMAL, CheckConstraint, Column, DateTime, Index,
                        String, UniqueConstraint, text)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func


class ServerMetricsFact(Base):
    """
    Модель для хранения фактических метрик серверов.
    Соответствующая таблице server_metrics_fact в PostgreSQL.
    """
    __tablename__ = "server_metrics_fact"

    __table_args__ = (
        UniqueConstraint('vm', 'timestamp', 'metric', name='uq_vm_timestamp_metric'),
        Index('idx_vm_timestamp_metric', 'vm', 'timestamp', 'metric'),
        CheckConstraint('timestamp <= CURRENT_TIMESTAMP', name='chk_timestamp_not_future'),
        {'comment': 'Фактическая таблица метрик серверов. Хранит исторические данные метрик.'}
    )

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
        comment='Уникальный идентификатор записи'
    )

    vm = Column(
        String(255),
        nullable=False,
        index=True,
        comment='Идентификатор виртуального сервера'
    )

    timestamp = Column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        comment='Временная метка измерения метрики (часовой пояс UTC)'
    )

    metric = Column(
        String(255),
        nullable=False,
        comment='Наименование метрики (cpu_usage, memory_usage, disk_io, etc.)'
    )

    value = Column(
        DECIMAL(20, 5),
        nullable=True,
        index=True,
        comment='Фактическое значение метрики. Точность: 20 цифр, 5 знаков после запятой'
    )

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment='Дата и время создания записи в БД'
    )

    def __repr__(self):
        return (
            f"<ServerMetricsFact(vm='{self.vm}', "
            f"timestamp='{self.timestamp}', "
            f"metric='{self.metric}', "
            f"value={self.value})>"
        )

    def to_dict(self):
        """Преобразовать в словарь для API"""
        return {
            'id': str(self.id),
            'vm': self.vm,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'metric': self.metric,
            'value': float(self.value) if self.value else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class ServerMetricsPredictions(Base):
    """
    Модель для хранения предсказанных метрик серверов.
    Соответствующая таблице server_metrics_predictions в PostgreSQL.
    """
    __tablename__ = "server_metrics_predictions"

    __table_args__ = (
        UniqueConstraint('vm', 'timestamp', 'metric', name='uq_vm_timestamp_metric_pred'),
        Index('idx_vm_timestamp_metric_pred', 'vm', 'timestamp', 'metric'),
        # CheckConstraint('prediction_horizon > 0', name='chk_positive_horizon'),
        {'comment': 'Таблица предсказаний метрик серверов. Хранит прогнозные значения.'}
    )

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
        comment='Уникальный идентификатор предсказания'
    )

    vm = Column(
        String(255),
        nullable=False,
        index=True,
        comment='Идентификатор виртуального сервера'
    )

    timestamp = Column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        comment='Временная метка для которой сделано предсказание'
    )

    metric = Column(
        String(255),
        nullable=False,
        comment='Наименование метрики (cpu_usage, memory_usage, disk_io, etc.)'
    )

    value_predicted = Column(
        DECIMAL(20, 5),
        nullable=False,
        comment='Предсказанное значение метрики'
    )

    lower_bound = Column(
        DECIMAL(20, 5),
        nullable=True,
        comment='Нижняя граница доверительного интервала'
    )

    upper_bound = Column(
        DECIMAL(20, 5),
        nullable=True,
        comment='Верхняя граница доверительного интервала'
    )

    # По дефолту зададим горизонт предсказаний, например, 1-3 дня
    # prediction_horizon = Column(
    #     Integer,
    #     nullable=False,
    #     default=1,
    #     comment='Горизонт предсказания в минутах'
    # )

    # Наверно не обязательно TODO подумать
    # model_version = Column(
    #     String(100),
    #     nullable=False,
    #     default='v1.0',
    #     comment='Версия модели использованной для предсказания'
    # )

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment='Дата и время создания предсказания'
    )

    def __repr__(self):
        return (
            f"<ServerMetricsPrediction(vm='{self.vm}', "
            f"timestamp='{self.timestamp}', "
            f"metric='{self.metric}', "
            f"predicted_value={self.value_predicted}"
        )


    def to_dict(self):
        """Преобразовать в словарь для API"""
        return {
            'id': str(self.id),
            'vm': self.vm,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'metric': self.metric,
            'value_predicted': float(self.value_predicted) if self.value_predicted else None,
            'lower_bound': float(self.lower_bound) if self.lower_bound else None,
            'upper_bound': float(self.upper_bound) if self.upper_bound else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


def create_tables_with_optimizations():
    """
    Создать все таблицы с дополнительными оптимизациями
    """
    # Создание базовых таблиц
    Base.metadata.create_all(engine)

    # Дополнительные оптимизации
    with engine.connect() as conn:
        # Оптимизация для fact таблицы
        conn.execute(
            text("ALTER TABLE server_metrics_fact SET (fillfactor = 90);")
        )

        # Оптимизация для predictions таблицы
        conn.execute(
            text("ALTER TABLE server_metrics_predictions SET (fillfactor = 90);")
        )

        # Анализ всех таблиц
        for table in ['server_metrics_fact', 'server_metrics_predictions']:
            conn.execute(text(f"ANALYZE {table};"))


# Создание таблиц при импорте (опционально)
if __name__ == "__main__":
    create_tables_with_optimizations()
    print("Таблицы успешно созданы и оптимизированы")
