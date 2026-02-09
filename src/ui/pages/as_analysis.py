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
sys.path.append(parent_dir)

try:
    from components.heatmap_as_cpu import (
        create_as_cpu_heatmap,
        create_scrollable_html,
        create_separate_as_heatmaps as create_separate_as_cpu_heatmaps,
    )
    from components.heatmap_as_mem import (
        create_as_mem_heatmap,
        create_separate_as_heatmaps as create_separate_as_mem_heatmaps,
    )

    from utils.as_mapping import get_as_mapping
    from utils.data_loader import generate_server_data, load_data_from_database
except ImportError:
    # Fallback для прямого импорта
    import importlib.util

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

    # Проверяем наличие data_loader
    data_loader_path = os.path.join(parent_dir, 'utils', 'data_loader.py')
    if os.path.exists(data_loader_path):
        spec = importlib.util.spec_from_file_location("data_loader", data_loader_path)
        data_loader = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(data_loader)
        load_data_from_database = data_loader.load_data_from_database
        generate_server_data = data_loader.generate_server_data
    else:
        # Fallback на генерацию данных
        def generate_server_data():
            # Создаем тестовые данные
            dates = pd.date_range(start='2024-01-01', end='2024-01-07', freq='H')
            servers = [f"Server_{i}" for i in range(1, 21)]
            data = []
            for date in dates:
                for server in servers:
                    data.append({
                        'timestamp': date,
                        'server': server,
                        'cpu.usage.average': np.random.uniform(0, 100),
                        'mem.usage.average': np.random.uniform(0, 100),
                    })
            return pd.DataFrame(data)


        load_data_from_database = None


@st.cache_data(ttl=300)
def load_data_from_db(start_date: datetime = None, end_date: datetime = None):
    """Load data from database with optional date range"""
    if load_data_from_database is None:
        # Fallback to generate_server_data if database loader not available
        df = generate_server_data()
        if start_date or end_date:
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
            if start_date:
                df = df[df['timestamp'] >= pd.Timestamp(start_date)]
            if end_date:
                df = df[df['timestamp'] <= pd.Timestamp(end_date)]
        return df


@st.cache_data(ttl=3600)
def load_as_mapping_data():
    """Загружает данные о маппинге серверов на АС из Excel файла"""
    try:
        # Пытаемся загрузить из модуля
        mapping = get_as_mapping()
        if mapping:
            return mapping

        # Если модуль не вернул данные, загружаем из файла
        file_path = os.path.join(current_dir, 'all_vm.xlsx')
        if not os.path.exists(file_path):
            # Пробуем найти файл в других местах
            possible_paths = [
                os.path.join(os.path.dirname(__file__), '../../../', 'data', 'source', 'all_vm.xlsx'),
                os.path.join(parent_dir, 'data', 'source', 'all_vm.xlsx'),
                'all_vm.xlsx'
            ]

            for path in possible_paths:
                if os.path.exists(path):
                    file_path = path
                    break

        if os.path.exists(file_path):
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
            st.warning(f"Файл маппинга АС не найден по пути: {file_path}")
            return {}

    except Exception as e:
        st.error(f"Ошибка загрузки маппинга АС: {e}")
        return {}


@st.cache_data(ttl=3600)
def load_server_capacities():
    """Загружает данные о мощностях серверов из Excel файла"""
    try:
        file_path = os.path.join(current_dir, 'all_vm.xlsx')
        if not os.path.exists(file_path):
            # Пробуем найти файл в других местах
            possible_paths = [
                os.path.join(os.path.dirname(__file__), '../../../', 'data', 'source', 'all_vm.xlsx'),
                os.path.join(parent_dir, 'data', 'source', 'all_vm.xlsx'),
                'all_vm.xlsx'
            ]

            for path in possible_paths:
                if os.path.exists(path):
                    file_path = path
                    break

        if os.path.exists(file_path):
            df = pd.read_excel(file_path)

            # Создаем словарь мощностей: server_name -> {'cpu': x, 'ram': y}
            capacities = {}
            for _, row in df.iterrows():
                server_name = str(row.get('Имя КЕ', '')).strip()
                cpu_count = float(row.get('Discovery_CPU Count', 0)) if pd.notna(row.get('Discovery_CPU Count')) else 0
                mem_count = float(row.get('Discovery_RAM (Gb)', 0)) if pd.notna(row.get('Discovery_RAM (Gb)')) else 0

                if server_name:
                    # Нормализуем имена серверов для лучшего сопоставления
                    server_normalized = server_name.lower().replace('_', '-').replace(' ', '-')

                    # Сохраняем обе мощности
                    capacities[server_normalized] = {
                        'cpu': cpu_count,
                        'ram': mem_count,
                        'original_name': server_name  # сохраняем оригинальное имя для удобства
                    }

                    # Также добавляем запись с оригинальным именем (без нормализации)
                    capacities[server_name] = {
                        'cpu': cpu_count,
                        'ram': mem_count,
                        'original_name': server_name
                    }

            return capacities
        else:
            st.warning(f"Файл мощностей серверов не найден по пути: {file_path}")
            return {}

    except Exception as e:
        st.error(f"Ошибка при загрузке мощностей серверов: {e}")
        return {}


@st.cache_data(ttl=300)
def prepare_as_analysis_data(analysis_df, as_mapping, server_capacities):
    """Подготавливает данные для анализа по АС"""
    if analysis_df.empty:
        return pd.DataFrame(), {}, {}

    # Создаем копию данных
    df = analysis_df.copy()

    # Нормализуем имена серверов для сопоставления
    df['server_normalized'] = df['server'].astype(str).str.lower().str.strip()
    df['server_normalized'] = df['server_normalized'].str.replace('_', '-').str.replace(' ', '-')

    # Сопоставляем серверы с АС
    df['as_name'] = df['server_normalized'].map(as_mapping)

    # Для серверов без маппинга используем имя сервера как АС
    missing_as_mask = df['as_name'].isna() | (df['as_name'] == '')
    df.loc[missing_as_mask, 'as_name'] = df.loc[missing_as_mask, 'server']

    # Добавляем мощности серверов
    df['server_capacity_cpu'] = df['server_normalized'].apply(
        lambda x: server_capacities.get(x, {}).get('cpu', 0)
        if isinstance(server_capacities.get(x), dict)
        else (server_capacities.get(x, 0) if isinstance(server_capacities.get(x), (int, float)) else 0)
    )

    df['server_capacity_ram'] = df['server_normalized'].apply(
        lambda x: server_capacities.get(x, {}).get('ram', 0)
        if isinstance(server_capacities.get(x), dict)
        else 0
    )

    # Также проверяем оригинальные имена серверов для мощности
    for idx, row in df.iterrows():
        if df.at[idx, 'server_capacity_cpu'] == 0:
            # Пробуем найти по оригинальному имени
            original_name = row['server']
            cpu_capacity = server_capacities.get(original_name, {}).get('cpu', 0) if isinstance(
                server_capacities.get(original_name), dict) else 0
            ram_capacity = server_capacities.get(original_name, {}).get('ram', 0) if isinstance(
                server_capacities.get(original_name), dict) else 0

            if cpu_capacity > 0:
                df.at[idx, 'server_capacity_cpu'] = cpu_capacity
                df.at[idx, 'server_capacity_ram'] = ram_capacity

    # Для серверов без данных о мощности используем значения по умолчанию
    default_cpu = 2.0  # 2 CPU ядра
    default_ram = 8.0  # 8 GB RAM

    df['server_capacity_cpu'] = df['server_capacity_cpu'].replace(0, default_cpu)
    df['server_capacity_ram'] = df['server_capacity_ram'].replace(0, default_ram)

    # Создаем сводную статистику по АС
    as_stats = {}
    server_to_as = {}

    # Группируем по АС и собираем статистику
    for as_name, group in df.groupby('as_name'):
        servers = group['server'].unique().tolist()

        # CPU статистика
        avg_cpu_load = group['cpu.usage.average'].mean() if 'cpu.usage.average' in group.columns else 0
        max_cpu_load = group['cpu.usage.average'].max() if 'cpu.usage.average' in group.columns else 0

        # RAM статистика (если есть данные об использовании RAM)
        avg_ram_load = group['mem.usage.average'].mean() if 'mem.usage.average' in group.columns else 0
        max_ram_load = group['mem.usage.average'].max() if 'mem.usage.average' in group.columns else 0

        # Суммарные мощности
        total_cpu_capacity = group['server_capacity_cpu'].sum()
        total_ram_capacity = group['server_capacity_ram'].sum()

        # Средние мощности
        avg_cpu_capacity = total_cpu_capacity / len(servers) if servers else 0
        avg_ram_capacity = total_ram_capacity / len(servers) if servers else 0

        # Расчет загруженности
        cpu_utilization = (avg_cpu_load / 100) * avg_cpu_capacity if avg_cpu_capacity > 0 else 0
        ram_utilization = (avg_ram_load / 100) * avg_ram_capacity if avg_ram_capacity > 0 else 0

        as_stats[as_name] = {
            'servers': servers,
            'server_count': len(servers),

            # CPU метрики
            'avg_cpu_load': avg_cpu_load,
            'max_cpu_load': max_cpu_load,
            'total_cpu_capacity': total_cpu_capacity,
            'avg_cpu_capacity': avg_cpu_capacity,
            'cpu_utilization': cpu_utilization,

            # RAM метрики
            'avg_ram_load': avg_ram_load,
            'max_ram_load': max_ram_load,
            'total_ram_capacity': total_ram_capacity,
            'avg_ram_capacity': avg_ram_capacity,
            'ram_utilization': ram_utilization,

            # Общие метрики
            'total_records': len(group),

            # Комбинированная загруженность (можно настроить веса)
            'overall_load': (avg_cpu_load * 0.7 + avg_ram_load * 0.3)  # 70% CPU, 30% RAM
        }

        # Сопоставление сервер -> АС
        for server in servers:
            server_to_as[server] = as_name

    return df, as_stats, server_to_as


