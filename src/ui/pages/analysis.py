import base64
from datetime import datetime, timedelta
import json
import os
import sys
import tempfile

from jinja2 import Template
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio
from plotly.subplots import make_subplots
import requests
import streamlit as st


# Добавляем путь для импорта
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
repo_root = os.path.abspath(os.path.join(current_dir, "..", "..", ".."))
sys.path.append(parent_dir)

# Импортируем модули для загрузки данных из базы
try:
    from utils.data_loader import generate_server_data, get_all_servers_list, load_data_from_database
except ImportError:
    # Fallback для прямого импорта
    import importlib.util

    get_all_servers_list = None
    generate_server_data = None
    data_loader_path = os.path.join(parent_dir, 'utils', 'data_loader.py')
    if os.path.exists(data_loader_path):
        spec = importlib.util.spec_from_file_location("data_loader", data_loader_path)
        data_loader = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(data_loader)
        load_data_from_database = data_loader.load_data_from_database
        generate_server_data = getattr(data_loader, 'generate_server_data', None)
        get_all_servers_list = getattr(data_loader, 'get_all_servers_list', None)
        # generate_server_data = data_loader.generate_server_data  # Исправлено: data_loader вместо data_generator
    # else:
        # Если нет data_loader, пробуем data_generator
        # data_generator_path = os.path.join(parent_dir, 'utils', 'data_generator.py')
        # spec = importlib.util.spec_from_file_location("data_generator", data_generator_path)
        # data_generator = importlib.util.module_from_spec(spec)
        # spec.loader.exec_module(data_generator)
        # generate_server_data = data_generator.generate_server_data
        # load_data_from_database = None

    # Проверяем наличие модуля с маппингом АС
    as_mapping_path = os.path.join(parent_dir, 'utils', 'as_mapping.py')
    if os.path.exists(as_mapping_path):
        spec = importlib.util.spec_from_file_location("as_mapping", as_mapping_path)
        as_mapping = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(as_mapping)
        get_as_mapping = as_mapping.get_as_mapping
    else:
        # Если модуля нет, создаем функцию заглушку
        def get_as_mapping():
            return {}


@st.cache_data(ttl=300)
def load_data_from_db(start_date: datetime = None, end_date: datetime = None):
    """
    Load data from database with optional date range

    Args:
        start_date: Start date for data loading
        end_date: End date for data loading

    Returns:
        DataFrame with server metrics
    """
    if load_data_from_database is None:
        # Fallback to generate_server_data if database loader not available
        df = generate_server_data()
        if df.empty:
            st.warning("Сгенерированные данные пусты")
            return df

        if start_date or end_date:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            if start_date:
                df = df[df['timestamp'] >= pd.Timestamp(start_date)]
            if end_date:
                df = df[df['timestamp'] <= pd.Timestamp(end_date)]
        return df

    try:
        df = load_data_from_database(
            start_date=start_date,
            end_date=end_date
        )
        return df
    except Exception as e:
        st.warning(f"Ошибка загрузки из базы данных: {e}. Используются данные по умолчанию.")
        # Fallback
        df = generate_server_data()
        if start_date or end_date:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            if start_date:
                df = df[df['timestamp'] >= pd.Timestamp(start_date)]
            if end_date:
                df = df[df['timestamp'] <= pd.Timestamp(end_date)]
        return df


def find_all_vm_file():
    env_path = os.getenv("ALL_VM_XLSX_PATH")
    candidates = [
        env_path,
        os.path.join(repo_root, "data", "source", "all_vm.xlsx"),
        os.path.join(current_dir, "all_vm.xlsx"),
        os.path.join(parent_dir, "data", "source", "all_vm.xlsx"),
        "all_vm.xlsx",
    ]
    cleaned = [path for path in candidates if path]
    for path in cleaned:
        if os.path.exists(path):
            return path, cleaned
    return None, cleaned


@st.cache_data(ttl=3600)
def load_as_mapping_data():
    """Загружает данные о маппинге серверов на АС из Excel файла"""
    try:
        # Пытаемся загрузить из модуля
        mapping = get_as_mapping()
        if mapping:
            return mapping

        # Если модуль не вернул данные, загружаем из файла
        file_path, attempted_paths = find_all_vm_file()
        if file_path:
            df = pd.read_excel(file_path)

            # Создаем словарь маппинга: server_name -> AS
            mapping = {}
            for _, row in df.iterrows():
                server_name = str(row.get('Имя КЕ', '')).strip()
                as_name = str(row.get('Объект обслуживания (АС/ПС)', '')).strip()

                if server_name and as_name and as_name != 'nan':
                    # Нормализуем имена серверов для лучшего сопоставления
                    server_normalized = server_name.lower().replace('_', '-').replace(' ', '-')
                    mapping[server_normalized] = as_name

                    # Также добавляем оригинальное имя
                    mapping[server_name] = as_name

            return mapping
        else:
            st.warning(
                "Файл маппинга АС не найден. Убедитесь, что all_vm.xlsx находится в "
                "data/source в корне проекта или задайте путь через ALL_VM_XLSX_PATH.\n"
                + "\n".join(f"- {path}" for path in attempted_paths)
            )
            return {}

    except Exception as e:
        st.error(f"Ошибка загрузки маппинга АС: {e}")
        return {}


