import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
import sys
import os
import numpy as np
from plotly.subplots import make_subplots
import warnings
from prophet import Prophet


warnings.filterwarnings('ignore')

# Добавляем путь для импорта
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
repo_root = os.path.abspath(os.path.join(current_dir, "..", "..", ".."))
sys.path.append(parent_dir)

# Импортируем модули для загрузки данных из базы
try:
    from utils.data_loader import load_data_from_database, generate_server_data
    from utils.base_logger import logger
    from app.prophet_forecaster import ProphetForecaster
except ImportError as e:
    logger.info(f"Ошибка импорта: {e}")


# Импортируем модули для работы с базой данных
app_dir = os.path.join(parent_dir, '..', 'app')
sys.path.insert(0, app_dir)
try:
    from app.connection import SessionLocal
    from app.facts_crud import FactsCRUD
except ImportError:
    logger.info("Модули базы данных не найдены, используется режим демо")
    SessionLocal = None
    FactsCRUD = None


@st.cache_data(ttl=300)
def load_as_mapping_data():
    """Загружает данные о маппинге серверов на АС"""
    try:
        file_path = os.path.join(repo_root, "data", "source", "all_vm.xlsx")
        if not os.path.exists(file_path):
            possible_paths = [
                os.path.join(repo_root, "data", "source", "all_vm.xlsx"),
                os.path.join("data", "source", "all_vm.xlsx"),
                "all_vm.xlsx",
            ]

            for path in possible_paths:
                if os.path.exists(path):
                    file_path = path
                    break

        if os.path.exists(file_path):
            df = pd.read_excel(file_path)
            mapping = {}
            for _, row in df.iterrows():
                server_name = str(row.get('Имя КЕ', '')).strip()
                as_name = str(row.get('Объект обслуживания (АС/ПС)', '')).strip()

                if server_name and as_name and as_name != 'nan':
                    server_normalized = server_name.lower().replace('_', '-').replace(' ', '-')
                    mapping[server_normalized] = as_name
                    mapping[server_name] = as_name
            return mapping
    except Exception as e:
        st.warning(f"Ошибка загрузки маппинга АС: {e}")
        servers = [f"Server_{i}" for i in range(1, 21)]
        as_list = ["ERP_System", "CRM_System", "HR_System", "Finance_System", "BI_System"]
        mapping = {}
        for server in servers:
            as_name = np.random.choice(as_list)
            mapping[server] = as_name
        return mapping


@st.cache_data(ttl=300)
def load_historical_data_for_as(as_name, as_mapping, history_days=30):
    """Загружает исторические данные для всех серверов АС с отказоустойчивостью"""
    try:
        # Загружаем все данные
        end_date = datetime.now()
        start_date = end_date - timedelta(days=history_days)
        
        # Получаем список серверов этой АС (все варианты написания)
        servers_in_as = []
        for server, mapped_name in as_mapping.items():
            if str(mapped_name).strip() == str(as_name).strip():
                servers_in_as.append(server)
        
        st.info(f"Найдено серверов в АС '{as_name}': {len(servers_in_as)}")
        
        # Загружаем данные для этих серверов
        if load_data_from_database:
            try:
                data = load_data_from_database(start_date=start_date, end_date=end_date)
                st.success(f"Загружено {len(data)} записей из БД")
            except Exception as db_error:
                st.warning(f"Ошибка загрузки из БД: {db_error}")
                
        
        # Фильтруем по серверам этой АС
        if 'server' in data.columns and 'as_name' not in data.columns:
            data['as_name'] = data['server'].map(as_mapping)
        
        if 'as_name' in data.columns:
            filtered_data = data[data['as_name'] == as_name]
            st.success(f"Отфильтровано {len(filtered_data)} записей для АС '{as_name}'")
        else:
            filtered_data = data
            st.warning("Колонка as_name не найдена, использую все данные")
        
        # Проверяем наличие необходимых метрик
        required_metrics = ['cpu.usage.average', 'mem.usage.average']
        available_metrics = [col for col in filtered_data.columns if any(m in col for m in ['cpu', 'mem', 'usage'])]
        
        if not available_metrics:
            # Добавляем демо-метрики если их нет
            for metric in required_metrics:
                filtered_data[metric] = np.random.uniform(10, 80, len(filtered_data))
        
        return filtered_data
        
    except Exception as e:
        st.error(f"Ошибка загрузки данных для АС {as_name}: {e}")
        import traceback
        st.code(traceback.format_exc())


