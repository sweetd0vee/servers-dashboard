from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

# **Правила анализа загруженности сервера**
# **Загруженный сервер**
# Сервер загружен, если более 20% времени (из 336 интервалов) хотя бы одна метрика превышает пороги:
# а) среднее использование CPU >85%;  *(cpu.usage.average)*
# б) среднее использование памяти >80%;  *(mem.usage.average)*
# в) сумма времени ожидания CPU >10% (в топ-20% пиковых интервалов). *(cpu.ready.summation)*
#
# **Простаивающий сервер**
# Сервер простаивает, если более 80% времени все метрики ниже порогов:
# а) среднее использование CPU <15%; *(cpu.usage.average)*
# б) среднее использование памяти <25%; *(mem.usage.average)*
# в) среднее использование сети <5% от ёмкости; *(net.usage.average)*
#
# **Нормальная работа сервера**
# Нормальная работа серверов (оптимизированная настройка ресурсов) все метрики входят в эти диапазоны
# a) среднее использрвание CPU от 15 до 85%; *(cpu.usage.average)*
# б) среденее использование памяти от 25 до 85%; *(mem.usage.average)*
# в) среднее использование сети от 6 до 85% от ёмкости; *(net.usage.average)*

# Пороговые метрики:
# cpu.usage.average, cpu.ready.summation, mem.usage.average, net.usage.average


class ServerStatus(Enum):
    """Статус сервера"""
    OVERLOADED = "overloaded"  # Загружен
    UNDERLOADED = "underloaded"  # Простаивает
    NORMAL = "normal"  # Норма
    UNKNOWN = "unknown"  # Неизвестно (нет данных)


class AlertSeverity(Enum):
    """Уровень серьезности алерта"""
    CRITICAL = "critical"  # Критический
    WARNING = "warning"  # Предупреждение
    INFO = "info"  # Информационный


@dataclass
class AlertRule:
    """Правило для алерта"""
    name: str
    metric: str
    condition: str  # 'gt' (greater than), 'lt' (less than), 'range', 'percentile_gt'
    thresholds: Dict
    severity: AlertSeverity
    description: str
    time_percentage: float = 0.2  # Процент времени для анализа (20% по умолчанию)


@dataclass
class Alert:
    """Алерт"""
    rule: AlertRule
    value: float
    timestamp: pd.Timestamp
    server: str
    message: str

    def to_dict(self):
        return {
            'server': self.server,
            'rule': self.rule.name,
            'value': self.value,
            'threshold': self.rule.thresholds,
            'severity': self.rule.severity.value,
            'timestamp': self.timestamp,
            'message': self.message
        }


