from datetime import datetime, timedelta
from enum import Enum
import logging
from typing import Dict, List, Optional, Tuple

import numpy as np


logger = logging.getLogger(__name__)


class AnomalyDetector:
    def __init__(self):
        self.thresholds = {
            'cpu.usage.average': {
                'z_score_threshold': 3.0,
                'rate_of_change_threshold': 20.0,  # % за 30 минут
                'critical_level': 80.0  # % CPU
            },
            'memory.usage.average': {
                'z_score_threshold': 3.0,
                'rate_of_change_threshold': 15.0,
                'critical_level': 90.0
            }
        }

    def detect_anomalies(
            self,
            actual_values: List[float],
            predicted_values: List[float],
            timestamps: List[datetime],
            metric: str
    ) -> List[Dict]:
        """Обнаружение аномалий"""
        anomalies = []

        if len(actual_values) != len(predicted_values):
            logger.error("Mismatch in actual and predicted values length")
            return anomalies

        thresholds = self.thresholds.get(metric, self.thresholds['cpu.usage.average'])

        for i in range(len(actual_values)):
            actual = actual_values[i]
            predicted = predicted_values[i]
            timestamp = timestamps[i]

            # 1. Проверка на критические значения
            if actual >= thresholds['critical_level']:
                anomalies.append({
                    'timestamp': timestamp,
                    'actual': actual,
                    'predicted': predicted,
                    'anomaly_score': 1.0,
                    'severity': 'critical',
                    'type': 'critical_level',
                    'message': f'Critical {metric}: {actual:.1f}%'
                })
                continue

            # 2. Z-score аномалии
            if i > 0:
                # Используем скользящее окно для расчета статистики
                window_start = max(0, i - 10)
                window_values = actual_values[window_start:i]

                if len(window_values) >= 3:
                    mean = np.mean(window_values)
                    std = np.std(window_values)

                    if std > 0:
                        z_score = abs(actual - mean) / std

                        if z_score > thresholds['z_score_threshold']:
                            anomalies.append({
                                'timestamp': timestamp,
                                'actual': actual,
                                'predicted': predicted,
                                'anomaly_score': min(z_score / 5.0, 1.0),
                                'severity': self._get_severity(z_score),
                                'type': 'z_score',
                                'message': f'Statistical anomaly: z-score={z_score:.2f}'
                            })

            # 3. Аномалии прогноза (большое отклонение от предсказания)
            error = abs(actual - predicted)
            if predicted > 0:
                relative_error = (error / predicted) * 100

                if relative_error > 30:  # 30% отклонение
                    anomalies.append({
                        'timestamp': timestamp,
                        'actual': actual,
                        'predicted': predicted,
                        'anomaly_score': min(relative_error / 100, 1.0),
                        'severity': 'high' if relative_error > 50 else 'medium',
                        'type': 'prediction_error',
                        'message': f'Prediction error: {relative_error:.1f}%'
                    })

            # 4. Быстрые изменения (rate of change)
            if i > 0:
                rate_of_change = abs(actual - actual_values[i - 1])
                if rate_of_change > thresholds['rate_of_change_threshold']:
                    anomalies.append({
                        'timestamp': timestamp,
                        'actual': actual,
                        'predicted': predicted,
                        'anomaly_score': min(rate_of_change / 50, 1.0),
                        'severity': 'high' if rate_of_change > 30 else 'medium',
                        'type': 'rate_of_change',
                        'message': f'Rapid change: {rate_of_change:.1f}% in 30min'
                    })

        return anomalies

    def _get_severity(self, z_score: float) -> str:
        """Определение серьезности аномалии"""
        if z_score >= 4.0:
            return 'critical'
        elif z_score >= 3.0:
            return 'high'
        elif z_score >= 2.0:
            return 'medium'
        else:
            return 'low'

    def detect_realtime_anomaly(
            self,
            current_value: float,
            historical_values: List[float],
            predicted_value: Optional[float] = None,
            metric: str = 'cpu.usage.average'
    ) -> Optional[Dict]:
        """Обнаружение аномалий в реальном времени"""
        if len(historical_values) < 10:
            return None

        thresholds = self.thresholds.get(metric, self.thresholds['cpu.usage.average'])

        # Проверка на критические значения
        if current_value >= thresholds['critical_level']:
            return {
                'severity': 'critical',
                'type': 'critical_level',
                'message': f'Critical {metric}: {current_value:.1f}%',
                'score': 1.0
            }

        # Z-score проверка
        mean = np.mean(historical_values)
        std = np.std(historical_values)

        if std > 0:
            z_score = abs(current_value - mean) / std

            if z_score > thresholds['z_score_threshold']:
                return {
                    'severity': self._get_severity(z_score),
                    'type': 'statistical',
                    'message': f'Statistical anomaly: z-score={z_score:.2f}',
                    'score': min(z_score / 5.0, 1.0)
                }

        # Проверка прогноза
        if predicted_value is not None:
            error = abs(current_value - predicted_value)
            relative_error = (error / predicted_value) * 100 if predicted_value > 0 else 0

            if relative_error > 30:
                return {
                    'severity': 'high' if relative_error > 50 else 'medium',
                    'type': 'prediction_error',
                    'message': f'Prediction error: {relative_error:.1f}%',
                    'score': min(relative_error / 100, 1.0)
                }

        return None