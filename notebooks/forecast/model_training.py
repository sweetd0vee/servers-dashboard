import json
import os
import pickle
from datetime import timedelta

import pandas as pd
from prophet import Prophet

from .config import CONDITIONAL_SEASONALITIES
from .evaluation import calculate_simple_metrics
from .utils import now_utc


def train_model(
    df: pd.DataFrame,
    vm: str,
    metric: str,
    model_storage_path: str,
    best_params: dict = None
):
    model_params = {
        'growth': 'linear',
        'yearly_seasonality': False,
        'interval_width': 0.95,
        'seasonality_mode': 'additive',
        'daily_seasonality': True,
        'weekly_seasonality': True,
        'changepoint_prior_scale': 0.05,
        'seasonality_prior_scale': 10.0,
        'changepoint_range': 0.8,
    }

    added_seasonalities = []

    if best_params:
        model_params.update({
            k: best_params[k] for k in [
                'seasonality_mode', 'daily_seasonality', 'weekly_seasonality',
                'changepoint_prior_scale', 'seasonality_prior_scale', 'changepoint_range'
            ] if k in best_params
        })
        added_seasonalities = best_params.get('added_seasonalities', [])

    model = Prophet(**model_params)

    # Добавляем сезонности ТОЛЬКО если они указаны в added_seasonalities
    for col in added_seasonalities:
        if col in CONDITIONAL_SEASONALITIES:
            spec = CONDITIONAL_SEASONALITIES[col]
            model.add_seasonality(
                name=col,
                period=spec['period'],
                fourier_order=spec['fourier_order'],
                condition_name=col
            )

    model.fit(df)

    # Оценка
    if len(df) >= 100:
        from prophet.diagnostics import cross_validation, performance_metrics
        try:
            df_cv = cross_validation(model, initial='3 days', period='1 day', horizon='1 day')
            df_p = performance_metrics(df_cv)
            metrics = {col: float(df_p[col].mean()) for col in df_p.columns if col in ['mape', 'rmse', 'mae', 'coverage', 'smape']}
            metrics['evaluation_type'] = 'cross_validation'
        except:
            metrics = calculate_simple_metrics(model, df)
    else:
        metrics = calculate_simple_metrics(model, df)

    # Сохраняем
    timestamp = now_utc().strftime('%Y%m%d_%H%M%S')
    model_filename = f"{vm}_{metric}_prophet_{timestamp}.pkl"
    model_path = os.path.join(model_storage_path, model_filename)

    model_data = {
        'model': model,
        'trained_at': now_utc(),
        'metrics': metrics,
        'data_points': len(df),
        'vm': vm,
        'metric': metric,
        'config': model_params,
        'optimized': best_params is not None,
        'optimized_params': best_params,
        'added_seasonalities': added_seasonalities
    }

    with open(model_path, 'wb') as f:
        pickle.dump(model_data, f)

    with open(model_path.replace('.pkl', '_metrics.json'), 'w') as f:
        json.dump(metrics, f, indent=2, default=str)

    return model, metrics, model_path, model_data