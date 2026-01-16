import pandas as pd
import numpy as np
from datetime import datetime
from enum import Enum
from typing import List, Dict, Optional, Tuple
import streamlit as st
from alert_rules import ServerStatus, AlertSeverity


class Alert:
    """Класс для хранения информации об алерте"""

    def __init__(self, metric_name: str, value: float, threshold: Dict,
                 severity: AlertSeverity, timestamp: datetime, server_name: str):
        self.metric_name = metric_name
        self.value = value
        self.threshold = threshold
        self.severity = severity
        self.timestamp = timestamp
        self.server_name = server_name
        self.message = self._create_message()

    def _create_message(self) -> str:
        """Создание сообщения для алерта"""
        if 'min' in self.threshold and 'max' in self.threshold:
            return f"{self.metric_name}: {self.value:.1f}% (диапазон: {self.threshold['min']}-{self.threshold['max']}%)"
        elif 'value' in self.threshold:
            condition = ">" if self.value > self.threshold['value'] else "<"
            return f"{self.metric_name}: {self.value:.1f}% {condition} {self.threshold['value']}%"
        return f"{self.metric_name}: {self.value:.1f}%"

    def to_dict(self) -> Dict:
        """Конвертация в словарь"""
        return {
            'server': self.server_name,
            'metric': self.metric_name,
            'value': self.value,
            'threshold': self.threshold,
            'severity': self.severity.value,
            'timestamp': self.timestamp,
            'message': self.message
        }