# def create_memory_heatmap_html(fig_heatmap_mem, y_labels, x_labels, values_matrix, pivot_df,
#                                server_cpu_capacity_map, server_ram_capacity_map,
#                                start_date, end_date, selected_count, total_servers,
#                                total_cpu_capacity, total_ram_capacity, sort_by, sort_order, filter_text):
#     """Создает HTML файл с тепловой картой памяти"""
#
#     # Конвертируем фигуру в HTML
#     plotly_html = pio.to_html(
#         fig_heatmap_mem,
#         full_html=False,
#         include_plotlyjs='cdn',
#         config={
#             'responsive': True,
#             'displayModeBar': True,
#             'displaylogo': False,
#             'scrollZoom': True,
#             'modeBarButtonsToAdd': ['drawline', 'drawopenpath', 'drawclosedpath',
#                                     'drawcircle', 'drawrect', 'eraseshape', 'toImage']
#         }
#     )
#
#     # Красивый HTML шаблон для памяти
#     html_template = """
#     <!DOCTYPE html>
#     <html lang="ru">
#     <head>
#         <meta charset="UTF-8">
#         <meta name="viewport" content="width=device-width, initial-scale=1.0">
#         <title>Тепловая карта нагрузки памяти по АС</title>
#         <script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
#         <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
#         <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
#         <style>
#             :root {
#                 --primary-color: #4f46e5;
#                 --primary-dark: #3730a3;
#                 --secondary-color: #10b981;
#                 --background-color: #f8fafc;
#                 --card-bg: #ffffff;
#                 --text-primary: #1e293b;
#                 --text-secondary: #64748b;
#                 --border-color: #e2e8f0;
#             }
#
#             * {
#                 margin: 0;
#                 padding: 0;
#                 box-sizing: border-box;
#             }
#
#             body {
#                 font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
#                 background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
#                 min-height: 100vh;
#                 color: var(--text-primary);
#                 line-height: 1.6;
#             }
#
#             .container {
#                 max-width: 1800px;
#                 margin: 0 auto;
#                 padding: 20px;
#             }
#
#             .dashboard {
#                 background: var(--card-bg);
#                 border-radius: 20px;
#                 box-shadow: 0 20px 60px rgba(0,0,0,0.15);
#                 overflow: hidden;
#                 margin: 20px;
#             }
#
#             .header {
#                 background: linear-gradient(135deg, var(--primary-color) 0%, var(--primary-dark) 100%);
#                 color: white;
#                 padding: 30px 40px;
#                 position: relative;
#                 overflow: hidden;
#             }
#
#             .header::before {
#                 content: '';
#                 position: absolute;
#                 top: -50%;
#                 right: -50%;
#                 width: 200%;
#                 height: 200%;
#                 background: radial-gradient(circle, rgba(255,255,255,0.1) 1px, transparent 1px);
#                 background-size: 30px 30px;
#                 opacity: 0.1;
#                 transform: rotate(15deg);
#             }
#
#             .header-content {
#                 position: relative;
#                 z-index: 1;
#             }
#
#             .title-section {
#                 display: flex;
#                 align-items: center;
#                 justify-content: space-between;
#                 margin-bottom: 20px;
#             }
#
#             .title-section h1 {
#                 font-size: 28px;
#                 font-weight: 700;
#                 margin: 0;
#             }
#
#             .logo {
#                 font-size: 32px;
#                 color: white;
#             }
#
#             .subtitle {
#                 font-size: 16px;
#                 opacity: 0.9;
#                 margin-bottom: 25px;
#                 max-width: 600px;
#             }
#
#             .stats-grid {
#                 display: grid;
#                 grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
#                 gap: 20px;
#                 margin: 30px 0;
#             }
#
#             .stat-card {
#                 background: rgba(255, 255, 255, 0.1);
#                 backdrop-filter: blur(10px);
#                 border-radius: 12px;
#                 padding: 20px;
#                 border: 1px solid rgba(255, 255, 255, 0.2);
#                 transition: transform 0.3s ease, box-shadow 0.3s ease;
#             }
#
#             .stat-card:hover {
#                 transform: translateY(-5px);
#                 box-shadow: 0 10px 30px rgba(0,0,0,0.2);
#             }
#
#             .stat-icon {
#                 font-size: 24px;
#                 margin-bottom: 10px;
#                 color: var(--secondary-color);
#             }
#
#             .stat-value {
#                 font-size: 32px;
#                 font-weight: 700;
#                 color: white;
#                 margin-bottom: 5px;
#             }
#
#             .stat-label {
#                 font-size: 14px;
#                 opacity: 0.8;
#                 text-transform: uppercase;
#                 letter-spacing: 1px;
#             }
#
#             .content {
#                 padding: 40px;
#             }
#
#             .chart-container {
#                 background: white;
#                 border-radius: 15px;
#                 padding: 25px;
#                 box-shadow: 0 10px 30px rgba(0,0,0,0.08);
#                 margin-bottom: 30px;
#                 border: 1px solid var(--border-color);
#             }
#
#             #plotly-chart {
#                 width: 100%;
#                 height: 800px;
#                 min-height: 600px;
#             }
#
#             .info-panel {
#                 background: linear-gradient(135deg, #f0f9ff 0%, #e6f7ff 100%);
#                 border-radius: 15px;
#                 padding: 25px;
#                 border-left: 5px solid var(--primary-color);
#                 margin-top: 30px;
#             }
#
#             .info-panel h3 {
#                 color: var(--primary-color);
#                 margin-bottom: 15px;
#                 font-size: 18px;
#             }
#
#             .info-panel ul {
#                 list-style: none;
#                 padding-left: 20px;
#             }
#
#             .info-panel li {
#                 margin-bottom: 8px;
#                 position: relative;
#                 padding-left: 25px;
#             }
#
#             .info-panel li:before {
#                 content: '✓';
#                 position: absolute;
#                 left: 0;
#                 color: var(--secondary-color);
#                 font-weight: bold;
#             }
#
#             .footer {
#                 background: var(--background-color);
#                 padding: 20px 40px;
#                 text-align: center;
#                 border-top: 1px solid var(--border-color);
#                 color: var(--text-secondary);
#                 font-size: 14px;
#             }
#
#             .legend-scale {
#                 display: flex;
#                 align-items: center;
#                 justify-content: space-between;
#                 margin-top: 20px;
#                 padding: 10px;
#                 background: #f8fafc;
#                 border-radius: 8px;
#                 border: 1px solid #e2e8f0;
#             }
#
#             .scale-item {
#                 display: flex;
#                 align-items: center;
#                 gap: 10px;
#             }
#
#             .scale-color {
#                 width: 20px;
#                 height: 20px;
#                 border-radius: 4px;
#             }
#
#             .scale-label {
#                 font-size: 12px;
#                 color: #64748b;
#             }
#
#             @media (max-width: 768px) {
#                 .container {
#                     padding: 10px;
#                 }
#
#                 .dashboard {
#                     margin: 10px;
#                 }
#
#                 .header {
#                     padding: 20px;
#                 }
#
#                 .title-section h1 {
#                     font-size: 22px;
#                 }
#
#                 .content {
#                     padding: 20px;
#                 }
#
#                 #plotly-chart {
#                     height: 600px;
#                 }
#
#                 .stats-grid {
#                     grid-template-columns: 1fr;
#                 }
#             }
#         </style>
#     </head>
#     <body>
#         <div class="container">
#             <div class="dashboard">
#                 <!-- Header -->
#                 <div class="header">
#                     <div class="header-content">
#                         <div class="title-section">
#                             <h1><i class="fas fa-fire"></i> Тепловая карта нагрузки памяти</h1>
#                             <div class="logo">
#                                 <i class="fas fa-server"></i>
#                             </div>
#                         </div>
#
#                         <div class="subtitle">
#                             Анализ нагрузки памяти по серверам в разрезе автоматизированных систем за период {{date_range}}
#                         </div>
#
#                         <div class="stats-grid">
#                             <div class="stat-card">
#                                 <div class="stat-icon">
#                                     <i class="fas fa-sitemap"></i>
#                                 </div>
#                                 <div class="stat-value">{{selected_count}}</div>
#                                 <div class="stat-label">Автоматизированных систем</div>
#                             </div>
#
#                             <div class="stat-card">
#                                 <div class="stat-icon">
#                                     <i class="fas fa-server"></i>
#                                 </div>
#                                 <div class="stat-value">{{total_servers}}</div>
#                                 <div class="stat-label">Серверов</div>
#                             </div>
#
#                             <div class="stat-card">
#                                 <div class="stat-icon">
#                                     <i class="fas fa-microchip"></i>
#                                 </div>
#                                 <div class="stat-value">{{total_cpu_capacity}}</div>
#                                 <div class="stat-label">Ядер CPU</div>
#                             </div>
#
#                             <div class="stat-card">
#                                 <div class="stat-icon">
#                                     <i class="fas fa-memory"></i>
#                                 </div>
#                                 <div class="stat-value">{{total_ram_capacity}} GB</div>
#                                 <div class="stat-label">Мощность RAM</div>
#                             </div>
#                         </div>
#                     </div>
#                 </div>
#
#                 <!-- Main Content -->
#                 <div class="content">
#                     <!-- Chart -->
#                     <div class="chart-container">
#                         <h2><i class="fas fa-chart-heatmap"></i> Тепловая карта нагрузки памяти</h2>
#                         <div class="legend-scale">
#                             <div class="scale-item">
#                                 <div class="scale-color" style="background: #00FF00;"></div>
#                                 <div class="scale-label">0-30% (Низкая)</div>
#                             </div>
#                             <div class="scale-item">
#                                 <div class="scale-color" style="background: #90EE90;"></div>
#                                 <div class="scale-label">30-50% (Средняя)</div>
#                             </div>
#                             <div class="scale-item">
#                                 <div class="scale-color" style="background: #FFFF00;"></div>
#                                 <div class="scale-label">50-70% (Высокая)</div>
#                             </div>
#                             <div class="scale-item">
#                                 <div class="scale-color" style="background: #FFA500;"></div>
#                                 <div class="scale-label">70-85% (Критическая)</div>
#                             </div>
#                             <div class="scale-item">
#                                 <div class="scale-color" style="background: #FF0000;"></div>
#                                 <div class="scale-label">85-100% (Аварийная)</div>
#                             </div>
#                         </div>
#                         <div id="plotly-chart"></div>
#                     </div>
#                 </div>
#
#                 <!-- Footer -->
#                 <div class="footer">
#                     <p>
#                         <i class="fas fa-code"></i> Анализ нагрузки памяти по АС |
#                         <i class="fas fa-clock"></i> Сгенерировано {{current_time}} |
#                     </p>
#                 </div>
#             </div>
#         </div>
#
#         <script>
#             // Вставляем plotly график
#             const plotlyData = {{plotly_data | safe}};
#
#             // Инициализация графика
#             function initChart() {
#                 const chartDiv = document.getElementById('plotly-chart');
#
#                 // Конфиг для графика
#                 const layout = plotlyData.layout || {};
#                 const config = {
#                     responsive: true,
#                     displayModeBar: true,
#                     displaylogo: false,
#                     scrollZoom: true,
#                     modeBarButtonsToAdd: [
#                         'drawline',
#                         'drawopenpath',
#                         'drawclosedpath',
#                         'drawcircle',
#                         'drawrect',
#                         'eraseshape',
#                         'toImage'
#                     ],
#                     modeBarButtonsToRemove: ['lasso2d', 'select2d'],
#                     toImageButtonOptions: {
#                         format: 'png',
#                         filename: 'memory_heatmap_{{timestamp}}',
#                         height: 1080,
#                         width: 1920,
#                         scale: 2
#                     }
#                 };
#
#                 // Рендерим график
#                 Plotly.newPlot(chartDiv, plotlyData.data, layout, config);
#
#                 // Адаптация при изменении размера
#                 window.addEventListener('resize', function() {
#                     Plotly.Plots.resize(chartDiv);
#                 });
#             }
#
#             // Функции управления
#             function toggleFullScreen() {
#                 const elem = document.querySelector('.dashboard');
#                 if (!document.fullscreenElement) {
#                     if (elem.requestFullscreen) {
#                         elem.requestFullscreen();
#                     } else if (elem.webkitRequestFullscreen) {
#                         elem.webkitRequestFullscreen();
#                     } else if (elem.msRequestFullscreen) {
#                         elem.msRequestFullscreen();
#                     }
#                 } else {
#                     if (document.exitFullscreen) {
#                         document.exitFullscreen();
#                     } else if (document.webkitExitFullscreen) {
#                         document.webkitExitFullscreen();
#                     } else if (document.msExitFullscreen) {
#                         document.msExitFullscreen();
#                     }
#                 }
#             }
#
#             function downloadImage() {
#                 const chartDiv = document.getElementById('plotly-chart');
#                 Plotly.downloadImage(chartDiv, {
#                     format: 'png',
#                     width: 1920,
#                     height: 1080,
#                     filename: 'memory_heatmap_{{timestamp}}'
#                 });
#             }
#
#             // Инициализация при загрузке
#             document.addEventListener('DOMContentLoaded', function() {
#                 initChart();
#             });
#
#             // Горячие клавиши
#             document.addEventListener('keydown', function(e) {
#                 // F - полноэкранный режим
#                 if (e.key === 'f' || e.key === 'F') {
#                     toggleFullScreen();
#                     e.preventDefault();
#                 }
#                 // S - сохранение (с Ctrl)
#                 if ((e.ctrlKey || e.metaKey) && e.key === 's') {
#                     downloadImage();
#                     e.preventDefault();
#                 }
#                 // Esc - выход из полноэкранного режима
#                 if (e.key === 'Escape' && document.fullscreenElement) {
#                     document.exitFullscreen();
#                 }
#             });
#         </script>
#     </body>
#     </html>
#     """
#
#     # Подготавливаем данные для передачи в шаблон
#     current_datetime = datetime.now()
#     timestamp = current_datetime.strftime("%Y%m%d_%H%M%S")
#
#     # Формируем диапазон дат
#     date_range = f"{start_date.strftime('%d.%m.%Y')} - {end_date.strftime('%d.%m.%Y')}"
#
#     # Преобразуем plotly фигуру в JSON для передачи в шаблон
#     plotly_json = fig_heatmap_mem.to_json()
#
#     # Заполняем шаблон
#     template = Template(html_template)
#     final_html = template.render(
#         plotly_data=plotly_json,
#         date_range=date_range,
#         selected_count=selected_count,
#         total_servers=total_servers,
#         total_cpu_capacity=f"{total_cpu_capacity:.0f}",
#         total_ram_capacity=f"{total_ram_capacity:.0f}",
#         sort_by=sort_by,
#         sort_order=sort_order,
#         filter_text=filter_text,
#         current_date=current_datetime.strftime("%d.%m.%Y"),
#         current_time=current_datetime.strftime("%H:%M"),
#         timestamp=timestamp
#     )
#
#     return final_html


