"""
Production-ready time series forecasting module for server metrics
"""

import pandas as pd
import numpy as np
from prophet import Prophet
from prophet.diagnostics import cross_validation, performance_metrics
import matplotlib.pyplot as plt
import logging
from typing import Tuple, Optional, Dict, Any, List
import pickle
import json
from datetime import datetime, timedelta
import warnings
from pathlib import Path
import sys
import os

# Создание необходимых директорий перед настройкой
BASE_DIR = Path(__file__).parent.absolute()
LOG_DIR = BASE_DIR / "logs"
MODEL_DIR = BASE_DIR / "models"
FORECAST_DIR = BASE_DIR / "forecasts"

# Создание всех необходимых директорий
for directory in [LOG_DIR, MODEL_DIR, FORECAST_DIR]:
    directory.mkdir(exist_ok=True, parents=True)

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/prophet_forecast.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Игнорировать warnings
warnings.filterwarnings('ignore')


class Config:
    """Конфигурация модели"""
    # Параметры модели
    DEFAULT_HYPERPARAMS = {
        'changepoint_prior_scale': 0.05,
        'seasonality_prior_scale': 10.0,
        'holidays_prior_scale': 10.0,
        'seasonality_mode': 'multiplicative',
        'daily_seasonality': True,
        'weekly_seasonality': True,
        'yearly_seasonality': False,
        'mcmc_samples': 300
    }

    # Параметры прогнозирования
    FORECAST_PERIODS = 48  # 24 часа при 30-минутном интервале
    FORECAST_FREQ = '30min'

    # Пороги для аномалий
    ANOMALY_THRESHOLD = 3.0  # В сигмах
    CONFIDENCE_LEVEL = 0.95  # Уровень доверия


class DataPreprocessor:
    """Предобработка временных рядов"""

    @staticmethod
    def prepare_data(df: pd.DataFrame, server: str, metric: str) -> pd.DataFrame:
        """Подготовка данных для конкретного сервера и метрики"""
        logger.info(f"Preparing data for server={server}, metric={metric}")

        # Фильтрация и сортировка
        df_filtered = df.copy()
        df_filtered = df_filtered.sort_values('timestamp')

        # Создание структуры для Prophet
        prophet_df = pd.DataFrame({
            'ds': pd.to_datetime(df_filtered['timestamp']),
            'y': df_filtered['value'].astype(float)
        })

        # Удаление дубликатов
        prophet_df = prophet_df.drop_duplicates(subset=['ds']).sort_values('ds')

        # Проверка качества данных
        DataPreprocessor._validate_data(prophet_df)

        # Обработка пропусков
        prophet_df = DataPreprocessor._handle_missing_values(prophet_df)

        # Обработка выбросов
        prophet_df = DataPreprocessor._handle_outliers(prophet_df)

        logger.info(f"Prepared {len(prophet_df)} records, "
                    f"span: {prophet_df['ds'].min()} to {prophet_df['ds'].max()}")

        return prophet_df

    @staticmethod
    def _validate_data(df: pd.DataFrame):
        """Валидация входных данных"""
        if len(df) < 48:
            raise ValueError(f"Insufficient data: only {len(df)} records. Minimum 48 required.")

        if df['y'].isnull().all():
            raise ValueError("All metric values are null")

        # Проверка временного интервала
        time_diff = df['ds'].diff().mode()[0]
        logger.info(f"Main time interval: {time_diff}")

    @staticmethod
    def _handle_missing_values(df: pd.DataFrame, method: str = 'linear') -> pd.DataFrame:
        """Обработка пропущенных значений"""
        if df['y'].isnull().sum() > 0:
            logger.warning(f"Found {df['y'].isnull().sum()} missing values, filling with {method}")

            if method == 'ffill':
                df['y'] = df['y'].ffill().bfill()
            elif method == 'linear':
                df['y'] = df['y'].interpolate(method='linear').bfill().ffill()
            elif method == 'spline':
                df['y'] = df['y'].interpolate(method='spline', order=3).bfill().ffill()

        return df

    @staticmethod
    def _handle_outliers(df: pd.DataFrame, n_sigma: float = 3.0) -> pd.DataFrame:
        """Обработка выбросов методом сигм"""
        mean = df['y'].mean()
        std = df['y'].std()

        lower_bound = mean - n_sigma * std
        upper_bound = mean + n_sigma * std

        outliers_mask = (df['y'] < lower_bound) | (df['y'] > upper_bound)

        if outliers_mask.any():
            logger.warning(f"Found {outliers_mask.sum()} outliers, clipping to bounds")
            df.loc[outliers_mask, 'y'] = np.clip(
                df.loc[outliers_mask, 'y'],
                lower_bound,
                upper_bound
            )

        return df