class AlertSystem:
    """Система алертов"""

    def __init__(self, network_capacity_mbps: float = 1000):
        self.rules = self._get_default_rules()
        self.alerts_history = []
        self.network_capacity_mbps = network_capacity_mbps

    def _get_default_rules(self) -> List[AlertRule]:
        """Получение правил по умолчанию"""
        return [
            # Правила для загруженного сервера
            AlertRule(
                name="high_cpu_usage",
                metric="cpu.usage.average",
                condition="gt",
                thresholds={'high': 85},
                severity=AlertSeverity.CRITICAL,
                description="Среднее использование CPU >85%",
                time_percentage=0.2
            ),
            AlertRule(
                name="high_memory_usage",
                metric="mem.usage.average",
                condition="gt",
                thresholds={'high': 80},
                severity=AlertSeverity.CRITICAL,
                description="Среднее использование памяти >80%",
                time_percentage=0.2
            ),
            # AlertRule(
            #     name="cpu_ready_time",
            #     metric="cpu.ready.summation",
            #     condition="percentile_gt",
            #     thresholds={'high': 10, 'percentile': 80},
            #     severity=AlertSeverity.CRITICAL,
            #     description="Сумма времени ожидания CPU >10% (в топ-20% пиковых интервалов)",
            #     time_percentage=0.2
            # ),

            # Правила для простаивающего сервера
            AlertRule(
                name="low_cpu_usage",
                metric="cpu.usage.average",
                condition="lt",
                thresholds={'low': 15},
                severity=AlertSeverity.WARNING,
                description="Среднее использование CPU <15%",
                time_percentage=0.8
            ),
            AlertRule(
                name="low_memory_usage",
                metric="mem.usage.average",
                condition="lt",
                thresholds={'low': 25},
                severity=AlertSeverity.WARNING,
                description="Среднее использование памяти <25%",
                time_percentage=0.8
            ),
            AlertRule(
                name="low_network_usage",
                metric="net.usage.average",
                condition="lt",
                thresholds={'low': 5},
                severity=AlertSeverity.WARNING,
                description="Среднее использование сети <5% от ёмкости",
                time_percentage=0.8
            ),

            # Правила для нормальной работы
            AlertRule(
                name="normal_cpu_range",
                metric="cpu.usage.average",
                condition="range",
                thresholds={'low': 15, 'high': 85},
                severity=AlertSeverity.INFO,
                description="Нормальный диапазон CPU: 15-85%",
                time_percentage=1.0
            ),
            AlertRule(
                name="normal_memory_range",
                metric="mem.usage.average",
                condition="range",
                thresholds={'low': 25, 'high': 85},
                severity=AlertSeverity.INFO,
                description="Нормальный диапазон памяти: 25-85%",
                time_percentage=1.0
            ),
            AlertRule(
                name="normal_network_range",
                metric="net.usage.average",
                condition="range",
                thresholds={'low': 6, 'high': 85},
                severity=AlertSeverity.INFO,
                description="Нормальный диапазон сети: 6-85%",
                time_percentage=1.0
            ),
        ]

    def _calculate_network_usage_percent(self, network_data_mbps: pd.Series) -> pd.Series:
        """Расчет использования сети в процентах от емкости"""
        return (network_data_mbps / self.network_capacity_mbps) * 100

    def _get_top_percentile_data(self, data: pd.Series, percentile: float = 80) -> pd.Series:
        """Получение данных выше указанного перцентиля"""
        threshold = data.quantile(percentile / 100)
        return data[data >= threshold]

    def analyze_server_status(self, server_data: pd.DataFrame, server_name: str) -> Dict:
        """Анализ статуса сервера"""
        if server_data.empty:
            return {
                'status': ServerStatus.UNKNOWN,
                'alerts': [],
                'metrics_summary': {}
            }

        alerts = []

        # Проверяем каждое правило
        for rule in self.rules:
            if rule.metric not in server_data.columns:
                continue

            metric_data = server_data[rule.metric]
            total_intervals = len(metric_data)
            required_intervals = int(total_intervals * rule.time_percentage)

            if rule.condition == "gt":
                # Больше порога
                exceeding_count = (metric_data > rule.thresholds['high']).sum()
                if exceeding_count >= required_intervals:
                    avg_value = metric_data[metric_data > rule.thresholds['high']].mean()
                    alert = Alert(
                        rule=rule,
                        value=avg_value,
                        timestamp=server_data['timestamp'].iloc[-1],
                        server=server_name,
                        message=f"{rule.description}: {avg_value:.1f}% (порог: {rule.thresholds['high']}%)"
                    )
                    alerts.append(alert)

            elif rule.condition == "lt":
                # Меньше порога
                below_count = (metric_data < rule.thresholds['low']).sum()
                if below_count >= required_intervals:
                    avg_value = metric_data[metric_data < rule.thresholds['low']].mean()
                    alert = Alert(
                        rule=rule,
                        value=avg_value,
                        timestamp=server_data['timestamp'].iloc[-1],
                        server=server_name,
                        message=f"{rule.description}: {avg_value:.1f}% (порог: {rule.thresholds['low']}%)"
                    )
                    alerts.append(alert)

            elif rule.condition == "range":
                # В диапазоне
                in_range_count = (
                        (metric_data >= rule.thresholds['low']) &
                        (metric_data <= rule.thresholds['high'])
                ).sum()

                # Для нормального диапазона требуется, чтобы ВСЕ точки были в диапазоне
                if rule.severity == AlertSeverity.INFO and in_range_count == total_intervals:
                    avg_value = metric_data.mean()
                    alert = Alert(
                        rule=rule,
                        value=avg_value,
                        timestamp=server_data['timestamp'].iloc[-1],
                        server=server_name,
                        message=f"{rule.description}: {avg_value:.1f}% (диапазон: {rule.thresholds['low']}-{rule.thresholds['high']}%)"
                    )
                    alerts.append(alert)
                # Для других случаев можно использовать процент времени
                elif rule.severity != AlertSeverity.INFO and in_range_count >= required_intervals:
                    avg_value = metric_data.mean()
                    alert = Alert(
                        rule=rule,
                        value=avg_value,
                        timestamp=server_data['timestamp'].iloc[-1],
                        server=server_name,
                        message=f"{rule.description}: {avg_value:.1f}% (диапазон: {rule.thresholds['low']}-{rule.thresholds['high']}%)"
                    )
                    alerts.append(alert)

            elif rule.condition == "percentile_gt":
                # Для cpu.ready.summation: проверяем топ-20% пиковых интервалов
                percentile = rule.thresholds.get('percentile', 80)
                top_data = self._get_top_percentile_data(metric_data, percentile)

                if not top_data.empty:
                    # Проверяем, превышает ли среднее значение в топовых интервалах порог
                    top_avg = top_data.mean()
                    if top_avg > rule.thresholds['high']:
                        alert = Alert(
                            rule=rule,
                            value=top_avg,
                            timestamp=server_data['timestamp'].iloc[-1],
                            server=server_name,
                            message=f"{rule.description}: {top_avg:.1f}% в топ-{100 - percentile}% интервалов (порог: {rule.thresholds['high']}%)"
                        )
                        alerts.append(alert)

        # Определяем общий статус сервера
        status = self._determine_server_status(alerts, server_data)

        # Сохраняем алерты в историю
        for alert in alerts:
            self.alerts_history.append(alert.to_dict())

        return {
            'status': status,
            'alerts': alerts,
            'metrics_summary': self._get_metrics_summary(server_data)
        }

    def _determine_server_status(self, alerts: List[Alert], server_data: pd.DataFrame) -> ServerStatus:
        """Определение общего статуса сервера по бизнес-правилам"""

        # 1. Проверка на перегрузку (загруженный сервер)
        # Сервер загружен, если более 20% времени хотя бы одна метрика превышает пороги
        overload_criteria = [
            ('cpu.usage.average', 85, 0.2),
            ('mem.usage.average', 80, 0.2),
        ]

        for metric, threshold, time_percentage in overload_criteria:
            if metric in server_data.columns:
                exceeding_count = (server_data[metric] > threshold).sum()
                total_count = len(server_data[metric])
                if exceeding_count / total_count > time_percentage:
                    return ServerStatus.OVERLOADED

        # Проверка cpu.ready.summation для топ-20% пиковых интервалов
        # if 'cpu.ready.summation' in server_data.columns:
        #     top_20_percent = self._get_top_percentile_data(server_data['cpu.ready.summation'], 80)
        #     if not top_20_percent.empty and top_20_percent.mean() > 10:
        #         return ServerStatus.OVERLOADED

        # 2. Проверка на простой (простаивающий сервер)
        # Сервер простаивает, если более 80% времени все метрики ниже порогов
        underload_criteria = [
            ('cpu.usage.average', 15, 0.8),
            ('mem.usage.average', 25, 0.8),
            ('net.usage.average', 5, 0.8),
        ]

        all_underloaded = True
        for metric, threshold, time_percentage in underload_criteria:
            if metric in server_data.columns:
                below_count = (server_data[metric] < threshold).sum()
                total_count = len(server_data[metric])
                if below_count / total_count < time_percentage:
                    all_underloaded = False
                    break

        if all_underloaded:
            return ServerStatus.UNDERLOADED

        # 3. Если не перегружен и не простаивает - нормальная работа
        return ServerStatus.NORMAL

    def _get_metrics_summary(self, server_data: pd.DataFrame) -> Dict:
        """Получение сводки по метрикам"""
        summary = {}

        metrics_to_check = ['cpu.usage.average', 'mem.usage.average', # 'cpu.ready.summation',
                            'net.usage.average']

        for metric in metrics_to_check:
            if metric in server_data.columns:
                summary[metric] = {
                    'mean': float(server_data[metric].mean()),
                    'max': float(server_data[metric].max()),
                    'min': float(server_data[metric].min()),
                    'std': float(server_data[metric].std()),
                    'p95': float(server_data[metric].quantile(0.95)),
                    'time_above_threshold': self._get_time_above_threshold_stats(server_data[metric])
                }

        return summary

    def _get_time_above_threshold_stats(self, data: pd.Series) -> Dict:
        """Статистика времени выше порогов"""
        stats = {}

        if data.name == 'cpu.usage.average':
            thresholds = [15, 85]
        elif data.name == 'mem.usage.average':
            thresholds = [25, 80]
        elif data.name == 'net.usage.average':
            thresholds = [5, 85]
        elif data.name == 'cpu.ready.summation':
            thresholds = [10]
        else:
            thresholds = []

        for threshold in thresholds:
            percentage = (data > threshold).sum() / len(data) * 100
            stats[f'above_{threshold}'] = f'{percentage:.1f}%'

        return stats

    def get_alerts_history(self, limit: int = 100) -> pd.DataFrame:
        """Получение истории алертов"""
        return pd.DataFrame(self.alerts_history[-limit:])

    def update_rule(self, rule_name: str, **kwargs):
        """Обновление правила"""
        for rule in self.rules:
            if rule.name == rule_name:
                for key, value in kwargs.items():
                    if hasattr(rule, key):
                        setattr(rule, key, value)
                break

    def set_network_capacity(self, capacity_mbps: float):
        """Установка емкости сети для расчета процентов"""
        self.network_capacity_mbps = capacity_mbps