def prepare_data_for_prophet(df, metric, server_name=None):
    """Подготавливает данные для Prophet с менее строгими условиями"""
    if df.empty:
        return pd.DataFrame()
    
    # Проверяем наличие метрики в данных
    available_columns = df.columns.tolist()
    if metric not in available_columns:
        # Пробуем найти похожие метрики
        similar_metrics = [col for col in available_columns if metric.split('.')[0] in col.lower()]
        if similar_metrics:
            metric = similar_metrics[0]
        else:
            return pd.DataFrame()
    
    # Фильтруем данные для конкретного сервера если указан
    if server_name:
        df_filtered = df[df['server'] == server_name].copy()
    else:
        df_filtered = df.copy()
    
    if df_filtered.empty:
        return pd.DataFrame()
    
    # Проверяем наличие timestamp
    if 'timestamp' not in df_filtered.columns:
        # Ищем альтернативные названия
        time_cols = [col for col in df_filtered.columns if 'time' in col.lower() or 'date' in col.lower()]
        if time_cols:
            df_filtered = df_filtered.rename(columns={time_cols[0]: 'timestamp'})
        else:
            return pd.DataFrame()
    
    # Подготавливаем данные в формате Prophet
    try:
        prophet_df = df_filtered[['timestamp', metric]].copy()
        prophet_df.columns = ['ds', 'y']
        
        # Преобразуем в datetime
        prophet_df['ds'] = pd.to_datetime(prophet_df['ds'], errors='coerce')
        prophet_df = prophet_df.dropna(subset=['ds', 'y'])
        
        # Удаляем дубликаты по времени
        prophet_df = prophet_df.drop_duplicates(subset=['ds'])
        
        # Минимальное требование - 4 точки данных
        if len(prophet_df) < 4:
            st.warning(f"Для сервера {server_name} недостаточно данных: {len(prophet_df)} точек")
            return pd.DataFrame()
        
        # Сортируем по времени
        prophet_df['ds'] = pd.to_datetime(prophet_df['ds']).dt.tz_localize(None)
        prophet_df = prophet_df.sort_values('ds')
        
        # Логируем информацию о данных
        st.info(f"Данные для {server_name}: {len(prophet_df)} точек с {prophet_df['ds'].min()} по {prophet_df['ds'].max()}")
        
        return prophet_df
        
    except Exception as e:
        st.warning(f"Ошибка подготовки данных для {server_name}: {str(e)}")
        return pd.DataFrame()