def create_memory_heatmap_html(fig_heatmap_mem, y_labels, x_labels, values_matrix, pivot_df,
                               server_cpu_capacity_map, server_ram_capacity_map,
                               start_date, end_date, selected_count, total_servers,
                               total_cpu_capacity, total_ram_capacity, sort_by, sort_order, filter_text):
    """Создает HTML файл с тепловой картой памяти, группируя серверы по АС"""

    # Группируем данные по АС
    as_groups = {}
    for i, (_, row) in enumerate(pivot_df.iterrows()):
        as_name = row['as_name']
        server = row['server']

        if as_name not in as_groups:
            as_groups[as_name] = {
                'indices': [],
                'servers': [],
                'cpu_capacities': [],
                'ram_capacities': [],
                'rows': []
            }

        as_groups[as_name]['indices'].append(i)
        as_groups[as_name]['servers'].append(server)
        as_groups[as_name]['cpu_capacities'].append(server_cpu_capacity_map.get(server, 0))
        as_groups[as_name]['ram_capacities'].append(server_ram_capacity_map.get(server, 0))
        as_groups[as_name]['rows'].append(row)

    # Создаем HTML с отдельными тепловыми картами для каждой АС
    all_html_content = ""

    for as_name, as_data in as_groups.items():
        # Создаем фигуру для текущей АС
        fig_as = go.Figure()

        # Получаем данные только для текущей АС
        as_indices = as_data['indices']
        as_y_labels = [y_labels[i] for i in as_indices]
        as_values = values_matrix[as_indices, :]

        # Подготовка hover данных для текущей АС
        hover_texts = []
        for i, idx in enumerate(as_indices):
            row = as_data['rows'][i]
            server = as_data['servers'][i]
            cpu_capacity = as_data['cpu_capacities'][i]
            ram_capacity = as_data['ram_capacities'][i]
            row_hover = []

            for j, interval in enumerate(range(48)):
                load_value = as_values[i, j]
                hour = interval // 2
                minute = (interval % 2) * 30
                time_str = f"{hour:02d}:{minute:02d}"

                if load_value <= 0:
                    text = (f"<b>{as_name} | {server}</b><br>"
                            f"CPU: {cpu_capacity:.0f} ядер | RAM: {ram_capacity:.0f} GB<br>"
                            f"Время: {time_str}<br>Нет данных")
                else:
                    # Цветовая категоризация нагрузки RAM
                    if load_value < 30:
                        load_status = "🟢 Низкая"
                    elif load_value < 50:
                        load_status = "🟡 Средняя"
                    elif load_value < 70:
                        load_status = "🟠 Высокая"
                    elif load_value < 85:
                        load_status = "🔴 Критическая"
                    else:
                        load_status = "🛑 Аварийная"

                    text = (f"<b>{as_name} | {server}</b><br>"
                            f"CPU: {cpu_capacity:.0f} ядер | RAM: {ram_capacity:.0f} GB<br>"
                            f"🕐 {time_str}<br>"
                            f"📊 Нагрузка RAM: <b>{load_value:.1f}%</b><br>"
                            f"🏷️ {load_status}")

                row_hover.append(text)
            hover_texts.append(row_hover)

        # Добавляем тепловую карту для текущей АС
        fig_as.add_trace(go.Heatmap(
            z=as_values,
            x=x_labels,
            y=as_y_labels,
            colorscale=[
                [0.0, "#00FF00"],   # Ярко-зеленый (0%)
                [0.3, "#90EE90"],   # Светло-зеленый (30%)
                [0.5, "#FFFF00"],   # Желтый (50%)
                [0.7, "#FFA500"],   # Оранжевый (70%)
                [1.0, "#FF0000"]    # Красный (100%)
            ],
            text=as_values.round(1),
            texttemplate='%{text}%',
            textfont={"size": 8, "color": "black"},
            colorbar=dict(
                title="Нагрузка RAM (%)",
                titleside="right",
                tickvals=[0, 25, 50, 75, 100],
                ticktext=["0%", "25%", "50%", "75%", "100%"],
                len=0.9
            ),
            hoverinfo='text',
            hovertext=hover_texts,
            hovertemplate="%{hovertext}<extra></extra>",
            zmin=0,
            zmax=100,
            showscale=True,
            xgap=0.5,
            ygap=0.5
        ))

        # Рассчитываем высоту графика на основе количества серверов в АС
        as_chart_height = max(400, len(as_y_labels) * 30)

        # Общая статистика для АС
        as_servers_count = len(as_y_labels)
        as_total_cpu = sum(as_data['cpu_capacities'])
        as_total_ram = sum(as_data['ram_capacities'])
        as_avg_ram = as_total_ram / as_servers_count if as_servers_count > 0 else 0

        # Настраиваем лейаут для текущей АС
        fig_as.update_layout(
            height=as_chart_height,
            title=dict(
                text=f"АС: {as_name}<br>Серверов: {as_servers_count} | CPU: {as_total_cpu:.0f} ядер | RAM: {as_total_ram:.0f} GB",
                font=dict(size=16),
                x=0.5,
                xanchor='center'
            ),
            xaxis=dict(
                title="Время суток (интервалы по 30 минут)",
                tickmode='array',
                tickvals=list(range(0, 48, 4)),
                ticktext=[x_labels[i] for i in range(0, 48, 4)],
                tickangle=45,
                tickfont=dict(size=9),
                gridcolor='rgba(128, 128, 128, 0.2)',
                showgrid=True,
                fixedrange=True
            ),
            yaxis=dict(
                title="Сервер (CPU ядра | RAM GB)",
                tickfont=dict(size=8),
                automargin=True
            ),
            margin=dict(l=150, r=50, t=80, b=80),
            plot_bgcolor='white',
            paper_bgcolor='white'
        )

        # Добавляем линии для часов
        for hour in range(0, 48, 2):
            fig_as.add_vline(
                x=hour - 0.5,
                line_dash="dot",
                line_color="rgba(128, 128, 128, 0.3)",
                line_width=1
            )

        # Конвертируем фигуру для текущей АС в HTML
        as_html_content = pio.to_html(
            fig_as,
            full_html=False,
            include_plotlyjs='cdn',
            config={
                'responsive': True,
                'displayModeBar': True,
                'displaylogo': False,
                'modeBarButtonsToAdd': ['toImage', 'resetScale2d'],
                'scrollZoom': True,
                'showTips': True
            }
        )

        # Добавляем HTML текущей АС к общему контенту
        all_html_content += f"""
        <div class="as-section">
            <div class="as-header">
                <h2>🏢 АС: {as_name}</h2>
                <div class="as-stats">
                    <span>📊 Серверов: {as_servers_count}</span>
                    <span>⚡ CPU: {as_total_cpu:.0f} ядер</span>
                    <span>💾 RAM: {as_total_ram:.0f} GB</span>
                </div>
            </div>
            <div class="chart-container as-chart">
                {as_html_content}
            </div>
        </div>
        <hr class="as-divider">
        """

    # Создаем HTML с прокруткой и фильтрацией
    scrollable_html_template = """
    <!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Тепловые карты нагрузки памяти по АС</title>
    <script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: #f5f7fa;
            color: #333;
            line-height: 1.6;
        }

        .container {
            max-width: 1400px;
            margin: 0 auto;
            padding: 20px;
        }

        .header {
            background: white;
            border-radius: 10px;
            padding: 25px;
            margin-bottom: 20px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            text-align: center;
        }

        .header h1 {
            color: #8e44ad;
            font-size: 24px;
            margin-bottom: 10px;
        }

        .subtitle {
            color: #666;
            font-size: 16px;
            margin-bottom: 20px;
        }

        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-top: 20px;
        }

        .stat-card {
            background: linear-gradient(135deg, #8e44ad 0%, #6c3483 100%);
            color: white;
            padding: 15px;
            border-radius: 8px;
            text-align: center;
        }

        .stat-card.cpu {
            background: linear-gradient(135deg, #3498db 0%, #2980b9 100%);
        }

        .stat-card.ram {
            background: linear-gradient(135deg, #9b59b6 0%, #8e44ad 100%);
        }

        .stat-value {
            font-size: 28px;
            font-weight: bold;
            margin-bottom: 5px;
        }

        .stat-label {
            font-size: 14px;
            opacity: 0.9;
        }

        /* Секции АС */
        .as-section {
            background: white;
            border-radius: 10px;
            padding: 20px;
            margin-bottom: 20px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }

        .as-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
            padding-bottom: 15px;
            border-bottom: 2px solid #e0e0e0;
        }

        .as-header h2 {
            color: #8e44ad;
            font-size: 20px;
            margin: 0;
        }

        .as-stats {
            display: flex;
            gap: 20px;
            font-size: 14px;
            color: #666;
        }

        .as-stats span {
            display: flex;
            align-items: center;
            gap: 5px;
            padding: 5px 10px;
            background: #f8f9fa;
            border-radius: 6px;
            border: 1px solid #e0e0e0;
        }

        .as-divider {
            border: none;
            border-top: 3px solid #8e44ad;
            margin: 30px 0;
            opacity: 0.3;
        }

        /* Контент */
        .content {
            background: white;
            border-radius: 10px;
            padding: 20px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            margin-bottom: 20px;
        }

        .chart-container {
            width: 100%;
            overflow-x: auto;
            overflow-y: visible;
            border: 1px solid #e0e0e0;
            border-radius: 8px;
            padding: 15px;
            background: white;
        }

        .as-chart {
            margin-top: 15px;
        }

        .legend {
            background: #f8f9fa;
            border-radius: 8px;
            padding: 15px;
            margin-top: 20px;
            border-left: 4px solid #8e44ad;
        }

        .legend h3 {
            color: #8e44ad;
            margin-bottom: 10px;
            font-size: 16px;
        }

        .legend-items {
            display: flex;
            flex-wrap: wrap;
            gap: 15px;
        }

        .legend-item {
            display: flex;
            align-items: center;
            font-size: 14px;
        }

        .legend-color {
            width: 20px;
            height: 20px;
            border-radius: 4px;
            margin-right: 8px;
        }

        .footer {
            text-align: center;
            color: #666;
            font-size: 14px;
            padding: 20px;
            background: white;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }

        .footer-info {
            display: flex;
            justify-content: center;
            gap: 20px;
            flex-wrap: wrap;
            margin-bottom: 10px;
        }

        .controls {
            position: fixed;
            bottom: 20px;
            right: 20px;
            z-index: 100;
            display: flex;
            flex-direction: column;
            gap: 10px;
        }

        .btn {
            background: #8e44ad;
            color: white;
            border: none;
            padding: 12px 20px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 14px;
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 8px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            transition: all 0.3s ease;
        }

        .btn:hover {
            background: #6c3483;
            transform: translateY(-2px);
            box-shadow: 0 6px 8px rgba(0,0,0,0.15);
        }

        .btn-download {
            background: #3498db;
        }

        .btn-download:hover {
            background: #2980b9;
        }

        .scroll-hint {
            position: fixed;
            bottom: 20px;
            left: 50%;
            transform: translateX(-50%);
            background: rgba(0,0,0,0.8);
            color: white;
            padding: 10px 20px;
            border-radius: 20px;
            font-size: 14px;
            animation: fadeInOut 3s ease-in-out;
            z-index: 100;
        }

        @keyframes fadeInOut {
            0%, 100% { opacity: 0; }
            10%, 90% { opacity: 1; }
        }

        .loading {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(255,255,255,0.9);
            justify-content: center;
            align-items: center;
            z-index: 9999;
            flex-direction: column;
        }

        .loading.show {
            display: flex;
        }

        .spinner {
            width: 40px;
            height: 40px;
            border: 4px solid #f3f3f3;
            border-top: 4px solid #8e44ad;
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin-bottom: 15px;
        }

        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }

        /* Быстрые кнопки */
        .quick-actions {
            display: flex;
            gap: 10px;
            justify-content: center;
            margin-top: 15px;
            flex-wrap: wrap;
        }

        .quick-btn {
            padding: 8px 15px;
            border: 2px solid #8e44ad;
            background: white;
            color: #8e44ad;
            border-radius: 6px;
            cursor: pointer;
            font-size: 14px;
            font-weight: 600;
            transition: all 0.3s ease;
        }

        .quick-btn:hover {
            background: #8e44ad;
            color: white;
        }

        .quick-btn.download {
            border-color: #3498db;
            color: #3498db;
        }

        .quick-btn.download:hover {
            background: #3498db;
            color: white;
        }

        /* Навигация по АС */
        .as-navigation {
            position: fixed;
            left: 20px;
            top: 50%;
            transform: translateY(-50%);
            background: white;
            border-radius: 10px;
            padding: 15px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            max-height: 80vh;
            overflow-y: auto;
            width: 250px;
            z-index: 99;
        }

        .as-navigation h3 {
            color: #8e44ad;
            margin-bottom: 10px;
            font-size: 16px;
            text-align: center;
            padding-bottom: 10px;
            border-bottom: 1px solid #e0e0e0;
        }

        .as-nav-list {
            list-style: none;
            padding: 0;
        }

        .as-nav-item {
            margin-bottom: 8px;
        }

        .as-nav-link {
            display: block;
            padding: 8px 12px;
            background: #f8f9fa;
            border-radius: 6px;
            text-decoration: none;
            color: #333;
            font-size: 13px;
            transition: all 0.2s ease;
            border-left: 3px solid transparent;
        }

        .as-nav-link:hover {
            background: #e8e9ea;
            border-left-color: #8e44ad;
            transform: translateX(5px);
        }

        .as-nav-link.active {
            background: #8e44ad;
            color: white;
            border-left-color: #6c3483;
        }

        .server-count {
            float: right;
            font-size: 11px;
            background: #e0e0e0;
            color: #666;
            padding: 2px 6px;
            border-radius: 10px;
        }

        .as-nav-link.active .server-count {
            background: rgba(255,255,255,0.2);
            color: white;
        }

        @media (max-width: 768px) {
            .container {
                padding: 10px;
            }

            .header {
                padding: 15px;
            }

            .header h1 {
                font-size: 20px;
            }

            .stats-grid {
                grid-template-columns: 1fr;
            }

            .as-header {
                flex-direction: column;
                align-items: flex-start;
                gap: 10px;
            }

            .as-stats {
                flex-direction: column;
                gap: 8px;
                width: 100%;
            }

            .as-stats span {
                justify-content: space-between;
            }

            .chart-container {
                padding: 10px;
            }

            .controls {
                position: static;
                margin-top: 20px;
                flex-direction: row;
                flex-wrap: wrap;
                justify-content: center;
            }

            .btn {
                flex: 1;
                min-width: 150px;
                justify-content: center;
            }

            .as-navigation {
                position: static;
                transform: none;
                width: 100%;
                max-height: 200px;
                margin-bottom: 20px;
            }

            .scroll-hint {
                display: none;
            }
        }
    </style>
</head>
<body>
    <div class="loading" id="loading">
        <div class="spinner"></div>
        <div>Загрузка...</div>
    </div>

    <!-- Навигация по АС -->
    <div class="as-navigation">
        <h3>📋 Навигация по АС</h3>
        <ul class="as-nav-list" id="asNavList">
            {% for as_name, as_data in as_groups.items() %}
            <li class="as-nav-item">
                <a href="#as-{{ loop.index }}" class="as-nav-link" data-as-index="{{ loop.index }}">
                    {{ as_name }}
                    <span class="server-count">{{ as_data.servers|length }}</span>
                </a>
            </li>
            {% endfor %}
        </ul>
    </div>

    <div class="container">
        <div class="header">
            <h1>🏢 Тепловые карты нагрузки памяти по Автоматизированным Системам</h1>
            <div class="subtitle">Анализ нагрузки памяти серверов | 48 интервалов по 30 минут | Показано {{ selected_count }} АС</div>

            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-value" id="stat-as">{{ selected_count }}</div>
                    <div class="stat-label">АВТОМАТИЗИРОВАННЫХ СИСТЕМ</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value" id="stat-servers">{{ total_servers }}</div>
                    <div class="stat-label">СЕРВЕРОВ</div>
                </div>
                <div class="stat-card cpu">
                    <div class="stat-value">{{ total_cpu_capacity }}</div>
                    <div class="stat-label">ЯДЕР CPU</div>
                </div>
                <div class="stat-card ram">
                    <div class="stat-value">{{ total_ram_capacity }}</div>
                    <div class="stat-label">ГБ RAM</div>
                </div>
            </div>

            <div style="margin-top: 15px; font-size: 14px; color: #666;">
                <span>📅 Период: {{ start_date }} - {{ end_date }}</span> | 
                <span>🔄 Сортировка: {{ sort_by }}, {{ sort_order }}</span> | 
                <span>⚡ Фильтр: {{ filter_text }}</span>
            </div>
        </div>

        <div class="content">
            <div class="legend">
                <h3>📊 Легенда нагрузки памяти:</h3>
                <div class="legend-items">
                    <div class="legend-item">
                        <div class="legend-color" style="background-color: #00FF00;"></div>
                        <span>0-25%: Низкая нагрузка</span>
                    </div>
                    <div class="legend-item">
                        <div class="legend-color" style="background-color: #90EE90;"></div>
                        <span>25-50%: Умеренная нагрузка</span>
                    </div>
                    <div class="legend-item">
                        <div class="legend-color" style="background-color: #FFFF00;"></div>
                        <span>50-70%: Средняя нагрузка</span>
                    </div>
                    <div class="legend-item">
                        <div class="legend-color" style="background-color: #FFA500;"></div>
                        <span>70-80%: Высокая нагрузка</span>
                    </div>
                    <div class="legend-item">
                        <div class="legend-color" style="background-color: #FF0000;"></div>
                        <span>80-100%: Критическая нагрузка</span>
                    </div>
                </div>
            </div>

            <!-- Быстрые действия -->
            <div class="quick-actions">
                <button class="quick-btn" onclick="toggleNavigation()">
                    📋 Показать/скрыть навигацию
                </button>
            </div>

            <!-- Секции с тепловыми картами по АС -->
            {{ all_html_content }}
        </div>

        <div class="footer">
            <div class="footer-info">
                <span>📅 Период анализа: {{ start_date }} - {{ end_date }}</span>
                <span>🔄 Сгенерировано: {{ generation_time }}</span>
            </div>
            <div>
                <span>👆 Используйте навигацию слева для быстрого перехода к нужной АС</span>
            </div>
        </div>
    </div>

    <!-- Подсказка о прокрутке -->
    <div class="scroll-hint" id="scrollHint">
        ↓ Используйте прокрутку для просмотра всех АС ↓
    </div>

    <script>
        // Показать загрузку
        function showLoading() {
            document.getElementById('loading').classList.add('show');
        }

        // Скрыть загрузку
        function hideLoading() {
            document.getElementById('loading').classList.remove('show');
        }

        // Прокрутка к определенной АС
        function scrollToAS(asId) {
            const element = document.getElementById(asId);
            if (element) {
                element.scrollIntoView({ behavior: 'smooth', block: 'start' });

                // Обновляем активную ссылку в навигации
                document.querySelectorAll('.as-nav-link').forEach(link => {
                    link.classList.remove('active');
                });
                document.querySelector(`.as-nav-link[href="#${asId}"]`).classList.add('active');
            }
        }

        // Прокрутка наверх
        function scrollToTop() {
            window.scrollTo({ top: 0, behavior: 'smooth' });
        }

        // Скачать все тепловые карты
        function downloadAllCharts() {
            showLoading();

            // Находим все графики Plotly
            const chartDivs = document.querySelectorAll('.as-chart .plotly-graph-div');
            let downloadPromises = [];

            chartDivs.forEach((chartDiv, index) => {
                // Получаем имя АС из заголовка
                const asSection = chartDiv.closest('.as-section');
                const asName = asSection.querySelector('.as-header h2').textContent.replace('🏢 АС: ', '');

                const promise = Plotly.downloadImage(chartDiv, {
                    format: 'png',
                    width: 1200,
                    height: Math.max(400, chartDiv.querySelectorAll('.ytick').length * 25),
                    scale: 2,
                    filename: `memory_heatmap_${asName.replace(/[^a-zA-Z0-9]/g, '_')}_{{ start_date_short }}_{{ end_date_short }}`
                });

                downloadPromises.push(promise);
            });

            // Ждем завершения всех загрузок
            Promise.all(downloadPromises)
                .then(() => {
                    hideLoading();
                    alert('✅ Все тепловые карты успешно скачаны!');
                })
                .catch((err) => {
                    console.error('Ошибка скачивания:', err);
                    hideLoading();
                    alert('⚠️ Произошла ошибка при скачивании некоторых графиков');
                });
        }

        // Обновление навигации при прокрутке
        function updateActiveNav() {
            const sections = document.querySelectorAll('.as-section');
            const scrollPosition = window.scrollY + 100;

            sections.forEach((section, index) => {
                const rect = section.getBoundingClientRect();
                const elementTop = rect.top + window.scrollY;
                const elementBottom = elementTop + rect.height;

                const link = document.querySelector(`.as-nav-link[href="#as-${index + 1}"]`);
                if (link) {
                    if (scrollPosition >= elementTop && scrollPosition < elementBottom) {
                        link.classList.add('active');
                    } else {
                        link.classList.remove('active');
                    }
                }
            });
        }

        // Показать/скрыть навигацию
        function toggleNavigation() {
            const nav = document.querySelector('.as-navigation');
            if (nav.style.display === 'none') {
                nav.style.display = 'block';
            } else {
                nav.style.display = 'none';
            }
        }

        // Скрыть подсказку о прокрутке через 5 секунд
        setTimeout(() => {
            const hint = document.getElementById('scrollHint');
            if (hint) {
                hint.style.display = 'none';
            }
        }, 5000);

        // Горячие клавиши
        document.addEventListener('keydown', function(e) {
            // Ctrl+S - сохранение всех графиков
            if ((e.ctrlKey || e.metaKey) && e.key === 's') {
                e.preventDefault();
                downloadAllCharts();
            }
            // Home - наверх
            if (e.key === 'Home') {
                e.preventDefault();
                scrollToTop();
            }
            // End - вниз
            if (e.key === 'End') {
                e.preventDefault();
                window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' });
            }
            // Ctrl+H - скрыть/показать навигацию
            if ((e.ctrlKey || e.metaKey) && e.key === 'h') {
                e.preventDefault();
                toggleNavigation();
            }
        });

        // Автоматическая прокрутка при загрузке
        window.onload = function() {
            // Скрыть загрузку
            setTimeout(() => {
                hideLoading();
            }, 1000);

            // Добавляем id к секциям АС
            const sections = document.querySelectorAll('.as-section');
            sections.forEach((section, index) => {
                section.id = `as-${index + 1}`;
            });

            // Добавляем обработчик прокрутки для обновления навигации
            window.addEventListener('scroll', updateActiveNav);

            // Инициализируем навигацию
            updateActiveNav();

            // Добавляем обработчики для навигационных ссылок
            document.querySelectorAll('.as-nav-link').forEach(link => {
                link.addEventListener('click', function(e) {
                    e.preventDefault();
                    const targetId = this.getAttribute('href').substring(1);
                    scrollToAS(targetId);
                });
            });

            // Фокусируемся на первой АС
            if (sections.length > 0) {
                scrollToAS('as-1');
            }
        };
    </script>
</body>
</html>
    """

    # Рассчитываем период в днях
    period_days = (end_date - start_date).days + 1

    # Подготавливаем данные для передачи в шаблон
    current_datetime = datetime.now()
    timestamp = current_datetime.strftime("%Y%m%d_%H%M%S")
    date_range = f"{start_date.strftime('%d.%m.%Y')} - {end_date.strftime('%d.%m.%Y')}"

    # Заполняем шаблон
    template = Template(scrollable_html_template)
    final_html = template.render(
        all_html_content=all_html_content,
        selected_count=selected_count,
        total_servers=total_servers,
        total_cpu_capacity=f"{total_cpu_capacity:.0f}",
        total_ram_capacity=f"{total_ram_capacity:.0f}",
        start_date=start_date.strftime("%d.%m.%Y"),
        end_date=end_date.strftime("%d.%m.%Y"),
        start_date_short=start_date.strftime("%Y%m%d"),
        end_date_short=end_date.strftime("%Y%m%d"),
        period_days=period_days,
        server_count=len(y_labels),
        generation_time=current_datetime.strftime("%d.%m.%Y %H:%M"),
        sort_by=sort_by,
        sort_order=sort_order,
        filter_text=filter_text,
        as_groups=as_groups
    )

    return final_html

