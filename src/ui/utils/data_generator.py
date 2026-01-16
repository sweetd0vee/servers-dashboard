"""
Data generator - now loads data from database instead of generating random data.
This file is kept for backward compatibility.
For new code, use data_loader.py directly.
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sys
import os

# Import the new data loader
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

try:
    from data_loader import generate_server_data as load_from_db, generate_forecast as forecast_from_db
    _USE_DATABASE = True
except ImportError:
    _USE_DATABASE = False
    print("Warning: data_loader not available, using fallback generation")


def generate_server_data():
    """
    Load server data from database.
    Falls back to generated data if database is not available.
    """
    # Try to load from database first
    if _USE_DATABASE:
        try:
            df = load_from_db()
            if not df.empty:
                return df
        except Exception as e:
            print(f"Warning: Could not load from database: {e}")
            print("Falling back to generated data")
    
    # Fallback to original generation logic
    return _generate_fallback_data()


def _generate_fallback_data():
    """Генерация тестовых данных с аномалиями и паттернами сбоев (fallback)"""
    servers = [
        "Web-Server-01", "Web-Server-02", "API-Server-01",
        "API-Server-02", "Database-01", "Database-02",
        "Cache-Server-01", "Load-Balancer-01", "File-Server-01",
        "Analytics-Server-01"
    ]

    dates = pd.date_range(start='2024-01-01', end='2024-01-30', freq='H')
    data = []

    # Паттерны сбоев для каждого сервера
    failure_patterns = {
        'Web': {
            'spike_days': [5, 12, 19, 26],  # Дни с пиковыми нагрузками
            'maintenance_hours': [2, 3],  # Часы техобслуживания
        },
        'API': {
            'spike_days': [1, 8, 15, 22, 29],
            'maintenance_hours': [4, 5],
        },
        'Database': {
            'spike_days': [3, 10, 17, 24],
            'maintenance_hours': [0, 1],
            'backup_hours': [2, 3],  # Часы резервного копирования
        },
        'Cache': {
            'spike_days': [6, 13, 20, 27],
            'maintenance_hours': [3, 4],
        }
    }

    for server in servers:
        server_type = server.split('-')[0]
        pattern = failure_patterns.get(server_type, {})

        for date in dates:
            day_of_month = date.day
            hour = date.hour

            # Базовая нагрузка с учетом типа сервера
            if server_type == 'Database':
                base_load = np.random.normal(60, 10)
            elif server_type == 'Cache':
                base_load = np.random.normal(40, 8)
            elif server_type == 'API':
                base_load = np.random.normal(55, 12)
            else:  # Web, Load-Balancer, File, Analytics
                base_load = np.random.normal(50, 15)

            # Сезонность
            if 9 <= hour <= 17:  # Рабочие часы
                base_load += np.random.normal(25, 7)
            elif 18 <= hour <= 22:  # Вечер
                base_load += np.random.normal(12, 4)
            else:  # Ночь
                base_load -= np.random.normal(18, 6)

            # Еженедельные паттерны
            if date.weekday() >= 5:  # Выходные
                base_load *= 0.7

            # Плановые пики нагрузки
            if day_of_month in pattern.get('spike_days', []):
                if 10 <= hour <= 16:
                    base_load *= 1.5

            # Техническое обслуживание
            if hour in pattern.get('maintenance_hours', []):
                base_load *= 0.3

            # Резервное копирование для баз данных
            if server_type == 'Database' and hour in pattern.get('backup_hours', []):
                disk_io_multiplier = 1.5
            else:
                disk_io_multiplier = 1.0

            noise = np.random.normal(0, 7)
            load = max(5, min(100, base_load + noise))

            # Генерация аномалий (5% случаев)
            has_anomaly = np.random.random() < 0.05
            if has_anomaly:
                # Типы аномалий
                anomaly_type = np.random.choice(['spike', 'drop', 'oscillation'])
                if anomaly_type == 'spike':
                    load = min(100, load * np.random.uniform(1.5, 3.0))
                elif anomaly_type == 'drop':
                    load = max(5, load * np.random.uniform(0.1, 0.5))
                else:  # oscillation
                    load = load * np.random.uniform(0.8, 1.2)

            # Метрики с учетом нагрузки и типа сервера
            if server_type == 'Database':
                cpu_usage = load * 0.7 + np.random.normal(15, 8)
                memory_usage = load * 0.8 + np.random.normal(25, 12)
                disk_usage = load * 0.9 + np.random.normal(10, 6)
                disk_latency = load * 0.3 + np.random.uniform(5, 20)
            elif server_type == 'Cache':
                cpu_usage = load * 0.6 + np.random.normal(8, 4)
                memory_usage = load * 0.95 + np.random.normal(5, 3)  # Кэш использует много памяти
                disk_usage = load * 0.2 + np.random.normal(10, 5)
                disk_latency = np.random.uniform(1, 10)  # SSD обычно
            else:
                cpu_usage = load * 0.8 + np.random.normal(10, 5)
                memory_usage = load * 0.6 + np.random.normal(20, 10)
                disk_usage = load * 0.7 + np.random.normal(15, 8)
                disk_latency = np.random.uniform(5, 35)

            # Сетевой трафик
            if server_type == 'Web' or server_type == 'API':
                network_in = load * 15 + np.random.normal(150, 50)
                network_out = load * 20 + np.random.normal(200, 60)
                network_usage = (network_in + network_out) / 2
            elif server_type == 'Database':
                network_in = load * 5 + np.random.normal(50, 20)
                network_out = load * 8 + np.random.normal(80, 30)
                network_usage = (network_in + network_out) / 2
            else:
                network_in = load * 10 + np.random.normal(100, 30)
                network_out = load * 12 + np.random.normal(120, 35)
                network_usage = (network_in + network_out) / 2

            # CPU ready time зависит от нагрузки
            cpu_ready_summation = np.random.uniform(0, load * 0.25)

            # Ошибки зависят от нагрузки
            if load > 80:
                error_rate = np.random.poisson(0.5)
            elif load > 60:
                error_rate = np.random.poisson(0.2)
            else:
                error_rate = np.random.poisson(0.05)

            data.append({
                'server': server,
                'timestamp': date,
                'load_percentage': load,
                'cpu.usage.average': min(100, cpu_usage),
                'mem.usage.average': min(100, memory_usage),
                'net.usage.average': max(0, network_usage),
                'cpu.ready.summation': cpu_ready_summation,
                'disk_latency': max(1, disk_latency),
                'disk.usage.average': min(100, disk_usage),
                'errors': error_rate,
                'server_type': server_type,
                'has_anomaly': has_anomaly,
                'weekday': date.weekday(),
                'hour_of_day': hour,
                'is_business_hours': 1 if 9 <= hour <= 17 else 0,
                'is_weekend': 1 if date.weekday() >= 5 else 0
            })

    df = pd.DataFrame(data)

    # Добавляем скользящие средние
    for server in servers:
        mask = df['server'] == server
        df.loc[mask, 'load_ma_6h'] = df.loc[mask, 'load_percentage'].rolling(6, min_periods=1).mean()
        df.loc[mask, 'load_ma_24h'] = df.loc[mask, 'load_percentage'].rolling(24, min_periods=1).mean()

    return df


def generate_forecast(historical_data, hours=48):
    """
    Generate forecast from historical data.
    Uses database loader if available, otherwise uses simple forecast.
    """
    if _USE_DATABASE:
        try:
            return forecast_from_db(historical_data, hours)
        except Exception as e:
            print(f"Warning: Could not use database forecast: {e}")
    
    # Fallback to original forecast logic
    return _generate_fallback_forecast(historical_data, hours)


def _generate_fallback_forecast(historical_data, hours=48):
    """Генерация прогноза (fallback)"""
    if historical_data.empty:
        return pd.DataFrame()

    last_date = historical_data['timestamp'].max()
    forecast_dates = [last_date + timedelta(hours=i) for i in range(1, hours + 1)]

    last_values = historical_data['load_percentage'].tail(24).values
    base_forecast = np.mean(last_values)

    forecast_values = []
    for i, date in enumerate(forecast_dates):
        hour = date.hour
        if 9 <= hour <= 17:
            seasonality = np.random.normal(15, 3)
        elif 18 <= hour <= 22:
            seasonality = np.random.normal(8, 2)
        else:
            seasonality = np.random.normal(-10, 3)

        trend = i * 0.02
        forecast_val = base_forecast + seasonality + trend
        forecast_val = max(5, min(100, forecast_val))
        forecast_values.append(forecast_val)

    return pd.DataFrame({
        'timestamp': forecast_dates,
        'load_percentage': forecast_values
    })