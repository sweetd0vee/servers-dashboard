import pickle
import pandas as pd
import numpy as np
from prophet import Prophet
from prophet.diagnostics import cross_validation, performance_metrics
from datetime import datetime, timedelta
import os
import json
from typing import Dict, List, Optional, Tuple, Any
import logging
from itertools import product
import random
from sqlalchemy.orm import Session
from facts_crud import DBCRUD

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ProphetForecaster:
    def __init__(self, model_storage_path: str = "./models_storage",
                 enable_optimization: bool = True):
        self.model_storage_path = model_storage_path
        self.enable_optimization = enable_optimization
        os.makedirs(model_storage_path, exist_ok=True)
        self.loaded_models = {}

        # Параметры для grid search
        self.default_param_grid = {
            'changepoint_prior_scale': [0.001, 0.01, 0.05, 0.1, 0.5],
            'seasonality_prior_scale': [2.0, 12.0, 24.0, 48.0],
            'seasonality_mode': ['additive', 'multiplicative'],
            'changepoint_range': [0.8, 0.9, 0.95],
            'weekly_seasonality': [True, False],
            'daily_seasonality': [True, False]
        }

    def prepare_data(self, data: List[Dict]) -> pd.DataFrame:
        """Подготовка данных для Prophet"""
        if not data:
            raise ValueError("No data provided for preparation")

        df = pd.DataFrame(data)
        df = df.rename(columns={'timestamp': 'ds', 'value': 'y'})
        df['ds'] = pd.to_datetime(df['ds'])

        df['ds'] = df['ds'].dt.tz_localize(None)

        df = df.sort_values('ds')

        # Проверка на пропуски
        if df['y'].isnull().any():
            logger.warning(f"Found {df['y'].isnull().sum()} missing values, filling with interpolation")
            df['y'] = df['y'].interpolate(method='linear').bfill().ffill()

        # Добавление признаков
        df['hour'] = df['ds'].dt.hour
        df['is_work_hours'] = df['hour'].between(9, 18).astype(float)
        df['is_night'] = df['hour'].between(0, 6).astype(float)
        df['day_of_week'] = df['ds'].dt.dayofweek
        df['is_weekend'] = (df['day_of_week'] >= 5).astype(float)

        # Проверка временных интервалов
        time_diff = df['ds'].diff().mode()[0] if len(df) > 1 else None
        if time_diff:
            logger.info(f"Main time interval: {time_diff}")

        return df

    def tune_hyperparameters(self, df: pd.DataFrame,
                             param_grid: Dict[str, list] = None,
                             max_combinations: int = 50) -> Dict[str, Any]:
        """Оптимизация гиперпараметров Prophet с помощью grid search"""

        if not self.enable_optimization:
            logger.info("Hyperparameter optimization is disabled")
            return None

        if param_grid is None:
            param_grid = self.default_param_grid

        logger.info("Starting hyperparameter tuning...")

        # Генерируем все комбинации параметров
        keys = param_grid.keys()
        values = param_grid.values()
        all_param_combinations = [dict(zip(keys, combo)) for combo in product(*values)]

        logger.info(f"Total parameter combinations: {len(all_param_combinations)}")

        # Ограничиваем количество тестируемых комбинаций
        if len(all_param_combinations) > max_combinations:
            logger.info(f"Using random search with {max_combinations} combinations")
            param_combinations = random.sample(all_param_combinations, max_combinations)
        else:
            param_combinations = all_param_combinations

        best_params = None
        best_score = float('inf')
        all_results = []

        for i, params in enumerate(param_combinations, 1):
            try:
                # Создаем модель с текущими параметрами
                model_params = {
                    'growth': 'linear',
                    'yearly_seasonality': False,
                    'mcmc_samples': 0,
                    'interval_width': 0.95
                }

                # Копируем только валидные параметры для Prophet
                valid_params = {}
                for key, value in params.items():
                    if key in ['changepoint_prior_scale', 'seasonality_prior_scale',
                               'seasonality_mode', 'weekly_seasonality', 'daily_seasonality']:
                        valid_params[key] = value

                model_params.update(valid_params)
                model = Prophet(**model_params)

                # Добавляем кастомные сезонности
                if 'is_work_hours' in df.columns:
                    model.add_seasonality(
                        name='work_hours',
                        period=1,
                        fourier_order=5,
                        condition_name='is_work_hours'
                    )

                if 'is_night' in df.columns:
                    model.add_seasonality(
                        name='night_hours',
                        period=1,
                        fourier_order=3,
                        condition_name='is_night'
                    )

                if 'is_weekend' in df.columns:
                    model.add_seasonality(
                        name='weekend_effect',
                        period=1,
                        fourier_order=3,
                        condition_name='is_weekend'
                    )

                # Обучение модели
                model.fit(df)

                # Быстрая кросс-валидация
                try:
                    if len(df) < 100:
                        # Для маленьких датасетов используем простую оценку
                        forecast = model.predict(df[['ds']])
                        y_true = df['y'].values
                        y_pred = forecast['yhat'].values

                        epsilon = 1e-10
                        safe_y_true = np.where(y_true == 0, epsilon, y_true)
                        mape = np.mean(np.abs((y_true - y_pred) / safe_y_true)) * 100
                        rmse = np.sqrt(np.mean((y_true - y_pred) ** 2))

                        if 'yhat_lower' in forecast.columns and 'yhat_upper' in forecast.columns:
                            in_interval = ((y_true >= forecast['yhat_lower'].values) &
                                           (y_true <= forecast['yhat_upper'].values))
                            coverage = np.mean(in_interval) * 100
                        else:
                            coverage = 0.0

                        score = mape  # Используем MAPE как основной критерий

                    else:
                        # Полная кросс-валидация
                        df_cv = cross_validation(
                            model,
                            initial='3 days',
                            period='1 day',
                            horizon='1 day',
                            parallel="processes",
                            disable_tqdm=True
                        )

                        if len(df_cv) > 0:
                            df_p = performance_metrics(df_cv)
                            mape = df_p['mape'].mean()
                            rmse = df_p['rmse'].mean()
                            coverage = df_p['coverage'].mean()

                            # Комбинированный score (можно настроить веса)
                            score = mape * 0.5 + (rmse / df['y'].std()) * 0.3 + (1 - coverage / 100) * 0.2
                        else:
                            continue

                    result = {
                        'params': params,
                        'mape': float(mape),
                        'rmse': float(rmse),
                        'coverage': float(coverage),
                        'score': float(score)
                    }

                    all_results.append(result)

                    if score < best_score:
                        best_score = score
                        best_params = params.copy()
                        best_params.update({
                            'mape': float(mape),
                            'rmse': float(rmse),
                            'coverage': float(coverage),
                            'score': float(score)
                        })

                    if i % 10 == 0:
                        logger.info(
                            f"Tested {i}/{len(param_combinations)} combinations. Best MAPE: {best_params.get('mape', 'N/A'):.2f}%")

                except Exception as cv_error:
                    logger.debug(f"CV failed for params {params}: {cv_error}")
                    continue

            except Exception as e:
                logger.debug(f"Failed with params {params}: {e}")
                continue

        if best_params:
            logger.info(f"Best parameters found: MAPE={best_params.get('mape', 0):.2f}%, "
                        f"RMSE={best_params.get('rmse', 0):.2f}, "
                        f"Coverage={best_params.get('coverage', 0):.1f}%")
            return best_params
        else:
            logger.warning("No valid parameters found during tuning, using defaults")
            return None

    def train_model(self, df: pd.DataFrame, vm: str, metric: str,
                    optimize_hyperparams: bool = None) -> Tuple[Prophet, Dict, str]:
        """Обучение модели Prophet с возможностью оптимизации гиперпараметров"""
        logger.info(f"Training Prophet model for {vm} - {metric}")

        # Определяем использовать ли оптимизацию
        if optimize_hyperparams is None:
            optimize_hyperparams = self.enable_optimization

        # Проверка достаточности данных
        if len(df) < 48:
            raise ValueError(f"Insufficient data: {len(df)} records. Minimum 48 required.")

        # Оптимизация гиперпараметров если включена
        best_params = None
        if optimize_hyperparams and len(df) >= 100:
            logger.info("Optimizing hyperparameters...")
            best_params = self.tune_hyperparameters(df)

        # Настройки модели
        if best_params:
            logger.info(f"Using optimized parameters: {best_params}")
            model_params = {
                'growth': 'linear',
                'seasonality_mode': best_params.get('seasonality_mode', 'multiplicative'),
                'daily_seasonality': best_params.get('daily_seasonality', True),
                'weekly_seasonality': best_params.get('weekly_seasonality', True),
                'yearly_seasonality': False,
                'changepoint_prior_scale': best_params.get('changepoint_prior_scale', 0.05),
                'seasonality_prior_scale': best_params.get('seasonality_prior_scale', 10.0),
                'changepoint_range': best_params.get('changepoint_range', 0.8),
                'interval_width': 0.95
            }
        else:
            logger.info("Using default parameters")
            model_params = {
                'growth': 'linear',
                'seasonality_mode': 'multiplicative',
                'daily_seasonality': True,
                'weekly_seasonality': True,
                'yearly_seasonality': False,
                'changepoint_prior_scale': 0.05,
                'seasonality_prior_scale': 10.0,
                'changepoint_range': 0.8,
                'interval_width': 0.95
            }

        model = Prophet(**model_params)

        # Добавление кастомных сезонностей
        if 'is_work_hours' in df.columns:
            model.add_seasonality(
                name='work_hours',
                period=1,
                fourier_order=5,
                condition_name='is_work_hours'
            )

        if 'is_night' in df.columns:
            model.add_seasonality(
                name='night_hours',
                period=1,
                fourier_order=3,
                condition_name='is_night'
            )

        if 'is_weekend' in df.columns:
            model.add_seasonality(
                name='weekend_effect',
                period=1,
                fourier_order=3,
                condition_name='is_weekend'
            )

        # Обучение
        model.fit(df)

        # Оценка модели
        metrics = self.evaluate_model(model, df)

        # Добавляем информацию о гиперпараметрах в метрики
        if best_params:
            metrics['optimized_params'] = best_params
            metrics['was_optimized'] = True
        else:
            metrics['was_optimized'] = False

        # Сохранение модели
        model_filename = f"{vm}_{metric}_prophet_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pkl"
        model_path = os.path.join(self.model_storage_path, model_filename)

        model_data = {
            'model': model,
            'trained_at': datetime.now(),
            'metrics': metrics,
            'data_points': len(df),
            'vm': vm,
            'metric': metric,
            'config': model_params,
            'optimized': best_params is not None,
            'optimized_params': best_params
        }

        with open(model_path, 'wb') as f:
            pickle.dump(model_data, f)

        # Сохранение метрик в JSON
        metrics_path = model_path.replace('.pkl', '_metrics.json')
        with open(metrics_path, 'w') as f:
            json.dump(metrics, f, indent=2, default=str)

        logger.info(f"Model saved to {model_path}")
        logger.info(f"Model metrics: MAPE={metrics.get('mape', 0):.2f}%, Coverage={metrics.get('coverage', 0):.1f}%")

        return model, metrics, model_path

    def evaluate_model(self, model: Prophet, df: pd.DataFrame) -> Dict:
        """Оценка качества модели"""
        try:
            if len(df) < 100:
                logger.warning("Not enough data for proper cross-validation")
                return self._calculate_simple_metrics(model, df)

            # Кросс-валидация
            df_cv = cross_validation(
                model,
                initial='3 days',
                period='1 day',
                horizon='1 day',
                parallel="processes",
                disable_tqdm=True
            )

            if len(df_cv) == 0:
                return self._calculate_simple_metrics(model, df)

            df_p = performance_metrics(df_cv)

            metrics = {
                'mape': float(df_p['mape'].mean()) if 'mape' in df_p.columns else 0.0,
                'rmse': float(df_p['rmse'].mean()) if 'rmse' in df_p.columns else 0.0,
                'mae': float(df_p['mae'].mean()) if 'mae' in df_p.columns else 0.0,
                'coverage': float(df_p['coverage'].mean()) if 'coverage' in df_p.columns else 0.0,
                'mdape': float(df_p['mdape'].mean()) if 'mdape' in df_p.columns else 0.0,
                'smape': float(df_p['smape'].mean()) if 'smape' in df_p.columns else 0.0,
                'evaluation_type': 'cross_validation'
            }

            return metrics

        except Exception as e:
            logger.warning(f"Cross-validation failed: {e}, using simple evaluation")
            return self._calculate_simple_metrics(model, df)

    def _calculate_simple_metrics(self, model: Prophet, df: pd.DataFrame) -> Dict:
        """Простая оценка модели без кросс-валидации"""
        try:
            # Прогноз на исторических данных
            forecast = model.predict(df[['ds']])

            # Расчет метрик
            y_true = df['y'].values
            y_pred = forecast['yhat'].values

            # Базовые метрики
            mae = np.mean(np.abs(y_true - y_pred))
            mse = np.mean((y_true - y_pred) ** 2)
            rmse = np.sqrt(mse)

            # MAPE с защитой от деления на ноль
            epsilon = 1e-10
            safe_y_true = np.where(y_true == 0, epsilon, y_true)
            mape = np.mean(np.abs((y_true - y_pred) / safe_y_true)) * 100

            # SMAPE
            smape = 200 * np.mean(np.abs(y_pred - y_true) / (np.abs(y_pred) + np.abs(y_true) + epsilon))

            # Coverage
            if 'yhat_lower' in forecast.columns and 'yhat_upper' in forecast.columns:
                in_interval = ((y_true >= forecast['yhat_lower'].values) &
                               (y_true <= forecast['yhat_upper'].values))
                coverage = np.mean(in_interval) * 100
            else:
                coverage = 0.0

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
            return {
                'mape': 0.0,
                'rmse': 0.0,
                'mae': 0.0,
                'coverage': 0.0,
                'smape': 0.0,
                'evaluation_type': 'failed'
            }

    def load_model(self, model_path: str) -> Optional[Prophet]:
        """Загрузка модели из файла"""
        try:
            with open(model_path, 'rb') as f:
                data = pickle.load(f)

            if 'model' in data:
                logger.info(f"Model loaded from {model_path}")
                return data['model']
            else:
                logger.error(f"No model found in {model_path}")
                return None

        except FileNotFoundError:
            logger.error(f"Model file not found: {model_path}")
            return None
        except Exception as e:
            logger.error(f"Failed to load model from {model_path}: {e}")
            return None

    def predict(self, model: Prophet, periods: int = 48,
                freq: str = '30min') -> pd.DataFrame:
        """Прогнозирование"""
        if model is None:
            raise ValueError("Model is None, cannot predict")

        future = model.make_future_dataframe(periods=periods, freq=freq, include_history=False)

        # Добавление условий для кастомных сезонностей
        if hasattr(model, 'seasonalities'):
            future['hour'] = future['ds'].dt.hour
            future['is_work_hours'] = future['hour'].between(9, 18).astype(float)
            future['is_night'] = future['hour'].between(0, 6).astype(float)
            future['day_of_week'] = future['ds'].dt.dayofweek
            future['is_weekend'] = (future['day_of_week'] >= 5).astype(float)

        forecast = model.predict(future)

        # Пост-обработка
        numeric_cols = forecast.select_dtypes(include=[np.number]).columns
        forecast[numeric_cols] = forecast[numeric_cols].round(2)

        # Ограничение отрицательных значений
        if 'yhat' in forecast.columns:
            forecast['yhat'] = forecast['yhat'].clip(lower=0)
        if 'yhat_lower' in forecast.columns:
            forecast['yhat_lower'] = forecast['yhat_lower'].clip(lower=0)
        if 'yhat_upper' in forecast.columns:
            forecast['yhat_upper'] = forecast['yhat_upper'].clip(lower=0)

        return forecast

    def train_or_load_model(self, db: Session, crud: DBCRUD,
                            vm: str, metric: str, retrain: bool = False,
                            optimize: bool = None) -> Optional[Prophet]:
        """Обучение или загрузка модели с возможностью оптимизации"""

        # Определяем использовать ли оптимизацию
        if optimize is None:
            optimize = self.enable_optimization

        # Проверка существующей модели
        if not retrain:
            try:
                model_files = [f for f in os.listdir(self.model_storage_path)
                               if f.startswith(f"{vm}_{metric}_prophet")]

                if model_files:
                    # Берем самую новую модель
                    model_files.sort(reverse=True)
                    latest_model = model_files[0]
                    model_path = os.path.join(self.model_storage_path, latest_model)

                    model = self.load_model(model_path)
                    if model:
                        logger.info(f"Loaded existing model for {vm} - {metric}")
                        return model

            except Exception as e:
                logger.warning(f"Failed to load existing model: {e}")

        # Обучение новой модели
        logger.info(f"Training new model for {vm} - {metric}")

        # Получаем данные из БД
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=30)

            data_records = crud.get_historical_metrics(
                vm=vm,
                metric=metric,
                start_date=start_date,
                end_date=end_date,
                limit=5000
            )

            if not data_records or len(data_records) < 48:
                logger.error(
                    f"Insufficient data for {vm} - {metric}: {len(data_records) if data_records else 0} records")
                return None

            # Преобразуем в список словарей
            data_dicts = []
            for record in data_records:
                data_dicts.append({
                    'timestamp': record.timestamp,
                    'value': float(record.value) if hasattr(record, 'value') else 0.0
                })

            # Подготовка данных
            df = self.prepare_data(data_dicts)

            # Обучение с оптимизацией
            model, metrics, model_path = self.train_model(df, vm, metric, optimize_hyperparams=optimize)

            logger.info(f"Model trained successfully: MAPE={metrics.get('mape', 0):.2f}%")

            return model

        except Exception as e:
            logger.error(f"Failed to train model for {vm} - {metric}: {e}")
            return None

    def generate_forecast(self, db: Session, crud: DBCRUD,
                          vm: str, metric: str,
                          periods: int = 48, freq: str = '30min',
                          save_to_db: bool = True,
                          optimize: bool = None) -> Dict[str, Any]:
        """
        Генерация прогноза с сохранением в БД

        Args:
            optimize: Переопределить глобальную настройку оптимизации
        """
        try:
            # Получение или обучение модели
            model = self.train_or_load_model(db, crud, vm, metric, optimize=optimize)

            if not model:
                return {
                    'success': False,
                    'error': 'Failed to get or train model',
                    'predictions': []
                }

            # Генерация прогноза
            forecast_df = self.predict(model, periods, freq)

            # Преобразование в список для ответа
            predictions = []
            for _, row in forecast_df.iterrows():
                prediction_data = {
                    'timestamp': row['ds'],
                    'prediction': float(row['yhat']),
                    'confidence_lower': float(row.get('yhat_lower', 0)),
                    'confidence_upper': float(row.get('yhat_upper', 0))
                }

                # Сохранение в БД
                if save_to_db:
                    try:
                        crud.save_prediction(
                            vm=vm,
                            metric=metric,
                            timestamp=row['ds'],
                            value=float(row['yhat']),
                            lower=float(row.get('yhat_lower', 0)),
                            upper=float(row.get('yhat_upper', 0))
                        )
                    except Exception as db_error:
                        logger.warning(f"Failed to save prediction to DB: {db_error}")

                predictions.append(prediction_data)

            # Получение статистики модели
            model_stats = self.get_model_stats(model)

            return {
                'success': True,
                'vm': vm,
                'metric': metric,
                'periods': periods,
                'freq': freq,
                'generated_at': datetime.now(),
                'predictions': predictions,
                'model_stats': model_stats,
                'total_predictions': len(predictions)
            }

        except Exception as e:
            logger.error(f"Failed to generate forecast: {e}")
            return {
                'success': False,
                'error': str(e),
                'predictions': []
            }

    def get_model_stats(self, model: Prophet) -> Dict:
        """Получение статистики модели"""
        if model is None:
            return {}

        stats = {
            'changepoints_count': len(model.changepoints) if hasattr(model, 'changepoints') else 0,
            'seasonalities': list(model.seasonalities.keys()) if hasattr(model, 'seasonalities') else [],
            'seasonality_mode': model.seasonality_mode if hasattr(model, 'seasonality_mode') else 'unknown',
            'interval_width': model.interval_width if hasattr(model, 'interval_width') else 0.95,
            'hyperparams': {
                'changepoint_prior_scale': getattr(model, 'changepoint_prior_scale', None),
                'seasonality_prior_scale': getattr(model, 'seasonality_prior_scale', None),
                'changepoint_range': getattr(model, 'changepoint_range', None)
            }
        }

        return stats

    def batch_train_models(self, db: Session, crud: DBCRUD,
                           vm_metric_pairs: List[Tuple[str, str]],
                           optimize: bool = None) -> Dict[str, Any]:
        """
        Пакетное обучение моделей для нескольких VM и метрик
        """
        results = {
            'total': len(vm_metric_pairs),
            'successful': 0,
            'failed': 0,
            'details': []
        }

        for vm, metric in vm_metric_pairs:
            try:
                logger.info(f"Training model for {vm} - {metric}")

                model = self.train_or_load_model(db, crud, vm, metric, retrain=True, optimize=optimize)

                if model:
                    results['successful'] += 1
                    results['details'].append({
                        'vm': vm,
                        'metric': metric,
                        'status': 'success',
                        'message': 'Model trained successfully'
                    })
                else:
                    results['failed'] += 1
                    results['details'].append({
                        'vm': vm,
                        'metric': metric,
                        'status': 'failed',
                        'message': 'Failed to train model'
                    })

            except Exception as e:
                results['failed'] += 1
                results['details'].append({
                    'vm': vm,
                    'metric': metric,
                    'status': 'error',
                    'message': str(e)
                })
                logger.error(f"Error training model for {vm} - {metric}: {e}")

        logger.info(f"Batch training completed: {results['successful']} successful, {results['failed']} failed")
        return results

    def cleanup_old_models(self, days_to_keep: int = 30) -> Dict:
        """
        Очистка старых моделей
        """
        try:
            cutoff_date = datetime.now() - timedelta(days=days_to_keep)
            deleted_count = 0
            kept_count = 0

            for filename in os.listdir(self.model_storage_path):
                if filename.endswith('.pkl'):
                    filepath = os.path.join(self.model_storage_path, filename)
                    file_time = datetime.fromtimestamp(os.path.getmtime(filepath))

                    if file_time < cutoff_date:
                        os.remove(filepath)

                        # Также удаляем соответствующий JSON файл с метриками
                        metrics_file = filepath.replace('.pkl', '_metrics.json')
                        if os.path.exists(metrics_file):
                            os.remove(metrics_file)

                        deleted_count += 1
                    else:
                        kept_count += 1

            return {
                'success': True,
                'deleted_models': deleted_count,
                'kept_models': kept_count,
                'cutoff_date': cutoff_date
            }

        except Exception as e:
            logger.error(f"Failed to cleanup old models: {e}")
            return {
                'success': False,
                'error': str(e),
                'deleted_models': 0,
                'kept_models': 0
            }