class ProphetOptimizer:
    """Оптимизация гиперпараметров Prophet"""

    @staticmethod
    def tune_hyperparameters(df: pd.DataFrame,
                             param_grid: Dict[str, list] = None) -> Dict[str, Any]:
        """Подбор оптимальных гиперпараметров с помощью кросс-валидации"""

        if param_grid is None:
            param_grid = {
                'changepoint_prior_scale': [0.001, 0.01, 0.05, 0.1, 0.5],
                'changepoint_range': [0.8],
                'seasonality_prior_scale': [2.0, 12.0, 24.0, 48.0],
                'seasonality_mode': ['multiplicative']
            }

        logger.info("Starting hyperparameter tuning...")

        best_params = None
        best_mape = float('inf')

        # Простой grid search (для продакшена лучше использовать Bayesian Optimization)
        for changepoint in param_grid['changepoint_prior_scale']:
            for seasonality in param_grid['seasonality_prior_scale']:
                for mode in param_grid['seasonality_mode']:
                    try:
                        model = Prophet(
                            daily_seasonality=True,
                            weekly_seasonality=True,
                            yearly_seasonality=False,
                            seasonality_mode=mode,
                            changepoint_prior_scale=changepoint,
                            seasonality_prior_scale=seasonality,
                            mcmc_samples=0
                        )

                        model.fit(df)

                        # Кросс-валидация
                        df_cv = cross_validation(
                            model,
                            initial='3 days',
                            period='1 day',
                            horizon='1 day',
                            parallel="processes"
                        )

                        df_p = performance_metrics(df_cv)
                        current_mape = df_p['mape'].mean()

                        if current_mape < best_mape:
                            best_mape = current_mape
                            best_params = {
                                'changepoint_prior_scale': changepoint,
                                'seasonality_prior_scale': seasonality,
                                'seasonality_mode': mode,
                                'mape': current_mape
                            }

                    except Exception as e:
                        logger.warning(f"Failed with params {changepoint}, {seasonality}, {mode}: {e}")

        logger.info(f"Best parameters: {best_params}")
        return best_params

    @staticmethod
    def add_custom_seasonalities(model: Prophet, df: pd.DataFrame) -> Tuple[Prophet, pd.DataFrame]:
        """Добавление кастомных сезонностей"""

        # Рабочие часы
        df['is_work_hours'] = df['ds'].dt.hour.between(9, 18).astype(float)
        df['is_night_hours'] = df['ds'].dt.hour.between(0, 6).astype(float)
        df['is_work_day'] = df['ds'].dt.weekday.between(0, 4).astype(float)

        model.add_seasonality(
            name='work_hours',
            period=1,
            fourier_order=5,
            condition_name='is_work_hours'
        )

        model.add_seasonality(
            name='night_hours',
            period=1,
            fourier_order=3,
            condition_name='is_night_hours'
        )

        return model, df