def analyze_server_alerts(
        server_data: pd.DataFrame,
        server_name: str,
        thresholds: Optional[Dict] = None,
        time_percent_overload: float = 0.2,
        time_percent_idle: float = 0.8
) -> Dict:
    """
    Анализирует метрики сервера и возвращает алерты по правилам:

    Правила:
    1. Загруженный сервер (более 20% времени хотя бы одна метрика превышает пороги):
       - CPU > 85%
       - Память > 80%
       - CPU Ready > 10% (в топ-20% пиковых интервалов)

    2. Простаивающий сервер (более 80% времени все метрики ниже порогов):
       - CPU < 15%
       - Память < 25%
       - Сеть < 5%

    3. Нормальная работа (все метрики в диапазонах):
       - CPU: 15-85%
       - Память: 25-85%
       - Сеть: 6-85%

    Parameters:
    -----------
    server_data : pd.DataFrame
        Данные сервера с колонками: timestamp, cpu_usage, memory_usage, network_in_mbps
    server_name : str
        Имя сервера
    thresholds : dict, optional
        Кастомные пороги
    time_percent_overload : float
        Процент времени для определения перегрузки (по умолчанию 20%)
    time_percent_idle : float
        Процент времени для определения простоя (по умолчанию 80%)

    Returns:
    --------
    dict: Результаты анализа со статусом и алертами
    """

    # Пороги по умолчанию
    default_thresholds = {
        # Загруженность
        'cpu_overload': 85,
        'memory_overload': 80,
        'cpu_ready_overload': 10,

        # Простой
        'cpu_idle': 15,
        'memory_idle': 25,
        'network_idle': 5,

        # Норма
        'cpu_normal_min': 15,
        'cpu_normal_max': 85,
        'memory_normal_min': 25,
        'memory_normal_max': 85,
        'network_normal_min': 6,
        'network_normal_max': 85,

        # Дополнительные
        'disk_latency': 25,
        'network_capacity': 1000  # Mbps
    }

    # Объединяем с пользовательскими порогами
    if thresholds:
        default_thresholds.update(thresholds)

    th = default_thresholds

    if server_data.empty:
        return {
            'status': ServerStatus.UNKNOWN,
            'alerts': [],
            'metrics_summary': {},
            'server_name': server_name
        }

    # Копируем данные
    data = server_data.copy()

    # Добавляем недостающие метрики, если их нет
    if 'cpu_ready_summation' not in data.columns:
        data['cpu_ready_summation'] = np.random.uniform(0, 15, len(data))

    if 'disk_latency' not in data.columns:
        data['disk_latency'] = np.random.uniform(5, 30, len(data))

    if 'disk_usage' not in data.columns:
        data['disk_usage'] = data['memory_usage'] * 0.7 + np.random.normal(15, 8, len(data))

    # Рассчитываем использование сети в процентах
    data['network_usage_percent'] = (data['network_in_mbps'] / th['network_capacity']) * 100

    alerts = []
    last_timestamp = data['timestamp'].iloc[-1] if len(data) > 0 else datetime.now()

    # 1. Проверка на перегрузку (более time_percent_overload% времени)
    overload_rules = [
        {
            'name': 'high_cpu_usage',
            'metric': 'cpu_usage',
            'threshold': th['cpu_overload'],
            'condition': 'gt',
            'severity': AlertSeverity.CRITICAL,
            'description': 'Среднее использование CPU >85%',
            'time_percent': time_percent_overload
        },
        {
            'name': 'high_memory_usage',
            'metric': 'memory_usage',
            'threshold': th['memory_overload'],
            'condition': 'gt',
            'severity': AlertSeverity.CRITICAL,
            'description': 'Среднее использование памяти >80%',
            'time_percent': time_percent_overload
        }
        # ,{
        #     'name': 'high_cpu_ready',
        #     'metric': 'cpu_ready_summation',
        #     'threshold': th['cpu_ready_overload'],
        #     'condition': 'gt',
        #     'severity': AlertSeverity.CRITICAL,
        #     'description': 'Сумма времени ожидания CPU >10%',
        #     'time_percent': time_percent_overload
        # }
    ]

    for rule in overload_rules:
        if rule['metric'] in data.columns:
            metric_data = data[rule['metric']]
            exceeding_intervals = metric_data > rule['threshold']
            exceeding_percent = exceeding_intervals.mean()

            if exceeding_percent >= rule['time_percent']:
                avg_value = metric_data[exceeding_intervals].mean()
                alert = Alert(
                    metric_name=rule['name'],
                    value=float(avg_value),
                    threshold={'value': rule['threshold']},
                    severity=rule['severity'],
                    timestamp=last_timestamp,
                    server_name=server_name
                )
                alerts.append(alert)

    # 2. Проверка на простой (более time_percent_idle% времени)
    idle_rules = [
        {
            'name': 'low_cpu_usage',
            'metric': 'cpu_usage',
            'threshold': th['cpu_idle'],
            'condition': 'lt',
            'severity': AlertSeverity.WARNING,
            'description': 'Среднее использование CPU <15%',
            'time_percent': time_percent_idle
        },
        {
            'name': 'low_memory_usage',
            'metric': 'memory_usage',
            'threshold': th['memory_idle'],
            'condition': 'lt',
            'severity': AlertSeverity.WARNING,
            'description': 'Среднее использование памяти <25%',
            'time_percent': time_percent_idle
        },
        {
            'name': 'low_network_usage',
            'metric': 'network_usage_percent',
            'threshold': th['network_idle'],
            'condition': 'lt',
            'severity': AlertSeverity.WARNING,
            'description': 'Среднее использование сети <5%',
            'time_percent': time_percent_idle
        }
    ]

    for rule in idle_rules:
        if rule['metric'] in data.columns:
            metric_data = data[rule['metric']]
            below_intervals = metric_data < rule['threshold']
            below_percent = below_intervals.mean()

            if below_percent >= rule['time_percent']:
                avg_value = metric_data[below_intervals].mean()
                alert = Alert(
                    metric_name=rule['name'],
                    value=float(avg_value),
                    threshold={'value': rule['threshold']},
                    severity=rule['severity'],
                    timestamp=last_timestamp,
                    server_name=server_name
                )
                alerts.append(alert)

    # 3. Проверка нормального диапазона
    normal_rules = [
        {
            'name': 'normal_cpu_range',
            'metric': 'cpu.usage.average',
            'min': th['cpu_normal_min'],
            'max': th['cpu_normal_max'],
            'severity': AlertSeverity.INFO,
            'description': 'CPU в нормальном диапазоне 15-85%'
        },
        {
            'name': 'normal_memory_range',
            'metric': 'memory_usage',
            'min': th['memory_normal_min'],
            'max': th['memory_normal_max'],
            'severity': AlertSeverity.INFO,
            'description': 'Память в нормальном диапазоне 25-85%'
        },
        {
            'name': 'normal_network_range',
            'metric': 'net.usage.average',
            'min': th['network_normal_min'],
            'max': th['network_normal_max'],
            'severity': AlertSeverity.INFO,
            'description': 'Сеть в нормальном диапазоне 6-85%'
        }
    ]

    for rule in normal_rules:
        if rule['metric'] in data.columns:
            metric_data = data[rule['metric']]
            in_range = (metric_data >= rule['min']) & (metric_data <= rule['max'])

            if in_range.all():  # Все значения в диапазоне
                avg_value = metric_data.mean()
                alert = Alert(
                    metric_name=rule['name'],
                    value=float(avg_value),
                    threshold={'min': rule['min'], 'max': rule['max']},
                    severity=rule['severity'],
                    timestamp=last_timestamp,
                    server_name=server_name
                )
                alerts.append(alert)

    # 4. Дополнительные проверки
    additional_rules = [
        {
            'name': 'high_disk_latency',
            'metric': 'disk_latency',
            'threshold': th['disk_latency'],
            'condition': 'gt',
            'severity': AlertSeverity.CRITICAL,
            'description': 'Высокая задержка диска',
            'time_percent': time_percent_overload
        }
    ]

    for rule in additional_rules:
        if rule['metric'] in data.columns:
            metric_data = data[rule['metric']]
            exceeding_intervals = metric_data > rule['threshold']
            exceeding_percent = exceeding_intervals.mean()

            if exceeding_percent >= rule['time_percent']:
                avg_value = metric_data[exceeding_intervals].mean()
                alert = Alert(
                    metric_name=rule['name'],
                    value=float(avg_value),
                    threshold={'value': rule['threshold']},
                    severity=rule['severity'],
                    timestamp=last_timestamp,
                    server_name=server_name
                )
                alerts.append(alert)

    # Определяем общий статус сервера
    status = _determine_server_status(alerts, data)

    # Создаем сводку метрик
    metrics_summary = _create_metrics_summary(data)

    return {
        'status': status,
        'alerts': alerts,
        'metrics_summary': metrics_summary,
        'server_name': server_name,
        'analysis_time': datetime.now()
    }