def generate_forecast_for_server(prophet_df: pd.DataFrame, forecast_days: int):
    def add_time_features(df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        dt = df['ds']
        df['hour'] = dt.dt.hour
        df['day_of_week'] = dt.dt.dayofweek
        df['day_of_month'] = dt.dt.day
        df['week_of_year'] = dt.dt.isocalendar().week.astype(int)
        df['month'] = dt.dt.month
        df['quarter'] = dt.dt.quarter
        df['is_weekend'] = (dt.dt.dayofweek >= 5).astype(int)
        df['is_month_start'] = dt.dt.is_month_start.astype(int)
        df['is_month_end'] = dt.dt.is_month_end.astype(int)
        df['is_quarter_start'] = dt.dt.is_quarter_start.astype(int)
        df['is_quarter_end'] = dt.dt.is_quarter_end.astype(int)
        df['is_year_start'] = dt.dt.is_year_start.astype(int)
        df['is_year_end'] = dt.dt.is_year_end.astype(int)
        return df

    def build_model(params: dict, feature_columns: list) -> Prophet:
        model = Prophet(
            daily_seasonality=params['daily_seasonality'],
            weekly_seasonality=params['weekly_seasonality'],
            yearly_seasonality=params['yearly_seasonality'],
            seasonality_mode=params['seasonality_mode'],
            changepoint_prior_scale=params['changepoint_prior_scale'],
            seasonality_prior_scale=params['seasonality_prior_scale'],
            holidays_prior_scale=params['holidays_prior_scale'],
            changepoint_range=params['changepoint_range'],
            n_changepoints=params['n_changepoints'],
        )
        for col in feature_columns:
            model.add_regressor(col)
        return model

    # Добавляем расширенные временные признаки
    prophet_df = add_time_features(prophet_df)
    feature_columns = [
        'hour',
        'day_of_week',
        'day_of_month',
        'week_of_year',
        'month',
        'quarter',
        'is_weekend',
        'is_month_start',
        'is_month_end',
        'is_quarter_start',
        'is_quarter_end',
        'is_year_start',
        'is_year_end',
    ]

    def evaluate_with_holdout(train_data: pd.DataFrame, val_data: pd.DataFrame, params: dict) -> float:
        model = build_model(params, feature_columns)
        model.fit(train_data)
        val_forecast = model.predict(val_data[['ds'] + feature_columns])
        val_actual = val_data['y'].values
        val_pred = val_forecast['yhat'].values
        return float(np.mean(np.abs(val_actual - val_pred)))

    def evaluate_with_cv(data: pd.DataFrame, params: dict, n_splits: int, horizon_points: int) -> float:
        maes = []
        total_points = len(data)
        for split_idx in range(1, n_splits + 1):
            train_end = total_points - horizon_points * (n_splits - split_idx + 1)
            train_df = data.iloc[:train_end]
            val_df = data.iloc[train_end:train_end + horizon_points]
            if len(train_df) < 4 or len(val_df) < 4:
                continue
            try:
                mae = evaluate_with_holdout(train_df, val_df, params)
                maes.append(mae)
            except Exception:
                continue
        if not maes:
            return np.inf
        return float(np.mean(maes))

    # Подготовка train/val разбиения для подбора гиперпараметров
    prophet_df = prophet_df.sort_values('ds')
    total_points = len(prophet_df)
    yearly_seasonality = (prophet_df['ds'].max() - prophet_df['ds'].min()).days >= 365

    if total_points < 8:
        fallback_params = {
            'daily_seasonality': True,
            'weekly_seasonality': True,
            'yearly_seasonality': yearly_seasonality,
            'seasonality_mode': 'additive',
            'changepoint_prior_scale': 0.05,
            'seasonality_prior_scale': 10.0,
            'holidays_prior_scale': 10.0,
            'changepoint_range': 0.9,
            'n_changepoints': 25,
        }
        best_model = build_model(fallback_params, feature_columns)
        best_model.fit(prophet_df)

        forecast_hours = forecast_days * 24
        future = best_model.make_future_dataframe(
            periods=forecast_hours * 2,
            freq='30min',
            include_history=False
        )
        future = add_time_features(future)
        forecast = best_model.predict(future[['ds'] + feature_columns])
        return forecast, best_model, None, "default"

    val_size = max(10, int(total_points * 0.2))
    val_size = min(val_size, total_points - 4)

    train_df = prophet_df.iloc[:-val_size].copy()
    val_df = prophet_df.iloc[-val_size:].copy()

    # Сетка гиперпараметров
    param_grid = [
        {
            'daily_seasonality': True,
            'weekly_seasonality': True,
            'yearly_seasonality': yearly_seasonality,
            'seasonality_mode': seasonality_mode,
            'changepoint_prior_scale': cps,
            'seasonality_prior_scale': sps,
            'holidays_prior_scale': hps,
            'changepoint_range': cpr,
            'n_changepoints': ncp,
        }
        for seasonality_mode in ['additive', 'multiplicative']
        for cps in [0.01, 0.05, 0.1, 0.2]
        for sps in [3.0, 5.0, 10.0, 15.0]
        for hps in [5.0, 10.0]
        for cpr in [0.8, 0.9, 0.95]
        for ncp in [15, 25, 35]
    ]

    # Подбор лучшей модели по MAE на валидации или кросс-валидации
    best_score = np.inf
    best_params = None
    best_model = None

    # Определяем, когда уместна кросс-валидация
    horizon_points = max(8, min(48, int(total_points * 0.1)))
    max_splits = total_points // (horizon_points * 2)
    n_splits = min(4, max(2, max_splits))
    use_cv = n_splits >= 2 and total_points >= (horizon_points * (n_splits + 1))
    eval_method = "cv" if use_cv else "holdout"

    for params in param_grid:
        try:
            if use_cv:
                mae = evaluate_with_cv(prophet_df, params, n_splits, horizon_points)
            else:
                mae = evaluate_with_holdout(train_df, val_df, params)

            if mae < best_score:
                best_score = mae
                best_params = params
        except Exception:
            continue

    # Если оптимизация не удалась, используем базовые параметры
    if best_params is None:
        fallback_params = {
            'daily_seasonality': True,
            'weekly_seasonality': True,
            'yearly_seasonality': yearly_seasonality,
            'seasonality_mode': 'additive',
            'changepoint_prior_scale': 0.05,
            'seasonality_prior_scale': 10.0,
            'holidays_prior_scale': 10.0,
            'changepoint_range': 0.9,
            'n_changepoints': 25,
        }
        best_model = build_model(fallback_params, feature_columns)
        best_model.fit(prophet_df)
    else:
        # Переобучаем лучшую модель на всех данных
        best_model = build_model(best_params, feature_columns)
        best_model.fit(prophet_df)

    # Создаем фрейм для прогноза
    forecast_hours = forecast_days * 24
    future = best_model.make_future_dataframe(
        periods=forecast_hours * 2,
        freq='30min',
        include_history=False
    )
    future = add_time_features(future)

    # Генерируем прогноз
    forecast = best_model.predict(future[['ds'] + feature_columns])
    return forecast, best_model, best_score, eval_method


def generate_forecast_for_as(as_name, servers_data, metric, forecast_days, as_mapping):
    """Генерирует прогноз для всех серверов АС"""
    results = {}

    for server in servers_data['server'].unique():
        # Подготавливаем данные для этого сервера
        prophet_df = prepare_data_for_prophet(servers_data, metric, server)

        if prophet_df.empty:
            continue

        try:
            forecast, model, quality_mae, quality_method = generate_forecast_for_server(
                prophet_df,
                forecast_days
            )

            # Сохраняем результаты
            results[server] = {
                'forecast': forecast[['ds', 'yhat', 'yhat_lower', 'yhat_upper']],
                'model': model,
                'history': prophet_df,
                'quality_mae': quality_mae,
                'quality_method': quality_method
            }

        except Exception as e:
            st.warning(f"Ошибка прогноза для сервера {server}: {e}")
            continue

    return results


def create_forecast_plot(server_name, forecast_results, metric, as_name):
    """Создает график прогноза для одного сервера"""
    if server_name not in forecast_results:
        return None

    result = forecast_results[server_name]
    forecast_df = result['forecast']
    history_df = result['history']

    fig = go.Figure()

    # Исторические данные (если есть)
    if not history_df.empty:
        fig.add_trace(go.Scatter(
            x=history_df['ds'],
            y=history_df['y'],
            mode='lines',
            name='Исторические данные',
            line=dict(color='#1E88E5', width=2),
            hovertemplate='<b>%{x}</b><br>Значение: %{y:.1f}%<extra></extra>'
        ))

    # Прогноз
    fig.add_trace(go.Scatter(
        x=forecast_df['ds'],
        y=forecast_df['yhat'],
        mode='lines',
        name='Прогноз',
        line=dict(color='#FF5722', width=3, dash='dash'),
        hovertemplate='<b>%{x}</b><br>Прогноз: %{y:.1f}%<extra></extra>'
    ))

    # Доверительный интервал
    fig.add_trace(go.Scatter(
        x=forecast_df['ds'].tolist() + forecast_df['ds'].tolist()[::-1],
        y=forecast_df['yhat_upper'].tolist() + forecast_df['yhat_lower'].tolist()[::-1],
        fill='toself',
        fillcolor='rgba(255, 87, 34, 0.2)',
        line=dict(color='rgba(255,255,255,0)'),
        hoverinfo='skip',
        name='Доверительный интервал (80%)'
    ))

    # Настройка layout
    metric_name = "CPU" if "cpu" in metric.lower() else "RAM"
    fig.update_layout(
        title=f'<b>{server_name}</b><br>Прогноз {metric_name} нагрузки',
        xaxis_title='<b>Дата и время</b>',
        yaxis_title=f'<b>Нагрузка {metric_name} (%)</b>',
        height=400,
        hovermode='x unified',
        plot_bgcolor='rgba(240, 242, 246, 1)',
        paper_bgcolor='rgba(255, 255, 255, 1)',
        legend=dict(
            yanchor="top",
            y=0.99,
            xanchor="left",
            x=0.01,
            bgcolor='rgba(255, 255, 255, 0.9)'
        ),
        margin=dict(l=50, r=30, t=80, b=50)
    )

    return fig


def create_summary_table(forecast_results, as_name, metric):
    """Создает сводную таблицу прогнозов"""
    summary_data = []

    for server, result in forecast_results.items():
        forecast_df = result['forecast']

        # Рассчитываем статистики
        avg_forecast = forecast_df['yhat'].mean()
        max_forecast = forecast_df['yhat'].max()
        min_forecast = forecast_df['yhat'].min()

        # Время пиковой нагрузки
        max_idx = forecast_df['yhat'].idxmax()
        peak_time = forecast_df.loc[max_idx, 'ds']

        # Оценка риска
        if max_forecast > 85:
            risk_level = "🟥 Критический"
        elif max_forecast > 70:
            risk_level = "🟧 Высокий"
        elif max_forecast > 50:
            risk_level = "🟨 Средний"
        else:
            risk_level = "🟩 Низкий"

        quality_mae = result.get('quality_mae')
        quality_method = result.get('quality_method', 'unknown')
        quality_label = "—" if quality_mae is None else f"{quality_mae:.3f}"

        summary_data.append({
            'Сервер': server,
            'Средняя': f"{avg_forecast:.1f}%",
            'Максимум': f"{max_forecast:.1f}%",
            'Минимум': f"{min_forecast:.1f}%",
            'Пик в': peak_time.strftime('%d.%m %H:%M'),
            'Риск': risk_level,
            'MAE': quality_label,
            'Метод оценки': quality_method
        })

    return pd.DataFrame(summary_data)


def show():
    """Страница прогнозирования по АС"""
    st.markdown('<h2 class="sub-header">🔮 Прогноз нагрузки по Автоматизированным Системам</h2>', unsafe_allow_html=True)

    try:
        # Загружаем маппинг АС
        with st.spinner("Загружаем данные об АС..."):
            as_mapping = load_as_mapping_data()

        if not as_mapping:
            st.error("⚠️ Не удалось загрузить данные об АС")
            return

        # Получаем список уникальных АС
        all_as = sorted(set(as_mapping.values()))

        if not all_as:
            st.warning("⚠️ АС не найдены в базе данных")
            return

        col1, col2 = st.columns([1, 3])

        with col1:
            st.markdown('<div class="server-selector fade-in">', unsafe_allow_html=True)

            # Выбор АС
            selected_as = st.selectbox(
                "**Выберите АС для прогноза:**",
                all_as,
                index=0 if all_as else None,
                key="forecast_as_select"
            )

            # Выбор метрики
            metric_options = {
                "cpu.usage.average": "cpu.usage.average",
                "mem.usage.average": "mem.usage.average"
            }

            selected_metric = st.selectbox(
                "**Выберите метрику:**",
                list(metric_options.keys()),
                format_func=lambda x: metric_options[x],
                key="forecast_metric_select"
            )

            # Параметры прогноза
            st.markdown("### ⚙️ Параметры")

            forecast_days = st.slider(
                "**Период прогноза (дней):**",
                min_value=1,
                max_value=14,
                value=7,
                step=1,
                key="forecast_days"
            )

            history_days = st.slider(
                "**Исторические данные (дней):**",
                min_value=7,
                max_value=90,
                value=30,
                step=7,
                key="history_days"
            )

            # Опции отображения
            st.markdown("### 👁️ Отображение")

            show_individual = st.checkbox(
                "Показывать индивидуальные графики",
                value=True,
                help="Показывать отдельный график для каждого сервера"
            )

            max_servers_to_show = st.slider(
                "Максимум серверов для отображения:",
                min_value=5,
                max_value=20,
                value=10,
                step=1
            )

            # Кнопка генерации прогноза
            generate_btn = st.button(
                "🚀 Сгенерировать прогноз",
                type="primary",
                use_container_width=True,
                key="generate_forecast_btn"
            )

            st.markdown('</div>', unsafe_allow_html=True)

        with col2:
            if generate_btn or st.session_state.get('forecast_generated', False):
                st.session_state.forecast_generated = True

                with st.spinner(f"Загружаем данные для АС '{selected_as}'..."):
                    # Загружаем данные для выбранной АС
                    servers_data = load_historical_data_for_as(
                        selected_as,
                        as_mapping,
                        history_days
                    )

                if servers_data.empty:
                    st.warning(f"⚠️ Нет данных для АС '{selected_as}'")
                    return

                # Получаем список серверов в этой АС
                servers_in_as = servers_data['server'].unique().tolist()
                server_count = len(servers_in_as)

                st.success(f"✅ Найдено {server_count} серверов в АС '{selected_as}'")

                # Прогресс бар для генерации прогноза
                progress_bar = st.progress(0)
                status_text = st.empty()

                with st.spinner("Генерируем прогнозы..."):
                    # Генерируем прогнозы для всех серверов
                    forecast_results = generate_forecast_for_as(
                        selected_as,
                        servers_data,
                        selected_metric,
                        forecast_days,
                        as_mapping
                    )

                if not forecast_results:
                    st.error("⚠️ Не удалось сгенерировать прогнозы")
                    return

                # Отображаем статистику
                st.markdown("### 📊 Статистика прогноза")

                col_stat1, col_stat2, col_stat3, col_stat4 = st.columns(4)

                with col_stat1:
                    st.metric("АС", selected_as)

                with col_stat2:
                    st.metric("Серверов", f"{len(forecast_results)}/{server_count}")

                with col_stat3:
                    # Средняя максимальная нагрузка
                    max_loads = []
                    for result in forecast_results.values():
                        max_loads.append(result['forecast']['yhat'].max())
                    avg_max_load = np.mean(max_loads) if max_loads else 0
                    st.metric("Ср. пик нагрузки", f"{avg_max_load:.1f}%")

                with col_stat4:
                    # Серверы с критической нагрузкой
                    critical_servers = 0
                    for result in forecast_results.values():
                        if result['forecast']['yhat'].max() > 85:
                            critical_servers += 1
                    st.metric("Критич. серверов", critical_servers)

                # Сводная таблица
                st.markdown("### 📋 Сводная таблица прогнозов")
                summary_df = create_summary_table(forecast_results, selected_as, selected_metric)

                # Сортировка по риску и максимальной нагрузке
                def risk_sort_key(row):
                    risk_map = {"🟥 Критический": 0, "🟧 Высокий": 1, "🟨 Средний": 2, "🟩 Низкий": 3}
                    return risk_map.get(row['Риск'], 4)

                summary_df['risk_numeric'] = summary_df.apply(risk_sort_key, axis=1)
                summary_df = summary_df.sort_values(['risk_numeric', 'Максимум'], ascending=[True, False])
                summary_df = summary_df.drop('risk_numeric', axis=1)

                # Отображаем таблицу с цветовым кодированием
                st.dataframe(
                    summary_df.style.apply(
                        lambda x: ['background-color: #ffcccc' if 'Критический' in str(v) else
                                   'background-color: #ffe6cc' if 'Высокий' in str(v) else
                                   'background-color: #fff2cc' if 'Средний' in str(v) else
                                   'background-color: #d9ead3' for v in x],
                        subset=['Риск']
                    ),
                    use_container_width=True,
                    height=400
                )

                # Индивидуальные графики
                if show_individual and forecast_results:
                    st.markdown("### 📈 Индивидуальные прогнозы")

                    # Ограничиваем количество отображаемых графиков
                    servers_to_show = list(forecast_results.keys())[:max_servers_to_show]

                    for i, server in enumerate(servers_to_show):
                        st.markdown(f"#### Сервер: {server}")

                        fig = create_forecast_plot(
                            server,
                            forecast_results,
                            selected_metric,
                            selected_as
                        )

                        if fig:
                            st.plotly_chart(fig, use_container_width=True)

                        # Разделитель между серверами
                        if i < len(servers_to_show) - 1:
                            st.divider()

                # Агрегированный прогноз по АС
                st.markdown("### 📊 Агрегированный прогноз по АС")

                try:
                    # Собираем все прогнозы в один DataFrame
                    all_forecasts = []
                    for server, result in forecast_results.items():
                        forecast_df = result['forecast'].copy()
                        forecast_df['server'] = server
                        all_forecasts.append(forecast_df)

                    if all_forecasts:
                        combined_forecasts = pd.concat(all_forecasts, ignore_index=True)

                        # Рассчитываем средние значения по времени
                        aggregated = combined_forecasts.groupby('ds').agg({
                            'yhat': 'mean',
                            'yhat_lower': 'mean',
                            'yhat_upper': 'mean'
                        }).reset_index()

                        # Создаем агрегированный график
                        fig_agg = go.Figure()

                        fig_agg.add_trace(go.Scatter(
                            x=aggregated['ds'],
                            y=aggregated['yhat'],
                            mode='lines',
                            name='Средний прогноз',
                            line=dict(color='#4CAF50', width=3),
                            hovertemplate='<b>%{x}</b><br>Средняя нагрузка: %{y:.1f}%<extra></extra>'
                        ))

                        fig_agg.add_trace(go.Scatter(
                            x=aggregated['ds'].tolist() + aggregated['ds'].tolist()[::-1],
                            y=aggregated['yhat_upper'].tolist() + aggregated['yhat_lower'].tolist()[::-1],
                            fill='toself',
                            fillcolor='rgba(76, 175, 80, 0.2)',
                            line=dict(color='rgba(255,255,255,0)'),
                            hoverinfo='skip',
                            name='Доверительный интервал'
                        ))

                        metric_name = "CPU" if "cpu" in selected_metric.lower() else "RAM"
                        fig_agg.update_layout(
                            title=f'<b>Агрегированный прогноз {metric_name} нагрузки для АС "{selected_as}"</b>',
                            xaxis_title='<b>Дата и время</b>',
                            yaxis_title=f'<b>Средняя нагрузка {metric_name} (%)</b>',
                            height=500,
                            hovermode='x unified',
                            plot_bgcolor='rgba(240, 242, 246, 1)',
                            paper_bgcolor='rgba(255, 255, 255, 1)'
                        )

                        st.plotly_chart(fig_agg, use_container_width=True)

                        # Статистика по агрегированному прогнозу
                        col_agg1, col_agg2, col_agg3 = st.columns(3)
                        with col_agg1:
                            avg_load = aggregated['yhat'].mean()
                            st.metric("Средняя нагрузка", f"{avg_load:.1f}%")

                        with col_agg2:
                            peak_load = aggregated['yhat'].max()
                            peak_time = aggregated.loc[aggregated['yhat'].idxmax(), 'ds']
                            st.metric("Пиковая нагрузка", f"{peak_load:.1f}%", f"в {peak_time.strftime('%H:%M')}")

                        with col_agg3:
                            if peak_load > 85:
                                overall_risk = "🟥 Критический"
                            elif peak_load > 65:
                                overall_risk = "🟧 Высокий"
                            elif peak_load > 50:
                                overall_risk = "🟨 Средний"
                            else:
                                overall_risk = "🟩 Низкий"
                            st.metric("Общий риск", overall_risk)

                except Exception as e:
                    st.warning(f"Не удалось создать агрегированный прогноз: {e}")

                # Рекомендации
                st.markdown("### 💡 Рекомендации по АС")

                # Анализируем риски
                critical_count = 0
                high_count = 0
                for result in forecast_results.values():
                    max_load = result['forecast']['yhat'].max()
                    if max_load > 85:
                        critical_count += 1
                    elif max_load > 70:
                        high_count += 1

                if critical_count > 0:
                    st.error(f"""
                    **⚠️ Требуются срочные меры ({critical_count} серверов с критической нагрузкой):**
                    - **Масштабирование ресурсов:** Рассмотрите увеличение CPU/RAM для критических серверов
                    - **Балансировка нагрузки:** Перенаправьте часть нагрузки на менее загруженные серверы
                    - **Оптимизация приложений:** Проверьте оптимизацию кода и запросов к БД
                    - **Мониторинг в реальном времени:** Установите алерты для критических порогов
                    """)
                elif high_count > 0:
                    st.warning(f"""
                    **🟡 Рекомендуется мониторинг ({high_count} серверов с высокой нагрузкой):**
                    - **Планирование ресурсов:** Подготовьте план масштабирования на пиковые периоды
                    - **Анализ трендов:** Изучите паттерны нагрузки для оптимизации
                    - **Резервные мощности:** Убедитесь в наличии резервных ресурсов
                    - **Проактивный мониторинг:** Установите алерты на 70% нагрузку
                    """)
                else:
                    st.success(f"""
                    **🟢 Система стабильна:**
                    - **Текущие ресурсы достаточны:** Все серверы в пределах нормы
                    - **Продолжайте мониторинг:** Регулярно проверяйте метрики
                    - **Плановое обслуживание:** Оптимальное время для обновлений
                    - **Анализ эффективности:** Изучите возможности оптимизации затрат
                    """)

                # Экспорт данных
                st.markdown("---")
                col_export1, col_export2 = st.columns(2)

                with col_export1:
                    if st.button("📊 Экспорт прогнозов (CSV)", type="secondary", use_container_width=True):
                        try:
                            # Собираем все данные для экспорта
                            export_data = []
                            for server, result in forecast_results.items():
                                forecast_df = result['forecast'].copy()
                                forecast_df['server'] = server
                                forecast_df['as_name'] = selected_as
                                forecast_df['metric'] = selected_metric
                                export_data.append(forecast_df)

                            if export_data:
                                export_df = pd.concat(export_data, ignore_index=True)
                                csv = export_df.to_csv(index=False, encoding='utf-8-sig')

                                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                                filename = f"forecast_{selected_as}_{selected_metric}_{timestamp}.csv"

                                st.download_button(
                                    label="⬇️ Скачать CSV",
                                    data=csv,
                                    file_name=filename,
                                    mime="text/csv",
                                    use_container_width=True
                                )
                        except Exception as e:
                            st.error(f"Ошибка экспорта: {e}")

                with col_export2:
                    if st.button("📈 Экспорт агрегированного графика", type="secondary", use_container_width=True):
                        st.info("Функция экспорта графика в разработке")

            else:
                # Инструкция при первом заходе
                st.markdown('<div class="info-card">', unsafe_allow_html=True)

                st.markdown("## 👋 Добро пожаловать в модуль прогнозирования по АС!")

                st.info("""
                **📋 Возможности модуля:**
                - Прогноз нагрузки CPU и RAM для всех серверов выбранной АС
                - Использование Prophet для точных временных прогнозов
                - Агрегированная статистика по всей АС
                - Индивидуальные графики для каждого сервера
                - Рекомендации по масштабированию ресурсов
                """)

                col_info1, col_info2 = st.columns(2)

                with col_info1:
                    st.markdown("""
                    **🚀 Для начала работы:**
                    1. Выберите АС из списка слева
                    2. Выберите метрику (CPU или RAM)
                    3. Настройте период прогноза
                    4. Нажмите "Сгенерировать прогноз"
                    """)

                with col_info2:
                    st.markdown("""
                    **📊 Вы получите:**
                    - Сводную таблицу с прогнозами
                    - Графики для каждого сервера
                    - Агрегированный прогноз по АС
                    - Автоматические рекомендации
                    - Возможность экспорта данных
                    """)

                st.divider()

                # Статистика по доступным АС
                st.markdown("### 📈 Доступные Автоматизированные Системы")

                # Подсчитываем серверы в каждой АС
                as_stats = {}
                for server, as_name in as_mapping.items():
                    if as_name not in as_stats:
                        as_stats[as_name] = 0
                    as_stats[as_name] += 1

                # Создаем DataFrame для отображения
                stats_df = pd.DataFrame([
                    {'АС': as_name, 'Кол-во серверов': count}
                    for as_name, count in as_stats.items()
                ]).sort_values('Кол-во серверов', ascending=False)

                # Отображаем таблицу
                st.dataframe(
                    stats_df.style.background_gradient(
                        subset=['Кол-во серверов'],
                        cmap='Blues'
                    ),
                    use_container_width=True,
                    height=300
                )

                st.markdown('</div>', unsafe_allow_html=True)

    except Exception as e:
        st.error(f"Ошибка при загрузке данных: {e}")
        import traceback
        with st.expander("Детали ошибки"):
            st.code(traceback.format_exc())