class ProductionProphetForecaster:
    """Продакшен-версия прогнозировщика"""

    def __init__(self, config: Config = None):
        self.config = config or Config()
        self.model = None
        self.metrics_history = []
        logger.info("ProductionProphetForecaster initialized")

    def train(self, df: pd.DataFrame,
              optimize: bool = False,
              save_model: bool = True) -> 'ProductionProphetForecaster':
        """Обучение модели"""

        logger.info(f"Training model on {len(df)} records")

        # Оптимизация гиперпараметров (опционально)
        hyperparams = self.config.DEFAULT_HYPERPARAMS.copy()

        if optimize and len(df) > 7 * 48:  # Только если достаточно данных
            try:
                best_params = ProphetOptimizer.tune_hyperparameters(df)
                if best_params:
                    hyperparams.update({
                        k: v for k, v in best_params.items()
                        if k in hyperparams
                    })
            except Exception as e:
                logger.error(f"Hyperparameter optimization failed: {e}")

        # Создание модели
        self.model = Prophet(**hyperparams)

        # Добавление кастомных сезонностей
        self.model, df = ProphetOptimizer.add_custom_seasonalities(self.model, df)

        # Обучение
        self.model.fit(df)

        # Сохранение модели
        if save_model:
            self.save_model(f"prophet_model_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pkl")

        logger.info("Model training completed")
        return self

    def predict(self,
                future_periods: int = None,
                freq: str = None,
                include_history: bool = True) -> Dict[str, Any]:
        """Прогнозирование с обработкой ошибок"""

        if self.model is None:
            raise ValueError("Model not trained. Call train() first.")

        periods = future_periods or self.config.FORECAST_PERIODS
        freq = freq or self.config.FORECAST_FREQ

        try:
            # Создание фрейма для прогноза
            future = self.model.make_future_dataframe(
                periods=periods,
                freq=freq,
                include_history=include_history
            )

            # Добавление условий для кастомных сезонностей
            future['is_work_hours'] = future['ds'].dt.hour.between(9, 18).astype(float)
            future['is_night_hours'] = future['ds'].dt.hour.between(0, 6).astype(float)

            # Прогнозирование
            forecast = self.model.predict(future)

            # Пост-обработка прогноза
            forecast = self._postprocess_forecast(forecast)

            # Детекция аномалий
            anomalies = self._detect_anomalies(forecast)

            # Формирование результата
            result = {
                'forecast': forecast,
                'anomalies': anomalies,
                'timestamp': datetime.now().isoformat(),
                'periods': periods,
                'freq': freq
            }

            # Сохранение прогноза
            self._save_forecast(result)

            logger.info(f"Forecast generated for {periods} periods")
            return result

        except Exception as e:
            logger.error(f"Prediction failed: {e}")
            raise

    def _postprocess_forecast(self, forecast: pd.DataFrame) -> pd.DataFrame:
        """Пост-обработка прогноза"""

        # Ограничение отрицательных значений
        forecast['yhat'] = forecast['yhat'].clip(lower=0)
        forecast['yhat_lower'] = forecast['yhat_lower'].clip(lower=0)
        forecast['yhat_upper'] = forecast['yhat_upper'].clip(lower=0)

        # Округление
        numeric_cols = forecast.select_dtypes(include=[np.number]).columns
        forecast[numeric_cols] = forecast[numeric_cols].round(2)

        return forecast

    def _detect_anomalies(self, forecast: pd.DataFrame) -> pd.DataFrame:
        """Детекция аномальных значений в прогнозе"""

        # Используем последние исторические данные для определения baseline
        historical = forecast[forecast['ds'] < datetime.now()].tail(100)

        if len(historical) > 0:
            mean = historical['yhat'].mean()
            std = historical['yhat'].std()

            future = forecast[forecast['ds'] >= datetime.now()].copy()
            future['z_score'] = (future['yhat'] - mean) / std

            anomalies = future[
                abs(future['z_score']) > self.config.ANOMALY_THRESHOLD
                ].copy()

            if len(anomalies) > 0:
                logger.warning(f"Detected {len(anomalies)} potential anomalies in forecast")

            return anomalies

        return pd.DataFrame()

    def evaluate(self, df: pd.DataFrame) -> Dict[str, float]:
        """Оценка качества модели"""

        if len(df) < 48:
            logger.warning("Insufficient data for evaluation")
            return {}

        # Разделение на train/test.csv
        split_idx = int(len(df) * 0.8)
        train_df = df.iloc[:split_idx]
        test_df = df.iloc[split_idx:]

        # Обучение на train
        self.train(train_df, optimize=False, save_model=False)

        # Прогноз на test.csv
        forecast = self.predict(
            future_periods=len(test_df),
            freq=test_df['ds'].diff().mode()[0] or '30min',
            include_history=False
        )['forecast']

        # Сравнение с фактическими значениями
        merged = pd.merge(
            test_df,
            forecast[['ds', 'yhat', 'yhat_lower', 'yhat_upper']],
            on='ds',
            how='inner'
        )

        if len(merged) > 0:
            # Вычисление метрик
            metrics = {
                'mae': np.mean(np.abs(merged['yhat'] - merged['y'])),
                'mse': np.mean((merged['yhat'] - merged['y']) ** 2),
                'rmse': np.sqrt(np.mean((merged['yhat'] - merged['y']) ** 2)),
                'mape': np.mean(np.abs((merged['yhat'] - merged['y']) / merged['y'].clip(lower=0.1))) * 100,
                'smape': 2.0 * np.mean(np.abs(merged['yhat'] - merged['y']) /
                                       (np.abs(merged['yhat']) + np.abs(merged['y']))) * 100,
                'coverage': ((merged['y'] >= merged['yhat_lower']) &
                             (merged['y'] <= merged['yhat_upper'])).mean() * 100
            }

            # Сохранение метрик
            self.metrics_history.append({
                'timestamp': datetime.now().isoformat(),
                **metrics
            })

            logger.info(f"Model evaluation metrics: {metrics}")
            return metrics

        return {}

    def save_model(self, filename: str):
        """Сохранение модели"""

        if self.model is None:
            raise ValueError("No model to save")

        model_path = MODEL_DIR / filename

        with open(model_path, 'wb') as f:
            pickle.dump({
                'model': self.model,
                'config': self.config,
                'timestamp': datetime.now().isoformat()
            }, f)

        logger.info(f"Model saved to {model_path}")

    @classmethod
    def load_model(cls, filename: str) -> 'ProductionProphetForecaster':
        """Загрузка модели"""

        model_path = Path(filename)

        if not model_path.exists():
            raise FileNotFoundError(f"Model file not found: {filename}")

        with open(model_path, 'rb') as f:
            data = pickle.load(f)

        forecaster = cls(data['config'])
        forecaster.model = data['model']

        logger.info(f"Model loaded from {filename}")
        return forecaster

    def _save_forecast(self, result: Dict[str, Any]):
        """Сохранение прогноза в файл"""

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        # Сохранение в CSV
        csv_path = FORECAST_DIR / f"forecast_{timestamp}.csv"
        result['forecast'].to_csv(csv_path, index=False)

        # Сохранение метаданных в JSON
        metadata = {
            'timestamp': result['timestamp'],
            'periods': result['periods'],
            'freq': str(result['freq']) if hasattr(result['freq'], '__str__') else result['freq'],
            'anomalies_count': len(result['anomalies'])
        }

        json_path = FORECAST_DIR / f"forecast_metadata_{timestamp}.json"
        with open(json_path, 'w') as f:
            json.dump(metadata, f, indent=2)

        logger.info(f"Forecast saved to {csv_path}")