@st.cache_data(ttl=300)
def load_all_servers():
    """Load list of all servers from database (fast: only distinct names, no metrics)."""
    try:
        if get_all_servers_list is not None:
            return get_all_servers_list()
        if generate_server_data is None:
            return []
        df = generate_server_data()
        if df.empty:
            st.warning("Сгенерированные данные пусты")
            return []

        # Проверяем наличие столбца 'server'
        if 'server' not in df.columns:
            st.warning("Столбец 'server' не найден в данных")
            return []

        servers = df['server'].dropna().unique().tolist()
        return sorted(servers)
    except Exception as e:
        st.warning(f"Ошибка загрузки списка серверов: {e}")
        return []


@st.cache_data(ttl=300)
def load_all_as_servers():
    """
    Загружает все серверы, сгруппированные по АС (автоматизированным системам).

    Возвращает:
        dict: Словарь, где ключи - названия АС, значения - списки серверов, принадлежащих этой АС.
              Пример: {'АС1': ['server1', 'server2'], 'АС2': ['server3', 'server4']}

    Raises:
        Exception: При ошибке загрузки данных
    """
    try:
        # Получаем все серверы из базы данных
        all_servers = load_all_servers()

        if not all_servers:
            st.warning("Не удалось загрузить список серверов из базы данных")
            return {}

        # Загружаем маппинг АС
        as_mapping = load_as_mapping_data()

        if not as_mapping:
            st.warning("Не удалось загрузить маппинг АС")
            return {}

        # Создаем словарь для группировки серверов по АС
        as_servers_dict = {}

        # Счетчики для статистики
        matched_servers = 0
        unmatched_servers = 0

        # Список для серверов без АС
        servers_without_as = []

        # Проходим по всем серверам и группируем их по АС
        for server in all_servers:
            # Пробуем найти АС для сервера
            as_name = None

            # Пробуем разные варианты написания имени сервера
            server_variants = [
                server,
                server.lower(),
                server.upper(),
                server.replace('_', '-'),
                server.replace('-', '_'),
                server.replace(' ', '-'),
                server.replace(' ', '_'),
                server.strip(),
                server.strip().lower(),
                server.strip().upper()
            ]

            # Ищем соответствие в маппинге
            for variant in server_variants:
                if variant in as_mapping:
                    as_name = as_mapping[variant]
                    break

            if as_name:
                # Нормализуем имя АС
                as_name_normalized = str(as_name).strip()

                # Добавляем сервер в соответствующую АС
                if as_name_normalized not in as_servers_dict:
                    as_servers_dict[as_name_normalized] = []

                # Добавляем сервер только если его еще нет в списке
                if server not in as_servers_dict[as_name_normalized]:
                    as_servers_dict[as_name_normalized].append(server)

                matched_servers += 1
            else:
                # Сервер не найден в маппинге
                servers_without_as.append(server)
                unmatched_servers += 1

        # Сортируем списки серверов внутри каждой АС
        for as_name in as_servers_dict:
            as_servers_dict[as_name] = sorted(as_servers_dict[as_name])

        # Сортируем ключи (названия АС) для удобства
        as_servers_dict = dict(sorted(as_servers_dict.items()))

        # Если есть серверы без АС, добавляем их в отдельную группу
        if servers_without_as:
            as_servers_dict['Не распределено'] = sorted(servers_without_as)

        # Логируем статистику
        total_servers = len(all_servers)
        if total_servers > 0:
            match_percentage = (matched_servers / total_servers) * 100
            st.info(f"""
            **Статистика распределения серверов по АС:**
            - Всего серверов в базе: **{total_servers}**
            - Распределено по АС: **{matched_servers}** ({match_percentage:.1f}%)
            - Не распределено: **{unmatched_servers}** ({100 - match_percentage:.1f}%)
            - Количество АС: **{len([k for k in as_servers_dict.keys() if k != 'Не распределено'])}**
            """)

        # Дополнительная проверка: убедимся, что есть минимум 11 АС
        as_count = len([k for k in as_servers_dict.keys() if k != 'Не распределено'])
        if as_count < 11:
            st.warning(f"⚠️ Найдено только {as_count} АС, хотя ожидалось не менее 11")
            st.info("💡 Проверьте файл маппинга АС (all_vm.xlsx) на наличие данных.")

        return as_servers_dict

    except Exception as e:
        st.error(f"Ошибка при загрузке серверов по АС: {str(e)}")
        import traceback
        st.debug(f"Трассировка ошибки: {traceback.format_exc()}")
        return {}


