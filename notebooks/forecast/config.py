# config.py
from typing import Dict, List


# Пути и параметры по умолчанию
MODEL_STORAGE_PATH = "./models_storage"

# Grid для подбора гиперпараметров
DEFAULT_PARAM_GRID = {
    'changepoint_prior_scale': [0.001, 0.01, 0.05, 0.1, 0.5],
    'seasonality_prior_scale': [2.0, 12.0, 24.0, 48.0],
    'seasonality_mode': ['additive', 'multiplicative'],
    'changepoint_range': [0.8, 0.9, 0.95],
    'weekly_seasonality': [True, False],
    'daily_seasonality': [True, False]
}

# Условные сезонности — определяем по наличию признаков
CONDITIONAL_SEASONALITIES = {
    'is_work_hours': {'period': 1, 'fourier_order': 5},
    'is_night': {'period': 1, 'fourier_order': 3},
    'is_weekend': {'period': 1, 'fourier_order': 3},
}