class MonitoringDashboard:
    """Дашборд для мониторинга прогнозов"""

    @staticmethod
    def create_dashboard(forecast_result: Dict[str, Any],
                         metrics: Optional[Dict[str, float]] = None):
        """Создание визуализаций"""

        fig, axes = plt.subplots(2, 2, figsize=(15, 10))
        fig.suptitle('Server Metrics Forecast Dashboard', fontsize=16)

        forecast = forecast_result['forecast']

        # 1. Основной график прогноза
        ax1 = axes[0, 0]
        ax1.plot(forecast['ds'], forecast['yhat'], 'b-', label='Forecast', linewidth=2)
        ax1.fill_between(forecast['ds'],
                         forecast['yhat_lower'],
                         forecast['yhat_upper'],
                         alpha=0.2, color='blue', label='Confidence Interval')

        if 'anomalies' in forecast_result and len(forecast_result['anomalies']) > 0:
            ax1.scatter(forecast_result['anomalies']['ds'],
                        forecast_result['anomalies']['yhat'],
                        color='red', s=100, label='Anomalies', zorder=5)

        ax1.set_xlabel('Date')
        ax1.set_ylabel('Metric Value')
        ax1.set_title('Forecast with Confidence Interval')
        ax1.legend()
        ax1.grid(True, alpha=0.3)

        # 2. Компоненты прогноза
        ax2 = axes[0, 1]
        # Можно добавить разложение на компоненты, если доступно
        ax2.set_title('Forecast Components')
        ax2.text(0.5, 0.5, 'Component analysis\n(requires Prophet model plot_components)',
                 horizontalalignment='center', verticalalignment='center')
        ax2.axis('off')

        # 3. Метрики качества (если есть)
        ax3 = axes[1, 0]
        if metrics:
            metric_names = list(metrics.keys())
            metric_values = list(metrics.values())

            bars = ax3.bar(metric_names, metric_values)
            ax3.set_ylabel('Value')
            ax3.set_title('Model Evaluation Metrics')
            ax3.set_xticklabels(metric_names, rotation=45)

            # Добавление значений на столбцы
            for bar, value in zip(bars, metric_values):
                ax3.text(bar.get_x() + bar.get_width() / 2, bar.get_height(),
                         f'{value:.2f}', ha='center', va='bottom')
        else:
            ax3.text(0.5, 0.5, 'No evaluation metrics available',
                     horizontalalignment='center', verticalalignment='center')
            ax3.axis('off')

        # 4. Аномалии
        ax4 = axes[1, 1]
        if 'anomalies' in forecast_result and len(forecast_result['anomalies']) > 0:
            anomalies = forecast_result['anomalies']
            ax4.bar(range(len(anomalies)), anomalies['z_score'])
            ax4.set_xlabel('Anomaly Index')
            ax4.set_ylabel('Z-Score')
            ax4.set_title(f'Detected Anomalies ({len(anomalies)} found)')
            ax4.axhline(y=3, color='r', linestyle='--', label='Threshold (3σ)')
            ax4.axhline(y=-3, color='r', linestyle='--')
            ax4.legend()
        else:
            ax4.text(0.5, 0.5, 'No anomalies detected',
                     horizontalalignment='center', verticalalignment='center')
            ax4.axis('off')

        plt.tight_layout()

        # Сохранение дашборда
        save_path = Path('forecasts') / f"dashboard_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        plt.show()

        logger.info(f"Dashboard saved to {save_path}")