# Пример использования
def create_sample_data(n_intervals: int = 336) -> pd.DataFrame:
    """Создание тестовых данных"""
    timestamps = pd.date_range(
        start='2024-01-01',
        periods=n_intervals,
        freq='30min'  # 5-минутные интервалы
    )

    data = {
        'timestamp': timestamps,
        'cpu.usage.average': np.random.uniform(10, 90, n_intervals),
        'mem.usage.average': np.random.uniform(20, 95, n_intervals),
        'cpu.ready.summation': np.random.uniform(0, 20, n_intervals),
        'network_in_mbps': np.random.uniform(10, 800, n_intervals),
    }

    return pd.DataFrame(data)


# Синглтон инстанс
alert_system = AlertSystem()

# Пример использования
if __name__ == "__main__":
    # Создаем тестовые данные
    test_data = create_sample_data()

    # Анализируем сервер
    result = alert_system.analyze_server_status(test_data, "test.csv-server-01")

    print(f"Статус сервера: {result['status'].value}")
    print(f"Количество алертов: {len(result['alerts'])}")

    for alert in result['alerts']:
        print(f"  - {alert.rule.severity.value}: {alert.message}")

    print("\nСводка по метрикам:")
    for metric, stats in result['metrics_summary'].items():
        print(f"  {metric}: среднее={stats['mean']:.1f}%, макс={stats['max']:.1f}%")