def create_timeseries_html(fig_lines, metric_name, date_range, df_data=None):
    """Создает красивый HTML файл с графиком временных рядов"""

    # Определяем отображаемое имя метрики
    metric_display_map = {
        'cpu.usage.average': 'Использование CPU (%)',
        'mem.usage.average': 'Использование памяти (%)',
    }
    metric_display = metric_display_map.get(metric_name, metric_name)

    # Подсчитываем количество серверов
    server_count = len(fig_lines.data) if hasattr(fig_lines, 'data') else 0

    # Создаем упрощенную версию графика для HTML
    fig_html = go.Figure(fig_lines)

    # Улучшаем дизайн графика
    fig_html.update_layout(
        template='plotly_white',
        hovermode='x unified',
        legend=dict(
            title="Серверы",
            yanchor="top",
            y=0.99,
            xanchor="left",
            x=0.01,
            bgcolor='rgba(255, 255, 255, 0.8)',
            bordercolor='rgba(0, 0, 0, 0.2)',
            borderwidth=1
        ),
        margin=dict(l=50, r=20, t=80, b=50),
        height=700,
        title=dict(
            text=f'<b>Временные ряды {metric_display}</b><br><span style="font-size:14px;color:gray">{date_range}</span>',
            x=0.5,
            xanchor='center',
            font=dict(size=20)
        )
    )

    # Конвертируем фигуру в HTML
    plotly_html = pio.to_html(
        fig_html,
        full_html=False,
        include_plotlyjs='cdn',
        config={
            'responsive': True,
            'displayModeBar': True,
            'displaylogo': False,
            'scrollZoom': True,
            'modeBarButtonsToAdd': [
                'drawline',
                'drawopenpath',
                'drawclosedpath',
                'drawcircle',
                'drawrect',
                'eraseshape',
                'toImage'
            ]
        }
    )

    # Собираем статистику
    stats_data = {}
    if df_data is not None and not df_data.empty:
        server_means = df_data.groupby('server')[metric_name].mean()
        stats_data = {
            'avg_load': df_data[metric_name].mean(),
            'max_load': df_data[metric_name].max(),
            'min_load': df_data[metric_name].min(),
            'top_server': server_means.idxmax() if not server_means.empty else '',
            'top_load': server_means.max() if not server_means.empty else 0,
            'server_list': list(df_data['server'].unique())[:20]  # Первые 20 серверов
        }

    # Красивый HTML шаблон
    html_template = """
    <!DOCTYPE html>
    <html lang="ru">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Временные ряды нагрузки серверов</title>
        <script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
        <style>
            :root {
                --primary-color: #4f46e5;
                --primary-dark: #3730a3;
                --secondary-color: #10b981;
                --background-color: #f8fafc;
                --card-bg: #ffffff;
                --text-primary: #1e293b;
                --text-secondary: #64748b;
                --border-color: #e2e8f0;
                --success-color: #10b981;
                --warning-color: #f59e0b;
                --danger-color: #ef4444;
            }

            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }

            body {
                font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                color: var(--text-primary);
                line-height: 1.6;
            }

            .container {
                max-width: 1400px;
                margin: 0 auto;
                padding: 20px;
            }

            .dashboard {
                background: var(--card-bg);
                border-radius: 20px;
                box-shadow: 0 20px 60px rgba(0,0,0,0.15);
                overflow: hidden;
                margin: 20px;
            }

            /* Header */
            .header {
                background: linear-gradient(135deg, var(--primary-color) 0%, var(--primary-dark) 100%);
                color: white;
                padding: 30px 40px;
                position: relative;
                overflow: hidden;
            }

            .header::before {
                content: '';
                position: absolute;
                top: -50%;
                right: -50%;
                width: 200%;
                height: 200%;
                background: radial-gradient(circle, rgba(255,255,255,0.1) 1px, transparent 1px);
                background-size: 30px 30px;
                opacity: 0.1;
                transform: rotate(15deg);
            }

            .header-content {
                position: relative;
                z-index: 1;
            }

            .title-section {
                display: flex;
                align-items: center;
                justify-content: space-between;
                margin-bottom: 20px;
            }

            .title-section h1 {
                font-size: 28px;
                font-weight: 700;
                margin: 0;
            }

            .logo {
                font-size: 32px;
                color: white;
            }

            .subtitle {
                font-size: 16px;
                opacity: 0.9;
                margin-bottom: 25px;
                max-width: 600px;
            }

            /* Stats Cards */
            .stats-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 20px;
                margin: 30px 0;
            }

            .stat-card {
                background: rgba(255, 255, 255, 0.1);
                backdrop-filter: blur(10px);
                border-radius: 12px;
                padding: 20px;
                border: 1px solid rgba(255, 255, 255, 0.2);
                transition: transform 0.3s ease, box-shadow 0.3s ease;
            }

            .stat-card:hover {
                transform: translateY(-5px);
                box-shadow: 0 10px 30px rgba(0,0,0,0.2);
            }

            .stat-icon {
                font-size: 24px;
                margin-bottom: 10px;
                color: var(--secondary-color);
            }

            .stat-value {
                font-size: 32px;
                font-weight: 700;
                color: white;
                margin-bottom: 5px;
            }

            .stat-label {
                font-size: 14px;
                opacity: 0.8;
                text-transform: uppercase;
                letter-spacing: 1px;
            }

            /* Main Content */
            .content {
                padding: 40px;
            }

            .chart-container {
                background: white;
                border-radius: 15px;
                padding: 25px;
                box-shadow: 0 10px 30px rgba(0,0,0,0.08);
                margin-bottom: 30px;
                border: 1px solid var(--border-color);
            }

            #plotly-chart {
                width: 100%;
                height: 600px;
                min-height: 500px;
            }

            /* Info Panel */
            .info-panel {
                background: linear-gradient(135deg, #f0f9ff 0%, #e6f7ff 100%);
                border-radius: 15px;
                padding: 25px;
                border-left: 5px solid var(--primary-color);
                margin-top: 30px;
            }

            .info-panel h3 {
                color: var(--primary-color);
                margin-bottom: 15px;
                font-size: 18px;
            }

            .info-panel ul {
                list-style: none;
                padding-left: 20px;
            }

            .info-panel li {
                margin-bottom: 8px;
                position: relative;
                padding-left: 25px;
            }

            .info-panel li:before {
                content: '✓';
                position: absolute;
                left: 0;
                color: var(--success-color);
                font-weight: bold;
            }

            /* Server List */
            .server-list {
                max-height: 200px;
                overflow-y: auto;
                background: #f8fafc;
                border-radius: 10px;
                padding: 15px;
                margin-top: 15px;
                font-size: 13px;
            }

            .server-item {
                padding: 5px 10px;
                border-bottom: 1px solid #e2e8f0;
                display: flex;
                justify-content: space-between;
            }

            .server-item:last-child {
                border-bottom: none;
            }

            /* Controls */
            .controls {
                position: fixed;
                bottom: 30px;
                right: 30px;
                z-index: 1000;
                display: flex;
                gap: 10px;
                flex-direction: column;
            }

            .control-btn {
                background: linear-gradient(135deg, var(--primary-color) 0%, var(--primary-dark) 100%);
                color: white;
                border: none;
                width: 50px;
                height: 50px;
                border-radius: 50%;
                cursor: pointer;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 18px;
                box-shadow: 0 8px 25px rgba(79, 70, 229, 0.4);
                transition: all 0.3s ease;
            }

            .control-btn:hover {
                transform: scale(1.1) translateY(-3px);
                box-shadow: 0 12px 30px rgba(79, 70, 229, 0.6);
            }

            .control-btn:active {
                transform: scale(0.95);
            }

            /* Footer */
            .footer {
                background: var(--background-color);
                padding: 20px 40px;
                text-align: center;
                border-top: 1px solid var(--border-color);
                color: var(--text-secondary);
                font-size: 14px;
            }

            /* Responsive */
            @media (max-width: 768px) {
                .container {
                    padding: 10px;
                }

                .dashboard {
                    margin: 10px;
                }

                .header {
                    padding: 20px;
                }

                .title-section h1 {
                    font-size: 22px;
                }

                .content {
                    padding: 20px;
                }

                #plotly-chart {
                    height: 400px;
                }

                .stats-grid {
                    grid-template-columns: 1fr;
                }

                .controls {
                    bottom: 20px;
                    right: 20px;
                }

                .control-btn {
                    width: 45px;
                    height: 45px;
                    font-size: 16px;
                }
            }

            /* Animation */
            @keyframes fadeIn {
                from { opacity: 0; transform: translateY(20px); }
                to { opacity: 1; transform: translateY(0); }
            }

            .fade-in {
                animation: fadeIn 0.6s ease-out;
            }

            /* Loading */
            .loading {
                display: flex;
                justify-content: center;
                align-items: center;
                height: 200px;
                color: var(--text-secondary);
            }

            /* Tooltips */
            [data-tooltip] {
                position: relative;
                cursor: pointer;
            }

            [data-tooltip]:before {
                content: attr(data-tooltip);
                position: absolute;
                bottom: 100%;
                left: 50%;
                transform: translateX(-50%);
                background: rgba(0,0,0,0.8);
                color: white;
                padding: 8px 12px;
                border-radius: 6px;
                font-size: 12px;
                white-space: nowrap;
                opacity: 0;
                visibility: hidden;
                transition: opacity 0.3s, visibility 0.3s;
                z-index: 1000;
            }

            [data-tooltip]:hover:before {
                opacity: 1;
                visibility: visible;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="dashboard fade-in">
                <!-- Header -->
                <div class="header">
                    <div class="header-content">
                        <div class="title-section">
                            <h1><i class="fas fa-chart-line"></i> Анализ временных рядов</h1>
                            <div class="logo">
                                <i class="fas fa-server"></i>
                            </div>
                        </div>

                        <div class="subtitle">
                            Динамика {{metric_display}} за период {{date_range}}
                        </div>

                        <div class="stats-grid">
                            <div class="stat-card">
                                <div class="stat-icon">
                                    <i class="fas fa-server"></i>
                                </div>
                                <div class="stat-value">{{server_count}}</div>
                                <div class="stat-label">Серверов</div>
                            </div>

                            <div class="stat-card">
                                <div class="stat-icon">
                                    <i class="fas fa-microchip"></i>
                                </div>
                                <div class="stat-value">{{metric_display}}</div>
                                <div class="stat-label">Метрика</div>
                            </div>

                            <div class="stat-card">
                                <div class="stat-icon">
                                    <i class="fas fa-calendar-alt"></i>
                                </div>
                                <div class="stat-value">{{date_range}}</div>
                                <div class="stat-label">Период</div>
                            </div>

                            {% if stats.avg_load %}
                            <div class="stat-card">
                                <div class="stat-icon">
                                    <i class="fas fa-chart-bar"></i>
                                </div>
                                <div class="stat-value">{{stats.avg_load | round(1)}}%</div>
                                <div class="stat-label">Средняя нагрузка</div>
                            </div>
                            {% endif %}
                        </div>
                    </div>
                </div>

                <!-- Main Content -->
                <div class="content">
                    <!-- Chart -->
                    <div class="chart-container">
                        <h2><i class="fas fa-chart-area"></i> График временных рядов</h2>
                        <p class="text-secondary">Интерактивный график нагрузки серверов по времени</p>
                        <div id="plotly-chart"></div>
                    </div>
                </div>

                <!-- Footer -->
                <div class="footer">
                    <p>
                        <i class="fas fa-code"></i> Анализ временных рядов нагрузки серверов | 
                        <i class="fas fa-clock"></i> Сгенерировано {{current_time}} | 
                    </p>
                </div>
            </div>
        </div>

        <!-- Floating Controls -->
        <div class="controls">
            <button class="control-btn" onclick="toggleFullScreen()" data-tooltip="Полный экран">
                <i class="fas fa-expand"></i>
            </button>
            <button class="control-btn" onclick="downloadImage()" data-tooltip="Сохранить PNG">
                <i class="fas fa-download"></i>
            </button>
            <button class="control-btn" onclick="resetView()" data-tooltip="Сбросить вид">
                <i class="fas fa-redo"></i>
            </button>
            <button class="control-btn" onclick="toggleTheme()" data-tooltip="Переключить тему">
                <i class="fas fa-moon"></i>
            </button>
        </div>

        <script>
            // Вставляем plotly график
            const plotlyData = {{plotly_data | safe}};

            // Инициализация графика
            function initChart() {
                const chartDiv = document.getElementById('plotly-chart');

                // Конфиг для графика
                const layout = plotlyData.layout || {};
                const config = {
                    responsive: true,
                    displayModeBar: true,
                    displaylogo: false,
                    scrollZoom: true,
                    modeBarButtonsToAdd: [
                        'drawline',
                        'drawopenpath',
                        'drawclosedpath',
                        'drawcircle',
                        'drawrect',
                        'eraseshape',
                        'toImage'
                    ],
                    modeBarButtonsToRemove: ['lasso2d', 'select2d'],
                    toImageButtonOptions: {
                        format: 'png',
                        filename: 'timeseries_{{metric_name}}_' + new Date().toISOString().slice(0,10),
                        height: 1080,
                        width: 1920,
                        scale: 2
                    }
                };

                // Рендерим график
                Plotly.newPlot(chartDiv, plotlyData.data, layout, config);

                // Адаптация при изменении размера
                window.addEventListener('resize', function() {
                    Plotly.Plots.resize(chartDiv);
                });
            }

            // Функции управления
            function toggleFullScreen() {
                const elem = document.querySelector('.dashboard');
                if (!document.fullscreenElement) {
                    if (elem.requestFullscreen) {
                        elem.requestFullscreen();
                    } else if (elem.webkitRequestFullscreen) {
                        elem.webkitRequestFullscreen();
                    } else if (elem.msRequestFullscreen) {
                        elem.msRequestFullscreen();
                    }
                } else {
                    if (document.exitFullscreen) {
                        document.exitFullscreen();
                    } else if (document.webkitExitFullscreen) {
                        document.webkitExitFullscreen();
                    } else if (document.msExitFullscreen) {
                        document.msExitFullscreen();
                    }
                }
            }

            function downloadImage() {
                const chartDiv = document.getElementById('plotly-chart');
                Plotly.downloadImage(chartDiv, {
                    format: 'png',
                    width: 1920,
                    height: 1080,
                    filename: 'timeseries_{{metric_name}}_' + new Date().toISOString().slice(0,10)
                });
            }

            function resetView() {
                const chartDiv = document.getElementById('plotly-chart');
                Plotly.relayout(chartDiv, {
                    'xaxis.autorange': true,
                    'yaxis.autorange': true
                });
            }

            function toggleTheme() {
                const body = document.body;
                const currentBg = getComputedStyle(body).background;

                if (currentBg.includes('linear-gradient(135deg, #667eea')) {
                    // Темная тема
                    body.style.background = 'linear-gradient(135deg, #1a1a2e 0%, #16213e 100%)';
                    document.querySelector('.dashboard').style.background = '#0f172a';
                    document.querySelector('.dashboard').style.color = '#e2e8f0';
                } else {
                    // Светлая тема (возврат)
                    body.style.background = 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)';
                    document.querySelector('.dashboard').style.background = '#ffffff';
                    document.querySelector('.dashboard').style.color = '#1e293b';
                }
            }

            // Горячие клавиши
            document.addEventListener('keydown', function(e) {
                // F - полноэкранный режим
                if (e.key === 'f' || e.key === 'F') {
                    toggleFullScreen();
                    e.preventDefault();
                }
                // R - сброс вида
                if (e.key === 'r' || e.key === 'R') {
                    resetView();
                    e.preventDefault();
                }
                // S - сохранение (с Ctrl)
                if ((e.ctrlKey || e.metaKey) && e.key === 's') {
                    downloadImage();
                    e.preventDefault();
                }
                // T - переключение темы
                if (e.key === 't' || e.key === 'T') {
                    toggleTheme();
                    e.preventDefault();
                }
                // Esc - выход из полноэкранного режима
                if (e.key === 'Escape' && document.fullscreenElement) {
                    document.exitFullscreen();
                }
            });

            // Инициализация при загрузке
            document.addEventListener('DOMContentLoaded', function() {
                initChart();

                // Анимация появления
                const elements = document.querySelectorAll('.fade-in');
                elements.forEach((el, index) => {
                    el.style.animationDelay = (index * 0.1) + 's';
                });

                // Показываем подсказку при первом посещении
                setTimeout(() => {
                    if (!localStorage.getItem('timeseriesHintShown')) {
                        alert('💡 Подсказка: используйте клавиши F, R, S, T для быстрого управления графиком');
                        localStorage.setItem('timeseriesHintShown', 'true');
                    }
                }, 1000);
            });

            // Обработка выхода из полноэкранного режима
            document.addEventListener('fullscreenchange', function() {
                const chartDiv = document.getElementById('plotly-chart');
                setTimeout(() => {
                    Plotly.Plots.resize(chartDiv);
                }, 300);
            });
        </script>
    </body>
    </html>
    """

    # Подготавливаем данные для передачи в шаблон
    current_datetime = datetime.now()

    # Преобразуем plotly фигуру в JSON для передачи в шаблон
    plotly_json = fig_html.to_json()

    # Заполняем шаблон
    template = Template(html_template)
    final_html = template.render(
        plotly_data=plotly_json,  # Передаем JSON вместо HTML
        metric_name=metric_name,
        metric_display=metric_display,
        server_count=server_count,
        date_range=date_range,
        current_date=current_datetime.strftime("%d.%m.%Y"),
        current_time=current_datetime.strftime("%H:%M"),
        stats={
            'avg_load': stats_data.get('avg_load', 0),
            'max_load': stats_data.get('max_load', 0),
            'min_load': stats_data.get('min_load', 0),
            'top_server': stats_data.get('top_server', ''),
            'top_load': stats_data.get('top_load', 0),
            'server_list': stats_data.get('server_list', [])
        }
    )

    return final_html


