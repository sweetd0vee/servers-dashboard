import random
import logging
from typing import Dict, Any, List, Optional
from itertools import product
from prophet import Prophet
from prophet.diagnostics import cross_validation, performance_metrics
import numpy as np
import pandas as pd
from .config import DEFAULT_PARAM_GRID, CONDITIONAL_SEASONALITIES
from .evaluation import calculate_simple_metrics


logger = logging.getLogger(__name__)


def tune_hyperparameters(
    df: pd.DataFrame,
    param_grid: Optional[Dict[str, list]] = None,
    max_combinations: int = 50
) -> Optional[Dict[str, Any]]:

    if param_grid is None:
        param_grid = DEFAULT_PARAM_GRID

    if max_combinations <= 0:
        raise ValueError("max_combinations must be positive")

    keys = param_grid.keys()
    values = param_grid.values()
    all_combinations = [dict(zip(keys, combo)) for combo in product(*values)]
    logger.info(f"Total parameter combinations: {len(all_combinations)}")

    if len(all_combinations) > max_combinations:
        param_combinations = random.sample(all_combinations, max_combinations)
    else:
        param_combinations = all_combinations

    best_params = None
    best_score = float('inf')
    all_results = []

    for i, params in enumerate(param_combinations, 1):
        try:
            model_params = {
                'growth': 'linear',
                'yearly_seasonality': False,
                'mcmc_samples': 0,
                'interval_width': 0.95,
                'seasonality_mode': params.get('seasonality_mode', 'multiplicative'),
                'daily_seasonality': params.get('daily_seasonality', True),
                'weekly_seasonality': params.get('weekly_seasonality', True),
                'changepoint_prior_scale': params.get('changepoint_prior_scale', 0.05),
                'seasonality_prior_scale': params.get('seasonality_prior_scale', 10.0),
                'changepoint_range': params.get('changepoint_range', 0.8),
            }

            model = Prophet(**model_params)

            # Добавляем только те условные сезонности, для которых есть столбцы
            added_seasonalities = []
            for col, spec in CONDITIONAL_SEASONALITIES.items():
                if col in df.columns:
                    model.add_seasonality(
                        name=col,
                        period=spec['period'],
                        fourier_order=spec['fourier_order'],
                        condition_name=col
                    )
                    added_seasonalities.append(col)

            model.fit(df)

            # Оценка
            if len(df) < 100:
                metrics = calculate_simple_metrics(model, df)
                mape, rmse, coverage = metrics['mape'], metrics['rmse'], metrics['coverage']
                score = mape
            else:
                try:
                    df_cv = cross_validation(
                        model, initial='3 days', period='1 day', horizon='1 day',
                        parallel="processes", disable_tqdm=True
                    )
                    if len(df_cv) == 0:
                        continue
                    df_p = performance_metrics(df_cv)
                    mape = float(df_p['mape'].mean())
                    rmse = float(df_p['rmse'].mean())
                    coverage = float(df_p['coverage'].mean())
                    score = mape * 0.5 + (rmse / (df['y'].std() + 1e-8)) * 0.3 + (1 - coverage / 100) * 0.2
                except Exception as e:
                    logger.debug(f"CV failed: {e}")
                    continue

            result = {
                'params': params,
                'mape': mape,
                'rmse': rmse,
                'coverage': coverage,
                'score': score,
                'added_seasonalities': added_seasonalities
            }
            all_results.append(result)

            if score < best_score:
                best_score = score
                best_params = result

            if i % 10 == 0:
                logger.info(f"Tested {i}/{len(param_combinations)}. Best MAPE: {best_params['mape']:.2f}%")

        except Exception as e:
            logger.debug(f"Failed with params {params}: {e}")
            continue

    return best_params
