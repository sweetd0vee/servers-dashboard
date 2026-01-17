import logging
import os
from datetime import timedelta
from typing import Any, Dict, List, Optional, Tuple

from prophet import Prophet
from sqlalchemy.orm import Session

from .config import DEFAULT_PARAM_GRID, MODEL_STORAGE_PATH
from .model_prediction import predict
from .model_training import train_model
from .model_tuning import tune_hyperparameters
from .storage import (cleanup_old_models, find_latest_model,
                      load_model_with_metadata)
from .utils import now_utc, prepare_data

logger = logging.getLogger(__name__)


class ProphetForecaster:
    def __init__(self, model_storage_path: str = MODEL_STORAGE_PATH, enable_optimization: bool = True):
        self.model_storage_path = model_storage_path
        self.enable_optimization = enable_optimization
        os.makedirs(model_storage_path, exist_ok=True)

    def train_or_load_model(
        self, db: Session, crud, vm: str, metric: str,
        retrain: bool = False, optimize: Optional[bool] = None
    ) -> Tuple[Optional[Prophet], Optional[Dict]]:
        if optimize is None:
            optimize = self.enable_optimization

        if not retrain:
            model_path = find_latest_model(self.model_storage_path, vm, metric)
            if model_path:
                model, meta = load_model_with_metadata(model_path)
                if model:
                    logger.info(f"Loaded model for {vm} - {metric}")
                    return model, meta

        # Обучение
        end_date = now_utc()
        start_date = end_date - timedelta(days=30)
        data_records = crud.get_historical_metrics(vm, metric, start_date, end_date, limit=5000)

        if not data_records or len(data_records) < 48:
            logger.error(f"Insufficient data for {vm} - {metric}")
            return None, None

        data_dicts = [{'timestamp': r.timestamp, 'value': float(r.value)} for r in data_records]
        df = prepare_data(data_dicts)

        best_params = None
        if optimize and len(df) >= 100:
            best_params = tune_hyperparameters(df)

        model, metrics, model_path, model_meta = train_model(
            df, vm, metric, self.model_storage_path, best_params
        )
        logger.info(f"Trained model: MAPE={metrics.get('mape', 0):.2f}%")
        return model, model_meta

    def generate_forecast(
        self, db: Session, crud, vm: str, metric: str,
        periods: int = 48, freq: str = '30min',
        save_to_db: bool = True, optimize: Optional[bool] = True
    ) -> Dict[str, Any]:
        try:
            model, meta = self.train_or_load_model(db, crud, vm, metric, optimize=optimize)
            if not model:
                return {'success': False, 'error': 'Model not available'}

            forecast_df = predict(model, meta, periods, freq)

            predictions = []
            for _, row in forecast_df.iterrows():
                pred = {
                    'timestamp': row['ds'],
                    'prediction': float(row['yhat']),
                    'confidence_lower': float(row.get('yhat_lower', 0)),
                    'confidence_upper': float(row.get('yhat_upper', 0))
                }
                if save_to_db:
                    crud.save_prediction(vm, metric, row['ds'], pred['prediction'], pred['confidence_lower'], pred['confidence_upper'])
                predictions.append(pred)

            return {
                'success': True,
                'vm': vm,
                'metric': metric,
                'predictions': predictions,
                'generated_at': now_utc(),
                'total_predictions': len(predictions)
            }
        except Exception as e:
            logger.error(f"Forecast failed: {e}")
            return {'success': False, 'error': str(e)}

    def cleanup_old_models(self, days_to_keep: int = 30) -> Dict[str, Any]:
        try:
            deleted = cleanup_old_models(self.model_storage_path, days_to_keep)
            return {'success': True, 'deleted_models': deleted}
        except Exception as e:
            return {'success': False, 'error': str(e)}