def show():
    """Страница общего анализа"""
    st.markdown('<h2 class="sub-header">📈Общий анализ нагрузки серверов</h2>', unsafe_allow_html=True)

    try:
        # Загружаем данные для определения диапазона дат
        initial_df = load_data_from_db()

        if initial_df.empty:
            st.warning("⚠️ Данные не найдены в базе данных. Пожалуйста, убедитесь, что данные загружены.")
            st.info("💡 Используйте API или утилиты для загрузки данных в базу.")
            return

        # Выбор даты для анализа
        col_date1, col_date2 = st.columns([1, 3])

        with col_date1:
            st.markdown('<div class="server-selector fade-in">', unsafe_allow_html=True)

            # Преобразуем timestamp к datetime если это еще не сделано
            initial_df['timestamp'] = pd.to_datetime(initial_df['timestamp'])

            # Выбор диапазона дат
            min_date = initial_df['timestamp'].min().date()
            max_date = initial_df['timestamp'].max().date()

            st.markdown("### Выбор серверов для анализа")

            # Получаем список серверов
            servers = load_all_servers()

            if not servers:
                st.warning("Не удалось загрузить список серверов из базы данных.")
                return

            # Инициализируем session state для выбранных серверов
            if 'selected_servers' not in st.session_state:
                # По умолчанию выбираем первые 10 серверов или все, если их меньше
                default_servers = servers[:10] if len(servers) > 10 else servers
                st.session_state.selected_servers = default_servers

            # Фильтр по серверам с поиском
            filtered_servers = servers

            # Выбор серверов с чекбоксами
            selected_servers = st.multiselect(
                "**Серверы:**",
                filtered_servers,
                default=st.session_state.get('selected_servers', []),
                key="analysis_servers"
            )

            # Обновляем session state при изменении выбора
            st.session_state.selected_servers = selected_servers


            # Показываем статистику выбора
            total_servers = len(servers)
            selected_count = len(selected_servers)

            st.info(f"""
            **Статистика выбора:**
            - Всего серверов в базе: **{total_servers}**
            - Выбрано серверов: **{selected_count}** ({selected_count / total_servers * 100:.1f}%)
            - Не выбрано: **{total_servers - selected_count}**
            """)

            # Фильтр по типу сервера (если есть колонка server_type)
            if 'server_type' in initial_df.columns:
                server_types = initial_df['server_type'].dropna().unique().tolist()
                selected_types = st.multiselect(
                    "**Типы серверов:**",
                    ["Все"] + server_types,
                    default=["Все"],
                    key="analysis_server_types"
                )
            else:
                selected_types = ["Все"]

            col_start, col_end = st.columns(2)
            with col_start:
                start_date_input = st.date_input(
                    "**С:**",
                    min_date,
                    min_value=min_date,
                    max_value=max_date,
                    key="analysis_start_date"
                )
            with col_end:
                end_date_input = st.date_input(
                    "**По:**",
                    max_date,
                    min_value=min_date,
                    max_value=max_date,
                    key="analysis_end_date"
                )
            start_date = datetime.combine(start_date_input, datetime.min.time())
            end_date = datetime.combine(end_date_input, datetime.max.time())

            # Кнопка обновления
            refresh_btn = st.button(
                "🔄 Обновить данные",
                type="primary",
                use_container_width=True,
                key="refresh_analysis"
            )

            st.markdown('</div>', unsafe_allow_html=True)

        with col_date2:
            # Загружаем данные за выбранный период
            if refresh_btn:
                load_data_from_db.clear()
                st.rerun()

            analysis_df = load_data_from_db(start_date=start_date, end_date=end_date)

            if analysis_df.empty:
                st.warning(f"⚠️ Нет данных за выбранный период ({start_date.date()} - {end_date.date()})")
                return

            # Применение фильтров
            if selected_servers:
                analysis_df = analysis_df[analysis_df['server'].isin(selected_servers)].copy()
            else:
                # Если не выбраны серверы - показываем все
                st.info("📋 Серверы не выбраны. Отображаются все доступные серверы.")

            if "Все" not in selected_types and 'server_type' in analysis_df.columns:
                analysis_df = analysis_df[analysis_df['server_type'].isin(selected_types)].copy()

            if analysis_df.empty:
                st.warning("⚠️ Нет данных, соответствующих выбранным фильтрам")
                return

            st.divider()

            # График 2: Временные ряды по серверам
            st.markdown("### 📈 Временные ряды нагрузки")

            # Выбор метрики для отображения
            metric_options = []
            for metric in ['cpu.usage.average', 'mem.usage.average']:
                if metric in analysis_df.columns:
                    metric_options.append(metric)

            if metric_options:
                selected_metric = st.selectbox(
                    "**Выберите метрику для отображения:**",
                    metric_options,
                    index=0,
                    key="analysis_metric"
                )

                if selected_metric and selected_metric in analysis_df.columns:
                    # Ограничиваем количество серверов для читаемости
                    server_means = analysis_df.groupby('server')[selected_metric].mean()
                    if not server_means.empty:
                        top_servers = server_means.nlargest(15).index.tolist()
                        plot_df = analysis_df[analysis_df['server'].isin(top_servers)].copy()

                        fig_lines = go.Figure()

                        for server in plot_df['server'].unique():
                            server_data = plot_df[plot_df['server'] == server].sort_values('timestamp')
                            fig_lines.add_trace(go.Scatter(
                                x=pd.to_datetime(server_data['timestamp']),
                                y=server_data[selected_metric],
                                mode='lines',
                                name=server,
                                line=dict(width=2),
                                hovertemplate=f'<b>{server}</b><br>%{{x}}<br>Значение: %{{y:.1f}}%<extra></extra>'
                            ))

                        fig_lines.update_layout(
                            height=500,
                            xaxis_title="Время",
                            yaxis_title="Значение (%)",
                            title=f"Временные ряды {selected_metric}",
                            hovermode='x unified',
                            legend=dict(
                                yanchor="top",
                                y=0.99,
                                xanchor="left",
                                x=0.01
                            )
                        )
                        st.plotly_chart(fig_lines, use_container_width=True)

                        # ДОБАВЛЕННЫЙ БЛОК ЭКСПОРТА
                        st.markdown("---")
                        # Статистика по графикам
                        st.markdown("### 📈 Статистика")
                        col_stat1, col_stat2, col_stat3 = st.columns(3)
                        with col_stat1:
                            total_servers = len(plot_df['server'].unique())
                            st.metric("Количество серверов", f"{total_servers}")
                        with col_stat2:
                            avg_value = plot_df[selected_metric].mean()
                            st.metric("Среднее значение", f"{avg_value:.1f}%")
                        with col_stat3:
                            time_range = plot_df['timestamp'].max() - plot_df['timestamp'].min()
                            st.metric("Период данных", f"{time_range.days + 1} дней")

                        if st.button("🌐 Скачать HTML",
                                     type="primary",
                                     use_container_width=True,
                                     key="export_timeseries_html"):
                            with st.spinner("Создаем интерактивный HTML файл..."):
                                try:
                                    # Формируем строку с диапазоном дат
                                    date_range_str = f"{start_date.strftime('%d.%m.%Y')} - {end_date.strftime('%d.%m.%Y')}"
                                    # Создаем HTML
                                    html_content = create_timeseries_html(
                                        fig_lines,
                                        selected_metric,
                                        date_range_str,
                                        plot_df  # Передаем данные для статистики
                                    )
                                    # Генерируем имя файла
                                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                                    filename = f"timeseries_{selected_metric}_{timestamp}.html"
                                    # Предлагаем скачать
                                    st.download_button(
                                        label="⬇️ Нажмите для скачивания HTML",
                                        data=html_content,
                                        file_name=filename,
                                        mime="text/html",
                                        use_container_width=True,
                                        key="download_timeseries_html"
                                    )
                                    st.success(f"✅ HTML файл '{filename}' готов к скачиванию!")
                                except Exception as e:
                                    st.error(f"Ошибка при создании HTML: {str(e)}")
                                    st.info("Попробуйте обновить страницу и повторить попытку")

    except Exception as e:
        st.error(f"Ошибка при загрузке данных: {e}")
        import traceback
        with st.expander("Детали ошибки"):
            st.code(traceback.format_exc())
        st.info("💡 Убедитесь, что база данных доступна и содержит данные.")