def create_cpu_heatmap_html(fig_heatmap_cpu, y_labels, x_labels, values_matrix, pivot_df_cpu,
                            server_cpu_capacity_map, server_ram_capacity_map,
                            start_date, end_date, selected_count, total_servers,
                            total_cpu_capacity, total_ram_capacity, sort_by_cpu, sort_order_cpu, filter_text):
    """Создает HTML файл с тепловой картой CPU, группируя серверы по АС"""

    # Группируем данные по АС
    as_groups = {}
    for i, (_, row) in enumerate(pivot_df_cpu.iterrows()):
        as_name = row['as_name']
        server = row['server']

        if as_name not in as_groups:
            as_groups[as_name] = {
                'indices': [],
                'servers': [],
                'cpu_capacities': [],
                'ram_capacities': [],
                'rows': []
            }

        as_groups[as_name]['indices'].append(i)
        as_groups[as_name]['servers'].append(server)
        as_groups[as_name]['cpu_capacities'].append(server_cpu_capacity_map.get(server, 0))
        as_groups[as_name]['ram_capacities'].append(server_ram_capacity_map.get(server, 0))
        as_groups[as_name]['rows'].append(row)

    # Создаем HTML с отдельными тепловыми картами для каждой АС
    all_html_content = ""

    for as_name, as_data in as_groups.items():
        # Создаем фигуру для текущей АС
        fig_as = go.Figure()

        # Получаем данные только для текущей АС
        as_indices = as_data['indices']
        as_y_labels = [y_labels[i] for i in as_indices]
        as_values = values_matrix[as_indices, :]

        # Подготовка hover данных для текущей АС
        hover_texts = []
        for i, idx in enumerate(as_indices):
            row = as_data['rows'][i]
            server = as_data['servers'][i]
            cpu_capacity = as_data['cpu_capacities'][i]
            ram_capacity = as_data['ram_capacities'][i]
            row_hover = []

            for j, interval in enumerate(range(48)):
                load_value = as_values[i, j]
                hour = interval // 2
                minute = (interval % 2) * 30
                time_str = f"{hour:02d}:{minute:02d}"

                if load_value <= 0:
                    text = (f"<b>{as_name} | {server}</b><br>"
                            f"CPU: {cpu_capacity:.0f} ядер | RAM: {ram_capacity:.0f} GB<br>"
                            f"Время: {time_str}<br>Нет данных")
                else:
                    # Цветовая категоризация нагрузки CPU
                    if load_value < 15:
                        load_status = "🟢 Низкая"
                    elif load_value < 50:
                        load_status = "🟡 Средняя"
                    elif load_value < 85:
                        load_status = "🟠 Высокая"
                    elif load_value < 95:
                        load_status = "🔴 Критическая"
                    else:
                        load_status = "🛑 Аварийная"

                    text = (f"<b>{as_name} | {server}</b><br>"
                            f"CPU: {cpu_capacity:.0f} ядер | RAM: {ram_capacity:.0f} GB<br>"
                            f"🕐 {time_str}<br>"
                            f"📊 Нагрузка CPU: <b>{load_value:.1f}%</b><br>"
                            f"🏷️ {load_status}")

                row_hover.append(text)
            hover_texts.append(row_hover)

        # Добавляем тепловую карту для текущей АС
        fig_as.add_trace(go.Heatmap(
            z=as_values,
            x=x_labels,
            y=as_y_labels,
            colorscale=[
                [0.0, "#00FF00"],   # Ярко-зеленый (0%)
                [0.3, "#90EE90"],   # Светло-зеленый (30%)
                [0.5, "#FFFF00"],   # Желтый (50%)
                [0.7, "#FFA500"],   # Оранжевый (70%)
                [1.0, "#FF0000"]    # Красный (100%)
            ],
            text=as_values.round(1),
            texttemplate='%{text}%',
            textfont={"size": 8, "color": "black"},
            colorbar=dict(
                title="Нагрузка CPU (%)",
                titleside="right",
                tickvals=[0, 25, 50, 75, 100],
                ticktext=["0%", "25%", "50%", "75%", "100%"],
                len=0.9
            ),
            hoverinfo='text',
            hovertext=hover_texts,
            hovertemplate="%{hovertext}<extra></extra>",
            zmin=0,
            zmax=100,
            showscale=True,
            xgap=0.5,
            ygap=0.5
        ))

        # Рассчитываем высоту графика на основе количества серверов в АС
        as_chart_height = max(400, len(as_y_labels) * 30)

        # Общая статистика для АС
        as_servers_count = len(as_y_labels)
        as_total_cpu = sum(as_data['cpu_capacities'])
        as_total_ram = sum(as_data['ram_capacities'])
        as_avg_cpu = as_total_cpu / as_servers_count if as_servers_count > 0 else 0

        # Настраиваем лейаут для текущей АС
        fig_as.update_layout(
            height=as_chart_height,
            title=dict(
                text=f"АС: {as_name}<br>Серверов: {as_servers_count} | CPU: {as_total_cpu:.0f} ядер | RAM: {as_total_ram:.0f} GB",
                font=dict(size=16),
                x=0.5,
                xanchor='center'
            ),
            xaxis=dict(
                title="Время суток (интервалы по 30 минут)",
                tickmode='array',
                tickvals=list(range(0, 48, 4)),
                ticktext=[x_labels[i] for i in range(0, 48, 4)],
                tickangle=45,
                tickfont=dict(size=9),
                gridcolor='rgba(128, 128, 128, 0.2)',
                showgrid=True,
                fixedrange=True
            ),
            yaxis=dict(
                title="Сервер (CPU ядра | RAM GB)",
                tickfont=dict(size=8),
                automargin=True
            ),
            margin=dict(l=150, r=50, t=80, b=80),
            plot_bgcolor='white',
            paper_bgcolor='white'
        )

        # Добавляем линии для часов
        for hour in range(0, 48, 2):
            fig_as.add_vline(
                x=hour - 0.5,
                line_dash="dot",
                line_color="rgba(128, 128, 128, 0.3)",
                line_width=1
            )

        # Конвертируем фигуру для текущей АС в HTML
        as_html_content = pio.to_html(
            fig_as,
            full_html=False,
            include_plotlyjs='cdn',
            config={
                'responsive': True,
                'displayModeBar': True,
                'displaylogo': False,
                'modeBarButtonsToAdd': ['toImage', 'resetScale2d'],
                'scrollZoom': True,
                'showTips': True
            }
        )

        # Добавляем HTML текущей АС к общему контенту
        all_html_content += f"""
        <div class="as-section">
            <div class="as-header">
                <h2>🏢 АС: {as_name}</h2>
                <div class="as-stats">
                    <span>📊 Серверов: {as_servers_count}</span>
                    <span>⚡ CPU: {as_total_cpu:.0f} ядер</span>
                    <span>💾 RAM: {as_total_ram:.0f} GB</span>
                </div>
            </div>
            <div class="chart-container as-chart">
                {as_html_content}
            </div>
        </div>
        <hr class="as-divider">
        """

    # Создаем HTML с прокруткой и фильтрацией
    scrollable_html_template = """
    <!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Тепловые карты нагрузки CPU по АС</title>
    <script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: #f5f7fa;
            color: #333;
            line-height: 1.6;
        }

        .container {
            max-width: 1400px;
            margin: 0 auto;
            padding: 20px;
        }

        .header {
            background: white;
            border-radius: 10px;
            padding: 25px;
            margin-bottom: 20px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            text-align: center;
        }

        .header h1 {
            color: #1a73e8;
            font-size: 24px;
            margin-bottom: 10px;
        }

        .subtitle {
            color: #666;
            font-size: 16px;
            margin-bottom: 20px;
        }

        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-top: 20px;
        }

        .stat-card {
            background: linear-gradient(135deg, #1a73e8 0%, #0d47a1 100%);
            color: white;
            padding: 15px;
            border-radius: 8px;
            text-align: center;
        }

        .stat-card.cpu {
            background: linear-gradient(135deg, #3498db 0%, #2980b9 100%);
        }

        .stat-card.ram {
            background: linear-gradient(135deg, #9b59b6 0%, #8e44ad 100%);
        }

        .stat-value {
            font-size: 28px;
            font-weight: bold;
            margin-bottom: 5px;
        }

        .stat-label {
            font-size: 14px;
            opacity: 0.9;
        }

        /* Секции АС */
        .as-section {
            background: white;
            border-radius: 10px;
            padding: 20px;
            margin-bottom: 20px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }

        .as-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
            padding-bottom: 15px;
            border-bottom: 2px solid #e0e0e0;
        }

        .as-header h2 {
            color: #1a73e8;
            font-size: 20px;
            margin: 0;
        }

        .as-stats {
            display: flex;
            gap: 20px;
            font-size: 14px;
            color: #666;
        }

        .as-stats span {
            display: flex;
            align-items: center;
            gap: 5px;
            padding: 5px 10px;
            background: #f8f9fa;
            border-radius: 6px;
            border: 1px solid #e0e0e0;
        }

        .as-divider {
            border: none;
            border-top: 3px solid #1a73e8;
            margin: 30px 0;
            opacity: 0.3;
        }

        /* Контент */
        .content {
            background: white;
            border-radius: 10px;
            padding: 20px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            margin-bottom: 20px;
        }

        .chart-container {
            width: 100%;
            overflow-x: auto;
            overflow-y: visible;
            border: 1px solid #e0e0e0;
            border-radius: 8px;
            padding: 15px;
            background: white;
        }

        .as-chart {
            margin-top: 15px;
        }

        .legend {
            background: #f8f9fa;
            border-radius: 8px;
            padding: 15px;
            margin-top: 20px;
            border-left: 4px solid #1a73e8;
        }

        .legend h3 {
            color: #1a73e8;
            margin-bottom: 10px;
            font-size: 16px;
        }

        .legend-items {
            display: flex;
            flex-wrap: wrap;
            gap: 15px;
        }

        .legend-item {
            display: flex;
            align-items: center;
            font-size: 14px;
        }

        .legend-color {
            width: 20px;
            height: 20px;
            border-radius: 4px;
            margin-right: 8px;
        }

        .footer {
            text-align: center;
            color: #666;
            font-size: 14px;
            padding: 20px;
            background: white;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }

        .footer-info {
            display: flex;
            justify-content: center;
            gap: 20px;
            flex-wrap: wrap;
            margin-bottom: 10px;
        }

        .scroll-hint {
            position: fixed;
            bottom: 20px;
            left: 50%;
            transform: translateX(-50%);
            background: rgba(0,0,0,0.8);
            color: white;
            padding: 10px 20px;
            border-radius: 20px;
            font-size: 14px;
            animation: fadeInOut 3s ease-in-out;
            z-index: 100;
        }

        @keyframes fadeInOut {
            0%, 100% { opacity: 0; }
            10%, 90% { opacity: 1; }
        }

        .loading {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(255,255,255,0.9);
            justify-content: center;
            align-items: center;
            z-index: 9999;
            flex-direction: column;
        }

        .loading.show {
            display: flex;
        }

        .spinner {
            width: 40px;
            height: 40px;
            border: 4px solid #f3f3f3;
            border-top: 4px solid #1a73e8;
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin-bottom: 15px;
        }

        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }

        /* Быстрые кнопки */
        .quick-actions {
            display: flex;
            gap: 10px;
            justify-content: center;
            margin-top: 15px;
            flex-wrap: wrap;
        }

        .quick-btn {
            padding: 8px 15px;
            border: 2px solid #1a73e8;
            background: white;
            color: #1a73e8;
            border-radius: 6px;
            cursor: pointer;
            font-size: 14px;
            font-weight: 600;
            transition: all 0.3s ease;
        }

        .quick-btn:hover {
            background: #1a73e8;
            color: white;
        }

        /* Навигация по АС */
        .as-navigation {
            position: fixed;
            left: 20px;
            top: 50%;
            transform: translateY(-50%);
            background: white;
            border-radius: 10px;
            padding: 15px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            max-height: 80vh;
            overflow-y: auto;
            width: 250px;
            z-index: 99;
        }

        .as-navigation h3 {
            color: #1a73e8;
            margin-bottom: 10px;
            font-size: 16px;
            text-align: center;
            padding-bottom: 10px;
            border-bottom: 1px solid #e0e0e0;
        }

        .as-nav-list {
            list-style: none;
            padding: 0;
        }

        .as-nav-item {
            margin-bottom: 8px;
        }

        .as-nav-link {
            display: block;
            padding: 8px 12px;
            background: #f8f9fa;
            border-radius: 6px;
            text-decoration: none;
            color: #333;
            font-size: 13px;
            transition: all 0.2s ease;
            border-left: 3px solid transparent;
        }

        .as-nav-link:hover {
            background: #e8e9ea;
            border-left-color: #1a73e8;
            transform: translateX(5px);
        }

        .as-nav-link.active {
            background: #1a73e8;
            color: white;
            border-left-color: #0d47a1;
        }

        .server-count {
            float: right;
            font-size: 11px;
            background: #e0e0e0;
            color: #666;
            padding: 2px 6px;
            border-radius: 10px;
        }

        .as-nav-link.active .server-count {
            background: rgba(255,255,255,0.2);
            color: white;
        }

        @media (max-width: 768px) {
            .container {
                padding: 10px;
            }

            .header {
                padding: 15px;
            }

            .header h1 {
                font-size: 20px;
            }

            .stats-grid {
                grid-template-columns: 1fr;
            }

            .as-header {
                flex-direction: column;
                align-items: flex-start;
                gap: 10px;
            }

            .as-stats {
                flex-direction: column;
                gap: 8px;
                width: 100%;
            }

            .as-stats span {
                justify-content: space-between;
            }

            .chart-container {
                padding: 10px;
            }

            .as-navigation {
                position: static;
                transform: none;
                width: 100%;
                max-height: 200px;
                margin-bottom: 20px;
            }

            .scroll-hint {
                display: none;
            }
        }
    </style>
</head>
<body>
    <div class="loading" id="loading">
        <div class="spinner"></div>
        <div>Загрузка...</div>
    </div>

    <!-- Навигация по АС -->
    <div class="as-navigation">
        <h3>📋 Навигация по АС</h3>
        <ul class="as-nav-list" id="asNavList">
            {% for as_name, as_data in as_groups.items() %}
            <li class="as-nav-item">
                <a href="#as-{{ loop.index }}" class="as-nav-link" data-as-index="{{ loop.index }}">
                    {{ as_name }}
                    <span class="server-count">{{ as_data.servers|length }}</span>
                </a>
            </li>
            {% endfor %}
        </ul>
    </div>

    <div class="container">
        <div class="header">
            <h1>🏢 Тепловые карты нагрузки CPU по Автоматизированным Системам</h1>
            <div class="subtitle">Анализ нагрузки CPU серверов | 48 интервалов по 30 минут | Показано {{ selected_count }} АС</div>

            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-value" id="stat-as">{{ selected_count }}</div>
                    <div class="stat-label">АВТОМАТИЗИРОВАННЫХ СИСТЕМ</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value" id="stat-servers">{{ total_servers }}</div>
                    <div class="stat-label">СЕРВЕРОВ</div>
                </div>
                <div class="stat-card cpu">
                    <div class="stat-value">{{ total_cpu_capacity }}</div>
                    <div class="stat-label">ЯДЕР CPU</div>
                </div>
                <div class="stat-card ram">
                    <div class="stat-value">{{ total_ram_capacity }}</div>
                    <div class="stat-label">ГБ RAM</div>
                </div>
            </div>

            <div style="margin-top: 15px; font-size: 14px; color: #666;">
                <span>📅 Период: {{ start_date }} - {{ end_date }}</span> | 
                <span>🔄 Сортировка: {{ sort_by }}, {{ sort_order }}</span> | 
                <span>⚡ Фильтр: {{ filter_text }}</span>
            </div>
        </div>

        <div class="content">
            <div class="legend">
                <h3>📊 Легенда нагрузки CPU:</h3>
                <div class="legend-items">
                    <div class="legend-item">
                        <div class="legend-color" style="background-color: #00FF00;"></div>
                        <span>0-15%: Низкая нагрузка</span>
                    </div>
                    <div class="legend-item">
                        <div class="legend-color" style="background-color: #90EE90;"></div>
                        <span>15-50%: Умеренная нагрузка</span>
                    </div>
                    <div class="legend-item">
                        <div class="legend-color" style="background-color: #FFFF00;"></div>
                        <span>50-85%: Средняя нагрузка</span>
                    </div>
                    <div class="legend-item">
                        <div class="legend-color" style="background-color: #FFA500;"></div>
                        <span>85-95%: Высокая нагрузка</span>
                    </div>
                    <div class="legend-item">
                        <div class="legend-color" style="background-color: #FF0000;"></div>
                        <span>95-100%: Критическая нагрузка</span>
                    </div>
                </div>
            </div>

            <!-- Быстрые действия -->
            <div class="quick-actions">
                <button class="quick-btn" onclick="toggleNavigation()">
                    📋 Показать/скрыть навигацию
                </button>
            </div>

            <!-- Секции с тепловыми картами по АС -->
            {{ all_html_content }}
        </div>

        <div class="footer">
            <div class="footer-info">
                <span>📅 Период анализа: {{ start_date }} - {{ end_date }}</span>
                <span>🔄 Сгенерировано: {{ generation_time }}</span>
            </div>
            <div>
                <span>👆 Используйте навигацию слева для быстрого перехода к нужной АС</span>
            </div>
        </div>
    </div>

    <!-- Подсказка о прокрутке -->
    <div class="scroll-hint" id="scrollHint">
        ↓ Используйте прокрутку для просмотра всех АС ↓
    </div>

    <script>
        // Показать загрузку
        function showLoading() {
            document.getElementById('loading').classList.add('show');
        }

        // Скрыть загрузку
        function hideLoading() {
            document.getElementById('loading').classList.remove('show');
        }

        // Прокрутка к определенной АС
        function scrollToAS(asId) {
            const element = document.getElementById(asId);
            if (element) {
                element.scrollIntoView({ behavior: 'smooth', block: 'start' });

                // Обновляем активную ссылку в навигации
                document.querySelectorAll('.as-nav-link').forEach(link => {
                    link.classList.remove('active');
                });
                document.querySelector(`.as-nav-link[href="#${asId}"]`).classList.add('active');
            }
        }

        // Прокрутка наверх
        function scrollToTop() {
            window.scrollTo({ top: 0, behavior: 'smooth' });
        }

        // Скачать все тепловые карты
        function downloadAllCharts() {
            showLoading();

            // Находим все графики Plotly
            const chartDivs = document.querySelectorAll('.as-chart .plotly-graph-div');
            let downloadPromises = [];

            chartDivs.forEach((chartDiv, index) => {
                // Получаем имя АС из заголовка
                const asSection = chartDiv.closest('.as-section');
                const asName = asSection.querySelector('.as-header h2').textContent.replace('🏢 АС: ', '');

                const promise = Plotly.downloadImage(chartDiv, {
                    format: 'png',
                    width: 1200,
                    height: Math.max(400, chartDiv.querySelectorAll('.ytick').length * 25),
                    scale: 2,
                    filename: `cpu_heatmap_${asName.replace(/[^a-zA-Z0-9]/g, '_')}_{{ start_date_short }}_{{ end_date_short }}`
                });

                downloadPromises.push(promise);
            });

            // Ждем завершения всех загрузок
            Promise.all(downloadPromises)
                .then(() => {
                    hideLoading();
                    alert('✅ Все тепловые карты успешно скачаны!');
                })
                .catch((err) => {
                    console.error('Ошибка скачивания:', err);
                    hideLoading();
                    alert('⚠️ Произошла ошибка при скачивании некоторых графиков');
                });
        }

        // Обновление навигации при прокрутке
        function updateActiveNav() {
            const sections = document.querySelectorAll('.as-section');
            const scrollPosition = window.scrollY + 100;

            sections.forEach((section, index) => {
                const rect = section.getBoundingClientRect();
                const elementTop = rect.top + window.scrollY;
                const elementBottom = elementTop + rect.height;

                const link = document.querySelector(`.as-nav-link[href="#as-${index + 1}"]`);
                if (link) {
                    if (scrollPosition >= elementTop && scrollPosition < elementBottom) {
                        link.classList.add('active');
                    } else {
                        link.classList.remove('active');
                    }
                }
            });
        }

        // Показать/скрыть навигацию
        function toggleNavigation() {
            const nav = document.querySelector('.as-navigation');
            if (nav.style.display === 'none') {
                nav.style.display = 'block';
            } else {
                nav.style.display = 'none';
            }
        }

        // Скрыть подсказку о прокрутке через 5 секунд
        setTimeout(() => {
            const hint = document.getElementById('scrollHint');
            if (hint) {
                hint.style.display = 'none';
            }
        }, 5000);

        // Горячие клавиши
        document.addEventListener('keydown', function(e) {
            // Ctrl+S - сохранение всех графиков
            if ((e.ctrlKey || e.metaKey) && e.key === 's') {
                e.preventDefault();
                downloadAllCharts();
            }
            // Home - наверх
            if (e.key === 'Home') {
                e.preventDefault();
                scrollToTop();
            }
            // End - вниз
            if (e.key === 'End') {
                e.preventDefault();
                window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' });
            }
            // Ctrl+H - скрыть/показать навигацию
            if ((e.ctrlKey || e.metaKey) && e.key === 'h') {
                e.preventDefault();
                toggleNavigation();
            }
        });

        // Автоматическая прокрутка при загрузке
        window.onload = function() {
            // Скрыть загрузку
            setTimeout(() => {
                hideLoading();
            }, 1000);

            // Добавляем id к секциям АС
            const sections = document.querySelectorAll('.as-section');
            sections.forEach((section, index) => {
                section.id = `as-${index + 1}`;
            });

            // Добавляем обработчик прокрутки для обновления навигации
            window.addEventListener('scroll', updateActiveNav);

            // Инициализируем навигацию
            updateActiveNav();

            // Добавляем обработчики для навигационных ссылок
            document.querySelectorAll('.as-nav-link').forEach(link => {
                link.addEventListener('click', function(e) {
                    e.preventDefault();
                    const targetId = this.getAttribute('href').substring(1);
                    scrollToAS(targetId);
                });
            });

            // Фокусируемся на первой АС
            if (sections.length > 0) {
                scrollToAS('as-1');
            }
        };
    </script>
</body>
</html>
    """

    # Рассчитываем период в днях
    period_days = (end_date - start_date).days + 1

    # Подготавливаем данные для передачи в шаблон
    current_datetime = datetime.now()
    timestamp = current_datetime.strftime("%Y%m%d_%H%M%S")
    date_range = f"{start_date.strftime('%d.%m.%Y')} - {end_date.strftime('%d.%m.%Y')}"

    # Заполняем шаблон
    template = Template(scrollable_html_template)
    final_html = template.render(
        all_html_content=all_html_content,
        selected_count=selected_count,
        total_servers=total_servers,
        total_cpu_capacity=f"{total_cpu_capacity:.0f}",
        total_ram_capacity=f"{total_ram_capacity:.0f}",
        start_date=start_date.strftime("%d.%m.%Y"),
        end_date=end_date.strftime("%d.%m.%Y"),
        start_date_short=start_date.strftime("%Y%m%d"),
        end_date_short=end_date.strftime("%Y%m%d"),
        period_days=period_days,
        server_count=len(y_labels),
        generation_time=current_datetime.strftime("%d.%m.%Y %H:%M"),
        sort_by=sort_by_cpu,
        sort_order=sort_order_cpu,
        filter_text=filter_text,
        as_groups=as_groups
    )

    return final_html