# Основной pipeline
def run_production_pipeline(df_path: str,
                            server: str,
                            metric: str,
                            retrain: bool = False):
    """Запуск полного pipeline для продакшена"""

    logger.info("=" * 60)
    logger.info(f"Starting production pipeline for {server} - {metric}")
    logger.info("=" * 60)

    try:
        # 1. Загрузка данных
        logger.info("Step 1: Loading data...")
        df = pd.read_excel(df_path)
        df['timestamp'] = pd.to_datetime(df['timestamp'],
                                         format="%Y-%m-%d %H:%M:%S",
                                         errors='coerce')

        # 2. Предобработка
        logger.info("Step 2: Preprocessing data...")
        preprocessor = DataPreprocessor()
        processed_df = preprocessor.prepare_data(df, server, metric)

        # 3. Инициализация и обучение модели
        logger.info("Step 3: Training model...")

        model_filename = f"{server}_{metric}_model.pkl"
        model_path = MODEL_DIR / model_filename

        if retrain or not model_path.exists():
            forecaster = ProductionProphetForecaster()
            forecaster.train(processed_df, optimize=True)
            forecaster.save_model(model_filename)
        else:
            logger.info("Loading existing model...")
            forecaster = ProductionProphetForecaster.load_model(model_path)

        # 4. Оценка модели
        logger.info("Step 4: Evaluating model...")
        metrics = forecaster.evaluate(processed_df)

        # 5. Прогнозирование
        logger.info("Step 5: Generating forecast...")
        forecast_result = forecaster.predict()

        # 6. Визуализация
        logger.info("Step 6: Creating dashboard...")
        MonitoringDashboard.create_dashboard(forecast_result, metrics)

        # 7. Экспорт результатов
        logger.info("Step 7: Exporting results...")

        # Экспорт прогноза
        forecast_df = forecast_result['forecast'].tail(48)
        forecast_df.to_excel(
            f'forecasts/{server}_{metric}_next_24h_{datetime.now().strftime("%Y%m%d")}.xlsx',
            index=False
        )

        # Экспорт метрик
        if metrics:
            metrics_df = pd.DataFrame([metrics])
            metrics_df.to_excel(
                f'forecasts/{server}_{metric}_metrics_{datetime.now().strftime("%Y%m%d")}.xlsx',
                index=False
            )

        logger.info("Pipeline completed successfully!")

        return {
            'forecaster': forecaster,
            'forecast': forecast_result,
            'metrics': metrics,
            'status': 'success'
        }

    except Exception as e:
        logger.error(f"Pipeline failed: {e}", exc_info=True)
        return {
            'status': 'error',
            'error': str(e)
        }


