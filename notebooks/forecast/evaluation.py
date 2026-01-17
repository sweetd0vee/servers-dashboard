import logging

import numpy as np
import pandas as pd
from prophet import Prophet
from prophet.diagnostics import cross_validation, performance_metrics


logger = logging.getLogger(__name__)


def calculate_simple_metrics(model: Prophet, df: pd.DataFrame) -> dict:
    try:
        forecast = model.predict(df[['ds']])
        y_true = df['y'].values
        y_pred = forecast['yhat'].values

        mae = np.mean(np.abs(y_true - y_pred))
        mse = np.mean((y_true - y_pred) ** 2)
        rmse = np.sqrt(mse)

        epsilon = 1e-10
        safe_y_true = np.where(y_true == 0, epsilon, y_true)
        mape = np.mean(np.abs((y_true - y_pred) / safe_y_true)) * 100
        smape = 200 * np.mean(np.abs(y_pred - y_true) / (np.abs(y_pred) + np.abs(y_true) + epsilon))

        coverage = 0.0
        if 'yhat_lower' in forecast.columns and 'yhat_upper' in forecast.columns:
            in_interval = (y_true >= forecast['yhat_lower']) & (y_true <= forecast['yhat_upper'])
            coverage = np.mean(in_interval) * 100

        return {
            'mape': float(mape),
            'rmse': float(rmse),
            'mae': float(mae),
            'coverage': float(coverage),
            'smape': float(smape),
            'mse': float(mse),
            'evaluation_type': 'simple'
        }
    except Exception as e:
        logger.error(f"Simple evaluation failed: {e}")
        return {k: 0.0 for k in ['mape', 'rmse', 'mae', 'coverage', 'smape', 'mse']}