def show():
    """Страница анализа в разрезе АС"""
    st.markdown('<h2 class="sub-header"> Анализ в разрезе Автоматизированных Систем </h2>', unsafe_allow_html=True)

    try:
        # Загружаем данные для определения диапазона дат
        initial_df = load_data_from_db()

        if initial_df.empty:
            st.warning("⚠️ Данные не найдены в базе данных.")
            st.info("💡 Используйте API или утилиты для загрузки данных в базу.")
            return

        # Загружаем маппинг АС и мощности серверов
        as_mapping = load_as_mapping_data()
        server_capacities = load_server_capacities()

        if not as_mapping:
            st.warning("⚠️ Не удалось загрузить данные о маппинге серверов на АС.")
            st.info("💡 Убедитесь, что файл all_vm.xlsx находится в правильной директории.")

        # Выбор даты для анализа
        col_date1, col_date2 = st.columns([1, 3])

        with col_date1:
            st.markdown('<div class="server-selector fade-in">', unsafe_allow_html=True)

            # Выбор диапазона дат
            min_date = pd.to_datetime(initial_df['timestamp']).min().date()
            max_date = pd.to_datetime(initial_df['timestamp']).max().date()

            date_range_type = "Одна дата"

            if date_range_type == "Одна дата":
                analysis_date = st.date_input(
                    "**Выберите дату:**",
                    max_date,
                    min_value=min_date,
                    max_value=max_date,
                    key="as_analysis_date_picker"
                )
                start_date = datetime.combine(analysis_date, datetime.min.time())
                end_date = datetime.combine(analysis_date, datetime.max.time())

            st.markdown("### Выбор АС для анализа")

            # Загружаем и подготавливаем данные для получения списка АС
            temp_df = load_data_from_db(start_date=start_date, end_date=end_date)

            # Используем исправленную функцию prepare_as_analysis_data
            temp_df, temp_as_stats, _ = prepare_as_analysis_data(temp_df, as_mapping, server_capacities)

            # Получаем список всех АС
            all_as = sorted(list(temp_as_stats.keys()))

            if not all_as:
                st.warning("⚠️ Не удалось определить АС для анализа.")
                st.markdown('</div>', unsafe_allow_html=True)
                st.stop()

            # Инициализируем session state для выбранных АС
            if 'selected_as' not in st.session_state:
                st.session_state.selected_as = all_as

            # Выбор АС с чекбоксами
            selected_as = st.multiselect(
                "**Автоматизированные системы:**",
                all_as,
                default=st.session_state.get('selected_as', []),
                key="analysis_as"
            )

            # Обновляем session state при изменении выбора
            st.session_state.selected_as = selected_as

            # Показываем статистику выбора
            total_as = len(all_as)
            selected_count = len(selected_as)

            total_servers = sum(
                temp_as_stats[as_name]['server_count'] for as_name in selected_as if as_name in temp_as_stats)

            st.info(f"""
            **Статистика выбора:**
            - Всего АС в базе: **{total_as}**
            - Выбрано АС: **{selected_count}** ({selected_count / total_as * 100:.1f}%)
            - Серверов в выбранных АС: **{total_servers}**
            """)

            # БЫСТРЫЕ ФИЛЬТРЫ МОЩНОСТИ RAM (ИЗМЕНЕНО: теперь фильтруем по RAM, а не CPU)
            st.markdown("### Фильтры мощности RAM")

            # Инициализация session state для быстрых фильтров
            if 'quick_ram_filter' not in st.session_state:
                st.session_state.quick_ram_filter = 'all'

            # Создаем колонки для кнопок
            col_bt1, col_bt2, col_bt3 = st.columns(3)

            with col_bt1:
                if st.button("↺ Все",
                             type="primary" if st.session_state.quick_ram_filter == 'all' else "secondary",
                             use_container_width=True):
                    st.session_state.quick_ram_filter = 'all'

            with col_bt2:
                if st.button("\>4GB",
                             type="primary" if st.session_state.quick_ram_filter == 'gt4' else "secondary",
                             use_container_width=True):
                    st.session_state.quick_ram_filter = 'gt4'

            with col_bt3:
                if st.button("\>8GB",
                             type="primary" if st.session_state.quick_ram_filter == 'gt8' else "secondary",
                             use_container_width=True):
                    st.session_state.quick_ram_filter = 'gt8'

            # Еще одна строка кнопок
            col_bt4, col_bt5, col_bt6 = st.columns(3)

            with col_bt4:
                if st.button("\>16GB",
                             type="primary" if st.session_state.quick_ram_filter == 'gt16' else "secondary",
                             use_container_width=True):
                    st.session_state.quick_ram_filter = 'gt16'

            with col_bt5:
                if st.button("\>32GB",
                             type="primary" if st.session_state.quick_ram_filter == 'gt32' else "secondary",
                             use_container_width=True):
                    st.session_state.quick_ram_filter = 'gt32'

            with col_bt6:
                if st.button("\>64GB",
                             type="primary" if st.session_state.quick_ram_filter == 'gt64' else "secondary",
                             use_container_width=True):
                    st.session_state.quick_ram_filter = 'gt64'

            # Показываем текущий выбранный фильтр
            filter_texts = {
                'all': 'Все серверы',
                'gt4': 'RAM > 4 GB',
                'gt8': 'RAM > 8 GB',
                'gt16': 'RAM > 16 GB',
                'gt32': 'RAM > 32 GB',
                'gt64': 'RAM > 64 GB'
            }

            st.info(f"**Текущий фильтр:** {filter_texts.get(st.session_state.quick_ram_filter, 'Все серверы')}")

            # Кнопка обновления
            refresh_btn = st.button(
                "🔄 Обновить данные",
                type="primary",
                use_container_width=True,
                key="refresh_as_analysis"
            )

            st.markdown('</div>', unsafe_allow_html=True)

        with col_date2:
            # Загружаем данные за выбранный период
            if refresh_btn:
                load_data_from_db.clear()

            analysis_df = load_data_from_db(start_date=start_date, end_date=end_date)

            if analysis_df.empty:
                st.warning(f"⚠️ Нет данных за выбранный период ({start_date.date()} - {end_date.date()})")
                return

            # Подготавливаем данные для анализа по АС
            analysis_df, as_stats, server_to_as = prepare_as_analysis_data(analysis_df, as_mapping, server_capacities)

            # Применение фильтров
            if selected_as:
                # Фильтруем по выбранным АС
                analysis_df = analysis_df[analysis_df['as_name'].isin(selected_as)].copy()
            else:
                # Если не выбраны АС - показываем все
                st.info("АС не выбраны. Отображаются все доступные системы.")

            # Фильтрация по мощности RAM с использованием быстрых фильтров
            if selected_as and 'server_capacity_ram' in analysis_df.columns:
                # Применяем быстрый фильтр мощности RAM
                quick_filter = st.session_state.get('quick_ram_filter', 'all')

                if quick_filter != 'all':
                    if quick_filter == 'gt4':
                        filtered_servers = analysis_df[analysis_df['server_capacity_ram'] > 4]['server'].unique()
                    elif quick_filter == 'gt8':
                        filtered_servers = analysis_df[analysis_df['server_capacity_ram'] > 8]['server'].unique()
                    elif quick_filter == 'gt16':
                        filtered_servers = analysis_df[analysis_df['server_capacity_ram'] > 16]['server'].unique()
                    elif quick_filter == 'gt32':
                        filtered_servers = analysis_df[analysis_df['server_capacity_ram'] > 32]['server'].unique()
                    elif quick_filter == 'gt64':
                        filtered_servers = analysis_df[analysis_df['server_capacity_ram'] > 64]['server'].unique()
                    else:
                        filtered_servers = analysis_df['server'].unique()

                    analysis_df = analysis_df[analysis_df['server'].isin(filtered_servers)].copy()

            if analysis_df.empty:
                st.warning("⚠️ Нет данных, соответствующих выбранным фильтрам")
                return

            # Создаем словари для быстрого доступа к мощностям серверов
            server_cpu_capacity_map = analysis_df.groupby('server')['server_capacity_cpu'].first().to_dict()
            server_ram_capacity_map = analysis_df.groupby('server')['server_capacity_ram'].first().to_dict()

            # 1. ТЕПЛОВАЯ КАРТА НАГРУЗКИ ПАМЯТИ
            st.markdown("### 🔥 Тепловая карта нагрузки памяти по серверам в разрезе АС")

            if 'mem.usage.average' in analysis_df.columns:
                # Выбор режима отображения
                view_mode = st.radio(
                    "**Режим отображения:**",
                    ["Общая карта (все АС)", "Отдельные карты по АС"],
                    key="mem_view_mode",
                    horizontal=True
                )

                # Выбор типа сортировки
                col_sort1, col_sort2 = st.columns(2)
                with col_sort1:
                    sort_by = st.selectbox(
                        "**Сортировка по:**",
                        ["Суммарной нагрузке", "Средней нагрузке", "Мощности RAM", "Имени АС"],
                        key="heatmap_mem_sort_by"
                    )

                with col_sort2:
                    sort_order = st.selectbox(
                        "**Порядок сортировки:**",
                        ["По убыванию", "По возрастанию"],
                        key="heatmap_mem_sort_order"
                    )

                if view_mode == "Общая карта (все АС)":
                    # Используем компонент для создания общей карты
                    try:
                        fig_heatmap_mem, y_labels, x_labels, values_matrix, pivot_df = create_as_mem_heatmap(
                            analysis_df,
                            server_cpu_capacity_map,
                            server_ram_capacity_map,
                            sort_by,
                            sort_order
                        )
                        
                        # Отображаем тепловую карту
                        st.markdown(
                            f"""
                            <style>
                            .scrollable-chart {{
                                max-height: 800px;
                                overflow-y: auto;
                                overflow-x: auto;
                                border: 1px solid #e0e0e0;
                                border-radius: 8px;
                                padding: 10px;
                                background: white;
                                margin-bottom: 20px;
                            }}
                            </style>
                            <div class="scrollable-chart">
                            """,
                            unsafe_allow_html=True
                        )

                        st.plotly_chart(fig_heatmap_mem, use_container_width=True, config={'scrollZoom': True})
                        st.markdown("</div>", unsafe_allow_html=True)
                    except Exception as e:
                        st.error(f"Ошибка при создании тепловой карты памяти: {e}")
                        st.exception(e)
                
                else:  # Отдельные карты по АС
                    # Используем компонент для создания отдельных карт
                    try:
                        as_figures = create_separate_as_mem_heatmaps(
                            analysis_df,
                            server_cpu_capacity_map,
                            server_ram_capacity_map,
                            sort_by,
                            sort_order
                        )
                        
                        if not as_figures:
                            st.warning("⚠️ Не удалось создать тепловые карты для выбранных АС")
                        else:
                            # Отображаем карты для каждой АС
                            for as_name, fig in as_figures.items():
                                st.markdown(f"#### 🏢 АС: {as_name}")
                                
                                st.markdown(
                                    f"""
                                    <style>
                                    .scrollable-chart {{
                                        max-height: 600px;
                                        overflow-y: auto;
                                        overflow-x: auto;
                                        border: 1px solid #e0e0e0;
                                        border-radius: 8px;
                                        padding: 10px;
                                        background: white;
                                        margin-bottom: 20px;
                                    }}
                                    </style>
                                    <div class="scrollable-chart">
                                    """,
                                    unsafe_allow_html=True
                                )
                                
                                st.plotly_chart(fig, use_container_width=True, config={'scrollZoom': True})
                                st.markdown("</div>", unsafe_allow_html=True)
                                st.divider()
                    except Exception as e:
                        st.error(f"Ошибка при создании отдельных тепловых карт памяти: {e}")
                        st.exception(e)

                st.divider()

                # HTML экспорт карты памяти
                st.markdown("---")
                col_export_mem1, col_export_mem2 = st.columns([1, 1])

                with col_export_mem1:
                    if st.button("🌐 Скачать HTML карты нагрузки памяти", type="primary", use_container_width=True):
                        with st.spinner("Создаем HTML файл тепловой карты памяти..."):
                            try:
                                # Рассчитываем суммарные мощности
                                total_cpu_capacity = analysis_df['server_capacity_cpu'].sum()
                                total_ram_capacity = analysis_df['server_capacity_ram'].sum()

                                # Получаем текущий фильтр
                                filter_text = filter_texts.get(st.session_state.get('quick_ram_filter', 'all'),
                                                               'Все серверы')

                                # В разделе создания HTML для памяти, добавьте подготовку as_groups:

                                # Подготавливаем данные по группам АС
                                as_groups = {}
                                for as_name, group in pivot_df.groupby('as_name'):
                                    servers_in_as = group['server'].tolist()
                                    total_cpu = sum(server_cpu_capacity_map.get(s, 0) for s in servers_in_as)
                                    total_ram = sum(server_ram_capacity_map.get(s, 0) for s in servers_in_as)

                                    # Получаем индексы серверов этой АС в values_matrix
                                    server_indices = [i for i, label in enumerate(y_labels) if as_name in label]
                                    avg_load = np.mean(values_matrix[server_indices]) if server_indices else 0

                                    # Собираем данные по каждому серверу
                                    server_loads = {}
                                    for i, server in enumerate(servers_in_as):
                                        if i < len(server_indices):
                                            idx = server_indices[i]
                                            server_avg_load = np.mean(values_matrix[idx]) if idx < len(
                                                values_matrix) else 0
                                            server_loads[server] = {'avg': server_avg_load}

                                    as_groups[as_name] = {
                                        'servers': servers_in_as,
                                        'server_count': len(servers_in_as),
                                        'total_cpu_capacity': total_cpu,
                                        'total_ram_capacity': total_ram,
                                        'avg_ram_load': avg_load,
                                        'server_loads': server_loads
                                    }

                                # Создаем HTML
                                html_content = create_memory_heatmap_html(
                                    fig_heatmap_mem,
                                    y_labels,
                                    x_labels,
                                    values_matrix,
                                    pivot_df,
                                    server_cpu_capacity_map,
                                    server_ram_capacity_map,
                                    start_date,
                                    end_date,
                                    selected_count,
                                    total_servers,
                                    total_cpu_capacity,
                                    total_ram_capacity,
                                    sort_by,
                                    sort_order,
                                    filter_text
                                    #as_groups=as_groups  # Добавляем этот параметр
                                )

                                # Генерируем имя файла
                                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                                filename = f"memory_heatmap_{timestamp}.html"

                                # Предлагаем скачать
                                st.download_button(
                                    label="⬇️ Нажмите для скачивания HTML",
                                    data=html_content,
                                    file_name=filename,
                                    mime="text/html",
                                    use_container_width=True,
                                    key="download_memory_html"
                                )

                                st.success(f"✅ HTML файл '{filename}' готов к скачиванию!")

                            except Exception as e:
                                st.error(f"Ошибка при создании HTML: {str(e)}")
                                import traceback
                                st.error(f"Детали: {traceback.format_exc()}")

                with col_export_mem2:
                    if st.button("📊 Экспорт статистики памяти (CSV)", type="secondary", use_container_width=True):
                        with st.spinner("Подготавливаем данные для экспорта..."):
                            try:
                                # Создаем DataFrame для экспорта
                                export_df = analysis_df[['as_name', 'server', 'timestamp', 'mem.usage.average',
                                                         'server_capacity_cpu', 'server_capacity_ram']].copy()
                                export_df = export_df.sort_values(['as_name', 'server', 'timestamp'])

                                csv = export_df.to_csv(index=False, encoding='utf-8-sig')
                                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                                filename = f"memory_stats_{timestamp}.csv"

                                st.download_button(
                                    label="⬇️ Скачать CSV",
                                    data=csv,
                                    file_name=filename,
                                    mime="text/csv",
                                    use_container_width=True,
                                    key="download_memory_csv"
                                )

                                st.success(f"✅ CSV файл '{filename}' готов к скачиванию!")

                            except Exception as e:
                                st.error(f"Ошибка при создании CSV: {str(e)}")
            st.divider()

            # ТАБЛИЦА СТАТИСТИКИ ДЛЯ ПАМЯТИ С МОЩНОСТЯМИ CPU И RAM
            st.markdown("### 📊 Детальная статистика нагрузки памяти")

            if 'mem.usage.average' in analysis_df.columns:
                # Создаем подробную таблицу статистики
                detailed_stats_mem = analysis_df.groupby(['as_name', 'server']).agg({
                    'mem.usage.average': ['mean', 'std', 'min', 'max', 'count'],
                    'server_capacity_cpu': 'first',
                    'server_capacity_ram': 'first'
                }).round(2)

                # Упрощаем мультииндекс
                detailed_stats_mem.columns = ['_'.join(col).strip() for col in detailed_stats_mem.columns.values]
                detailed_stats_mem = detailed_stats_mem.rename(columns={
                    'mem.usage.average_mean': 'Средняя нагрузка RAM',
                    'mem.usage.average_std': 'Стд. откл. RAM',
                    'mem.usage.average_min': 'Мин. RAM',
                    'mem.usage.average_max': 'Макс. RAM',
                    'mem.usage.average_count': 'Записей',
                    'server_capacity_cpu_first': 'Мощность CPU (ядра)',
                    'server_capacity_ram_first': 'Мощность RAM (GB)'
                })

                detailed_stats_mem = detailed_stats_mem.reset_index()

                # Добавляем суммарную нагрузку если есть
                if 'total_load' in pivot_df.columns:
                    load_sums = pivot_df.set_index(['as_name', 'server'])['total_load']
                    detailed_stats_mem = detailed_stats_mem.set_index(['as_name', 'server'])
                    detailed_stats_mem['Суммарная нагрузка RAM'] = load_sums
                    detailed_stats_mem = detailed_stats_mem.reset_index()

                # Отображаем таблицу
                st.dataframe(
                    detailed_stats_mem.style
                    .background_gradient(
                        cmap='RdYlGn_r',
                        subset=['Средняя нагрузка RAM', 'Макс. RAM']
                    )
                    .format({
                        'Средняя нагрузка RAM': '{:.1f}%',
                        'Мощность CPU (ядра)': '{:.1f}',
                        'Мощность RAM (GB)': '{:.1f}'
                    }),
                    use_container_width=True,
                    height=400
                )

            st.divider()

            # 2. ТЕПЛОВАЯ КАРТА НАГРУЗКИ CPU
            st.markdown("### 🔥 Тепловая карта нагрузки CPU по серверам в разрезе АС")

            if 'cpu.usage.average' in analysis_df.columns:
                # Выбор режима отображения
                view_mode_cpu = st.radio(
                    "**Режим отображения:**",
                    ["Общая карта (все АС)", "Отдельные карты по АС"],
                    key="cpu_view_mode",
                    horizontal=True
                )

                # Выбор типа сортировки для CPU
                col_sort_cpu1, col_sort_cpu2 = st.columns(2)
                with col_sort_cpu1:
                    sort_by_cpu = st.selectbox(
                        "**Сортировка по:**",
                        ["Суммарной нагрузке", "Средней нагрузке", "Мощности CPU", "Имени АС"],
                        key="heatmap_cpu_sort_by"
                    )

                with col_sort_cpu2:
                    sort_order_cpu = st.selectbox(
                        "**Порядок сортировки:**",
                        ["По убыванию", "По возрастанию"],
                        key="heatmap_cpu_sort_order"
                    )

                if view_mode_cpu == "Общая карта (все АС)":
                    # Используем компонент для создания общей карты
                    try:
                        fig_heatmap_cpu, y_labels_cpu, x_labels, values_matrix_cpu, pivot_df_cpu = create_as_cpu_heatmap(
                            analysis_df,
                            server_cpu_capacity_map,
                            server_ram_capacity_map,
                            sort_by_cpu,
                            sort_order_cpu
                        )

                        # Отображаем тепловую карту CPU
                        st.markdown(
                            f"""
                            <style>
                            .scrollable-chart {{
                                max-height: 800px;
                                overflow-y: auto;
                                overflow-x: auto;
                                border: 1px solid #e0e0e0;
                                border-radius: 8px;
                                padding: 10px;
                                background: white;
                                margin-bottom: 20px;
                            }}
                            </style>
                            <div class="scrollable-chart">
                            """,
                            unsafe_allow_html=True
                        )

                        st.plotly_chart(fig_heatmap_cpu, use_container_width=True, config={'scrollZoom': True})
                        st.markdown("</div>", unsafe_allow_html=True)
                    except Exception as e:
                        st.error(f"Ошибка при создании тепловой карты CPU: {e}")
                        st.exception(e)
                
                else:  # Отдельные карты по АС
                    # Используем компонент для создания отдельных карт
                    try:
                        as_figures_cpu = create_separate_as_cpu_heatmaps(
                            analysis_df,
                            server_cpu_capacity_map,
                            server_ram_capacity_map,
                            sort_by_cpu,
                            sort_order_cpu
                        )
                        
                        if not as_figures_cpu:
                            st.warning("⚠️ Не удалось создать тепловые карты для выбранных АС")
                        else:
                            # Отображаем карты для каждой АС
                            for as_name, fig in as_figures_cpu.items():
                                st.markdown(f"#### 🏢 АС: {as_name}")
                                
                                st.markdown(
                                    f"""
                                    <style>
                                    .scrollable-chart {{
                                        max-height: 600px;
                                        overflow-y: auto;
                                        overflow-x: auto;
                                        border: 1px solid #e0e0e0;
                                        border-radius: 8px;
                                        padding: 10px;
                                        background: white;
                                        margin-bottom: 20px;
                                    }}
                                    </style>
                                    <div class="scrollable-chart">
                                    """,
                                    unsafe_allow_html=True
                                )
                                
                                st.plotly_chart(fig, use_container_width=True, config={'scrollZoom': True})
                                st.markdown("</div>", unsafe_allow_html=True)
                                st.divider()
                    except Exception as e:
                        st.error(f"Ошибка при создании отдельных тепловых карт CPU: {e}")
                        st.exception(e)

                st.divider()

                # В разделе тепловой карты CPU, после отображения графика, добавьте:
                # HTML экспорт карты CPU
                st.markdown("---")
                col_export_cpu1, col_export_cpu2 = st.columns([1, 1])

                with col_export_cpu1:
                    if st.button("🌐 Скачать HTML карты нагрузки CPU", type="primary", use_container_width=True):
                        with st.spinner("Создаем HTML файл тепловой карты CPU..."):
                            try:
                                # Рассчитываем суммарные мощности
                                total_cpu_capacity = analysis_df['server_capacity_cpu'].sum()
                                total_ram_capacity = analysis_df['server_capacity_ram'].sum()

                                # Получаем текущий фильтр
                                filter_text = filter_texts.get(st.session_state.get('quick_ram_filter', 'all'),
                                                               'Все серверы')

                                # Создаем HTML
                                html_content = create_cpu_heatmap_html(
                                    fig_heatmap_cpu,
                                    y_labels_cpu,
                                    x_labels,
                                    values_matrix_cpu,
                                    pivot_df_cpu,
                                    server_cpu_capacity_map,
                                    server_ram_capacity_map,
                                    start_date,
                                    end_date,
                                    selected_count,
                                    total_servers,
                                    total_cpu_capacity,
                                    total_ram_capacity,
                                    sort_by_cpu,
                                    sort_order_cpu,
                                    filter_text
                                )

                                # Генерируем имя файла
                                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                                filename = f"cpu_heatmap_{timestamp}.html"

                                # Предлагаем скачать
                                st.download_button(
                                    label="⬇️ Нажмите для скачивания HTML",
                                    data=html_content,
                                    file_name=filename,
                                    mime="text/html",
                                    use_container_width=True,
                                    key="download_cpu_html"
                                )

                                st.success(f"✅ HTML файл '{filename}' готов к скачиванию!")

                            except Exception as e:
                                st.error(f"Ошибка при создании HTML: {str(e)}")
                                import traceback
                                st.error(f"Детали: {traceback.format_exc()}")

                with col_export_cpu2:
                    if st.button("📊 Экспорт статистики CPU (CSV)", type="secondary", use_container_width=True):
                        with st.spinner("Подготавливаем данные для экспорта..."):
                            try:
                                # Создаем DataFrame для экспорта
                                export_df = analysis_df[['as_name', 'server', 'timestamp', 'cpu.usage.average',
                                                         'server_capacity_cpu', 'server_capacity_ram']].copy()
                                export_df = export_df.sort_values(['as_name', 'server', 'timestamp'])

                                csv = export_df.to_csv(index=False, encoding='utf-8-sig')
                                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                                filename = f"cpu_stats_{timestamp}.csv"

                                st.download_button(
                                    label="⬇️ Скачать CSV",
                                    data=csv,
                                    file_name=filename,
                                    mime="text/csv",
                                    use_container_width=True,
                                    key="download_cpu_csv"
                                )

                                st.success(f"✅ CSV файл '{filename}' готов к скачиванию!")

                            except Exception as e:
                                st.error(f"Ошибка при создании CSV: {str(e)}")

                # ТАБЛИЦА СТАТИСТИКИ ДЛЯ CPU С МОЩНОСТЯМИ CPU И RAM
                st.markdown("### 📊 Детальная статистика нагрузки CPU")

                # Создаем подробную таблицу статистики для CPU
                detailed_stats_cpu = analysis_df.groupby(['as_name', 'server']).agg({
                    'cpu.usage.average': ['mean', 'std', 'min', 'max', 'count'],
                    'server_capacity_cpu': 'first',
                    'server_capacity_ram': 'first'
                }).round(2)

                # Упрощаем мультииндекс
                detailed_stats_cpu.columns = ['_'.join(col).strip() for col in detailed_stats_cpu.columns.values]
                detailed_stats_cpu = detailed_stats_cpu.rename(columns={
                    'cpu.usage.average_mean': 'Средняя нагрузка CPU',
                    'cpu.usage.average_std': 'Стд. откл. CPU',
                    'cpu.usage.average_min': 'Мин. CPU',
                    'cpu.usage.average_max': 'Макс. CPU',
                    'cpu.usage.average_count': 'Записей',
                    'server_capacity_cpu_first': 'Мощность CPU (ядра)',
                    'server_capacity_ram_first': 'Мощность RAM (GB)'
                })

                detailed_stats_cpu = detailed_stats_cpu.reset_index()

                # Добавляем суммарную нагрузку если есть
                if 'total_load' in pivot_df_cpu.columns:
                    load_sums_cpu = pivot_df_cpu.set_index(['as_name', 'server'])['total_load']
                    detailed_stats_cpu = detailed_stats_cpu.set_index(['as_name', 'server'])
                    detailed_stats_cpu['Суммарная нагрузка CPU'] = load_sums_cpu
                    detailed_stats_cpu = detailed_stats_cpu.reset_index()

                # Отображаем таблицу
                st.dataframe(
                    detailed_stats_cpu.style
                    .background_gradient(
                        cmap='RdYlGn_r',
                        subset=['Средняя нагрузка CPU', 'Макс. CPU']
                    )
                    .format({
                        'Средняя нагрузка CPU': '{:.1f}%',
                        'Мощность CPU (ядра)': '{:.1f}',
                        'Мощность RAM (GB)': '{:.1f}'
                    }),
                    use_container_width=True,
                    height=400
                )

                # ОБЩАЯ СТАТИСТИКА
                st.divider()
                st.markdown("### 📈 Статистика")

                col_stat1, col_stat2, col_stat3, col_stat4 = st.columns(4)

                with col_stat1:
                    total_as_filtered = analysis_df['as_name'].nunique()
                    st.metric("АС", total_as_filtered)

                with col_stat2:
                    total_servers = analysis_df['server'].nunique()
                    st.metric("Серверов", total_servers)

                with col_stat3:
                    if 'cpu.usage.average' in analysis_df.columns:
                        avg_cpu_load = analysis_df['cpu.usage.average'].mean()
                        total_cpu_capacity = analysis_df['server_capacity_cpu'].sum()
                        st.metric("Нагрузка CPU", f"{avg_cpu_load:.1f}%",
                                  f"Мощность: {total_cpu_capacity:.0f} ядер")

                with col_stat4:
                    if 'mem.usage.average' in analysis_df.columns:
                        avg_ram_load = analysis_df['mem.usage.average'].mean()
                        total_ram_capacity = analysis_df['server_capacity_ram'].sum()
                        st.metric("Нагрузка RAM", f"{avg_ram_load:.1f}%",
                                  f"Мощность: {total_ram_capacity:.0f} GB")

    except Exception as e:
        st.error(f"Ошибка при анализе по АС: {e}")
        import traceback
        with st.expander("Детали ошибки"):
            st.code(traceback.format_exc())
    
        # Добавляем кнопку для перехода в LLM UI в конце страницы
    st.divider()
    st.markdown("### 🤖 Переход в LLM интерфейс")

    # Проверяем доступность контейнера Llama
    LLAMA_UI_URL_HEALTH = "http://llama-server:8080"
    LLAMA_UI_URL = "http://localhost:8080"  # Уточнен порт

    # Функция для проверки доступности (выполняется на сервере)
    @st.cache_data(ttl=30)  # Кэшируем результат на 30 секунд
    def check_llama_availability():
        try:
            response = requests.get(f"{LLAMA_UI_URL_HEALTH}/health", timeout=5)
            return response.status_code == 200, LLAMA_UI_URL
        except requests.exceptions.RequestException:
            try:
                response = requests.get(f"{LLAMA_UI_URL}", timeout=5)
                return response.status_code == 200, LLAMA_UI_URL
            except:
                return False, LLAMA_UI_URL

    # Проверяем доступность
    is_available, llama_url = check_llama_availability()

    # Создаем кнопку
    col1, col2, col3 = st.columns([1, 2, 1])

    with col2:
        if is_available:
            if st.button(
                    "🚀 Перейти в LLM UI",
                    type="primary",
                    use_container_width=True,
                    help="Откроет интерфейс LLM в новой вкладке"
            ):
                # Используем markdown с ссылкой для открытия в новой вкладке
                st.markdown(f'<a href="{llama_url}" target="_blank" style="display: none;" id="llama-link"></a>',
                            unsafe_allow_html=True)
                st.success(f"✅ LLM UI доступен по адресу: {llama_url}")
                # Добавляем JavaScript для открытия ссылки
                st.components.v1.html(f"""
                    <script>
                        window.open("{llama_url}", "_blank");
                    </script>
                """, height=0)
        else:
            st.warning("⚠️ LLM UI временно недоступен")

            if st.button("🔄 Проверить доступность снова", use_container_width=True):
                st.cache_data.clear()  # Очищаем кэш
                st.rerun()

            st.info("""
            **Возможные причины:**
            - Сервер LLM не запущен
            - Контейнер llama-server не активен
            - Порт 8080 занят другим приложением
            """)