def evaluate_prophet_model(model, test_df, forecast_df):
    """Простая оценка модели Prophet"""

    # Совмещение прогноза и факта
    merged = pd.merge(
        test_df,
        forecast_df[['ds', 'yhat', 'yhat_lower', 'yhat_upper']],
        on='ds'
    )

    # Расчет метрик
    metrics = {
        'MAE': np.mean(np.abs(merged['yhat'] - merged['y'])),
        'RMSE': np.sqrt(np.mean((merged['yhat'] - merged['y']) ** 2)),
        'MAPE': np.mean(np.abs((merged['yhat'] - merged['y']) / merged['y'])) * 100,
        'Coverage': ((merged['y'] >= merged['yhat_lower']) &
                     (merged['y'] <= merged['yhat_upper'])).mean() * 100
    }

    return metrics


if __name__ == '__main__':
    # Пример использования
    import argparse

    parser = argparse.ArgumentParser(description='Server metrics forecasting')
    parser.add_argument('--data', type=str,
                        default='/Users/sweetd0ve/dashboard/data/processed/DataLake-DBN1_cpu.usage.average_2025-11-25 17:00:00_2025-11-30 23:30:00.xlsx',
                         help='Path to data file')
    parser.add_argument('--server', type=str, default='DataLake-DBN1',
                        help='Server name')
    parser.add_argument('--metric', type=str, default='cpu.usage.average',
                        help='Metric name')
    parser.add_argument('--retrain', action='store_true',
                        help='Force retrain model')

    args = parser.parse_args()

    # Запуск pipeline
    result = run_production_pipeline(
        df_path=args.data,
        server=args.server,
        metric=args.metric,
        retrain=args.retrain
    )

    # Вывод результата
    if result['status'] == 'success':
        print(f"\n✅ Forecast completed successfully!")
        print(f"📊 Metrics: {result.get('metrics', {})}")
        print(f"📈 Forecast saved in 'forecasts/' directory")
    else:
        print(f"\n❌ Forecast failed: {result.get('error', 'Unknown error')}")
        sys.exit(1)