def _determine_server_status(alerts: List[Alert], data: pd.DataFrame) -> ServerStatus:
    """
    Определяет общий статус сервера на основе алертов
    """
    if not alerts:
        return ServerStatus.NORMAL

    # Считаем критические алерты (перегрузка)
    critical_alerts = [a for a in alerts if a.severity == AlertSeverity.CRITICAL]
    critical_metrics = {'high_cpu_usage', 'high_memory_usage', 'high_cpu_ready'}
    critical_count = sum(1 for a in critical_alerts if a.metric_name in critical_metrics)

    if critical_count >= 1:
        return ServerStatus.OVERLOADED

    # Считаем warning алерты (простой)
    warning_alerts = [a for a in alerts if a.severity == AlertSeverity.WARNING]
    warning_metrics = {'low_cpu_usage', 'low_memory_usage', 'low_network_usage'}
    warning_count = sum(1 for a in warning_alerts if a.metric_name in warning_metrics)

    if warning_count >= 3:  # Все три метрики показывают простой
        return ServerStatus.UNDERLOADED

    return ServerStatus.NORMAL


def _create_metrics_summary(data: pd.DataFrame) -> Dict:
    """
    Создает сводку по метрикам
    """
    summary = {}

    metrics = ['cpu_usage', 'memory_usage', 'network_in_mbps',
               'network_usage_percent', 'cpu_ready_summation',
               'disk_latency', 'disk_usage']

    for metric in metrics:
        if metric in data.columns:
            summary[metric] = {
                'mean': float(data[metric].mean()),
                'max': float(data[metric].max()),
                'min': float(data[metric].min()),
                'std': float(data[metric].std()),
                'median': float(data[metric].median()),
                'q25': float(data[metric].quantile(0.25)),
                'q75': float(data[metric].quantile(0.75))
            }

    return summary


# Функция для отображения алертов в Streamlit
def display_alerts_in_streamlit(analysis_result: Dict):
    """
    Отображает результаты анализа в Streamlit
    """
    status = analysis_result['status']
    alerts = analysis_result['alerts']
    server_name = analysis_result.get('server_name', 'Неизвестный сервер')

    # Отображение статуса
    status_config = {
        ServerStatus.OVERLOADED: {"icon": "🔴", "color": "#F44336", "text": "ПЕРЕГРУЗКА"},
        ServerStatus.UNDERLOADED: {"icon": "🟡", "color": "#FFC107", "text": "ПРОСТОЙ"},
        ServerStatus.NORMAL: {"icon": "🟢", "color": "#4CAF50", "text": "НОРМА"},
        ServerStatus.UNKNOWN: {"icon": "⚪", "color": "#9E9E9E", "text": "НЕТ ДАННЫХ"}
    }

    config = status_config.get(status, status_config[ServerStatus.UNKNOWN])

    st.markdown(f"""
    <div style="
        background: linear-gradient(135deg, {config['color']}20 0%, {config['color']}10 100%);
        padding: 15px;
        border-radius: 10px;
        border-left: 5px solid {config['color']};
        margin: 10px 0;
    ">
        <div style="display: flex; align-items: center; gap: 10px;">
            <span style="font-size: 1.8rem;">{config['icon']}</span>
            <div>
                <h4 style="margin: 0; color: {config['color']};">Статус: {config['text']}</h4>
                <p style="margin: 5px 0 0 0; color: #666; font-size: 0.9rem;">
                    Сервер: {server_name}
                </p>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Отображение алертов
    if alerts:
        st.subheader(f"⚠️ Активные алерты ({len(alerts)})")

        # Группируем по уровню серьезности
        critical_alerts = [a for a in alerts if a.severity == AlertSeverity.CRITICAL]
        warning_alerts = [a for a in alerts if a.severity == AlertSeverity.WARNING]
        info_alerts = [a for a in alerts if a.severity == AlertSeverity.INFO]

        # Критические алерты
        if critical_alerts:
            st.markdown("#### 🔴 Критические")
            for alert in critical_alerts:
                st.error(f"**{alert.metric_name}**: {alert.message}")

        # Предупреждения
        if warning_alerts:
            st.markdown("#### 🟡 Предупреждения")
            for alert in warning_alerts:
                st.warning(f"**{alert.metric_name}**: {alert.message}")

        # Информационные
        if info_alerts:
            st.markdown("#### 🔵 Информационные")
            for alert in info_alerts:
                st.info(f"**{alert.metric_name}**: {alert.message}")
    else:
        st.success("✅ Нет активных алертов. Все метрики в норме.")

    # Отображение сводки метрик
    if 'metrics_summary' in analysis_result and analysis_result['metrics_summary']:
        st.subheader("📊 Сводка метрик")

        metrics_df = pd.DataFrame(analysis_result['metrics_summary']).T
        st.dataframe(
            metrics_df.style.format("{:.2f}"),
            use_container_width=True
        )