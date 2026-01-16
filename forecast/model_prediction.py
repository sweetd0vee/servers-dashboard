import pandas as pd
import numpy as np
from prophet import Prophet
from .config import CONDITIONAL_SEASONALITIES
from .utils import add_time_features


def predict(model: Prophet, model_metadata: dict, periods: int = 48, freq: str = '30min') -> pd.DataFrame:
    future = model.make_future_dataframe(periods=periods, freq=freq, include_history=False)

    added_seasonalities = model_metadata.get('added_seasonalities', [])

    if added_seasonalities:
        future = add_time_features(future)
        # Удаляем ненужные столбцы
        for col in ['hour', 'day_of_week']:
            if col not in added_seasonalities and col in future.columns:
                del future[col]

    forecast = model.predict(future)

    # Округление и clipping
    numeric_cols = forecast.select_dtypes(include=[np.number]).columns
    forecast[numeric_cols] = forecast[numeric_cols].round(2)
    for col in ['yhat', 'yhat_lower', 'yhat_upper']:
        if col in forecast.columns:
            forecast[col] = forecast[col].clip(lower=0)

    return forecast
