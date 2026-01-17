from datetime import datetime
import json

import chardet
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots


def detect_encoding(file_path):
    """Определяет кодировку файла"""
    with open(file_path, 'rb') as f:
        raw_data = f.read(10000)
    result = chardet.detect(raw_data)
    return result['encoding']


def create_cpu_heatmap_dashboard(data_file_path, output_html_path='cpu_dashboard.html'):
    """
    Создает красивый интерактивный дашборд с тепловой картой CPU нагрузки

    Parameters:
    -----------
    data_file_path : str
        Путь к файлу с данными
    output_html_path : str
        Путь для сохранения HTML файла
    """

    # Определяем кодировку файла
    try:
        encoding = detect_encoding(data_file_path)
        print(f"Определена кодировка: {encoding}")
    except:
        encoding = 'utf-8'
        print(f"Не удалось определить кодировку, используется utf-8")

    # Чтение данных из файла
    print("Чтение данных...")
    try:
        with open(data_file_path, 'r', encoding=encoding) as f:
            lines = f.readlines()
    except UnicodeDecodeError:
        print(f"Ошибка с кодировкой {encoding}, пробуем latin-1...")
        with open(data_file_path, 'r', encoding='latin-1') as f:
            lines = f.readlines()

    # Парсинг данных
    data = []
    for line in lines:
        # Пропускаем пустые строки и строки с метаданными
        if not line.strip() or 'metadata.sheet_name' in line or 'metadata.sheet_index_num' in line:
            continue

        # Пропускаем строки с заголовком таблицы
        if line.strip().startswith('|') and ('---' in line or 'vm' in line.lower() and 'metric' in line.lower()):
            continue

        # Проверяем, что это строка с данными
        if '|' in line and len(line.split('|')) >= 4:
            parts = line.strip().split('|')
            # Убираем пробелы и проверяем, что это валидные данные
            cleaned_parts = [part.strip() for part in parts if part.strip()]

            if len(cleaned_parts) >= 4:
                try:
                    vm = cleaned_parts[0]
                    metric = cleaned_parts[1]
                    value = float(cleaned_parts[2])
                    timestamp = cleaned_parts[3]
                    data.append([vm, metric, value, timestamp])
                except (ValueError, IndexError) as e:
                    print(f"Ошибка парсинга строки: {line[:100]}...")
                    continue

    if not data:
        print("Ошибка: не удалось извлечь данные из файла")
        print("Первые несколько строк файла:")
        for i, line in enumerate(lines[:10]):
            print(f"{i}: {line.strip()}")
        return None

    print(f"Обработано {len(data)} записей")

    # Создание DataFrame
    df = pd.DataFrame(data, columns=['vm', 'metric', 'value', 'timestamp'])

    # Преобразование времени
    try:
        df['timestamp'] = pd.to_datetime(df['timestamp'])
    except Exception as e:
        print(f"Ошибка преобразования времени: {e}")
        # Пробуем другой формат
        try:
            df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
        except:
            print("Не удалось преобразовать время, создаем искусственные временные метки")
            df['timestamp'] = pd.date_range(start='2025-12-07 00:00:00', periods=len(df), freq='30min')

    df['time_str'] = df['timestamp'].dt.strftime('%H:%M')

    print(f"Уникальных серверов: {df['vm'].nunique()}")
    print(f"Диапазон времени: {df['timestamp'].min()} - {df['timestamp'].max()}")

    # Подготовка данных для тепловой карты
    servers = sorted(df['vm'].unique())
    time_points = sorted(df['time_str'].unique())

    print(f"Уникальных временных точек: {len(time_points)}")

    # Создание матрицы значений
    z_matrix = []
    hover_text = []

    # Статистика
    max_load = 0
    max_load_server = ''
    max_load_time = ''
    total_load = 0
    total_measurements = 0
    min_load = 100
    min_load_server = ''
    peak_count = 0

    for server in servers:
        server_row = []
        server_hover = []

        server_data = df[df['vm'] == server]

        for time_point in time_points:
            time_data = server_data[server_data['time_str'] == time_point]
            if not time_data.empty:
                value = time_data['value'].iloc[0]
                server_row.append(value)
                server_hover.append(f'Сервер: {server}<br>Время: {time_point}<br>Нагрузка CPU: {value:.2f}%')

                # Обновление статистики
                total_load += value
                total_measurements += 1

                if value > max_load:
                    max_load = value
                    max_load_server = server
                    max_load_time = time_point

                if value < min_load and value > 0:
                    min_load = value
                    min_load_server = server

                if value > 20:
                    peak_count += 1
            else:
                server_row.append(0)
                server_hover.append(f'Сервер: {server}<br>Время: {time_point}<br>Нет данных')

        z_matrix.append(server_row)
        hover_text.append(server_hover)

    avg_load = total_load / total_measurements if total_measurements > 0 else 0

    print(f"\nСтатистика:")
    print(f"Максимальная нагрузка: {max_load:.2f}% на сервере {max_load_server} в {max_load_time}")
    print(f"Минимальная нагрузка: {min_load:.2f}% на сервере {min_load_server}")
    print(f"Средняя нагрузка: {avg_load:.2f}%")
    print(f"Пиков (>20%): {peak_count}")

    # Создание HTML шаблона
    html_template = f'''
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CPU Usage Dashboard - Все серверы</title>
    <script src="https://cdn.plot.ly/plotly-2.24.1.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/jquery/3.6.0/jquery.min.js"></script>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        }}

        body {{
            background: linear-gradient(135deg, #0f2027 0%, #203a43 50%, #2c5364 100%);
            color: #e0f7fa;
            min-height: 100vh;
            padding: 20px;
        }}

        .container {{
            max-width: 95%;
            margin: 0 auto;
            background: rgba(25, 35, 45, 0.85);
            border-radius: 20px;
            padding: 30px;
            box-shadow: 0 15px 35px rgba(0, 0, 0, 0.5);
            backdrop-filter: blur(10px);
            border: 1px solid rgba(64, 224, 208, 0.2);
        }}

        .header {{
            text-align: center;
            margin-bottom: 30px;
            padding-bottom: 20px;
            border-bottom: 2px solid rgba(64, 224, 208, 0.3);
        }}

        .header h1 {{
            font-size: 2.8rem;
            background: linear-gradient(90deg, #40e0d0, #20b2aa);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 10px;
            text-shadow: 0 2px 10px rgba(64, 224, 208, 0.3);
        }}

        .header p {{
            font-size: 1.2rem;
            color: #b0bec5;
            max-width: 800px;
            margin: 0 auto;
            line-height: 1.6;
        }}

        .date-info {{
            display: flex;
            justify-content: center;
            align-items: center;
            gap: 15px;
            margin-top: 15px;
            flex-wrap: wrap;
        }}

        .date-chip {{
            background: rgba(64, 224, 208, 0.15);
            padding: 8px 20px;
            border-radius: 50px;
            font-size: 1.1rem;
            border: 1px solid rgba(64, 224, 208, 0.3);
            display: flex;
            align-items: center;
            gap: 8px;
        }}

        .controls {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 20px;
            margin-bottom: 25px;
            padding: 20px;
            background: rgba(30, 40, 50, 0.6);
            border-radius: 15px;
            border: 1px solid rgba(64, 224, 208, 0.2);
        }}

        .filter-section {{
            display: flex;
            align-items: center;
            gap: 15px;
            flex-wrap: wrap;
        }}

        .filter-label {{
            font-weight: 600;
            color: #40e0d0;
            font-size: 1.1rem;
        }}

        .search-box {{
            background: rgba(20, 30, 40, 0.8);
            border: 1px solid rgba(64, 224, 208, 0.3);
            border-radius: 10px;
            padding: 12px 20px;
            color: #e0f7fa;
            font-size: 1rem;
            width: 300px;
            transition: all 0.3s;
        }}

        .search-box:focus {{
            outline: none;
            border-color: #40e0d0;
            box-shadow: 0 0 15px rgba(64, 224, 208, 0.2);
        }}

        .legend {{
            display: flex;
            align-items: center;
            gap: 15px;
            flex-wrap: wrap;
        }}

        .legend-item {{
            display: flex;
            align-items: center;
            gap: 8px;
        }}

        .legend-color {{
            width: 25px;
            height: 25px;
            border-radius: 5px;
        }}

        .legend-text {{
            font-size: 0.9rem;
            color: #b0bec5;
        }}

        #heatmap {{
            width: 100%;
            height: 850px;
            background: rgba(15, 25, 35, 0.7);
            border-radius: 15px;
            overflow: hidden;
            border: 1px solid rgba(64, 224, 208, 0.2);
            margin-top: 10px;
        }}

        .stats {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-top: 30px;
        }}

        .stat-card {{
            background: linear-gradient(135deg, rgba(30, 40, 50, 0.8), rgba(20, 30, 40, 0.9));
            border-radius: 15px;
            padding: 25px;
            border: 1px solid rgba(64, 224, 208, 0.2);
            transition: transform 0.3s, box-shadow 0.3s;
        }}

        .stat-card:hover {{
            transform: translateY(-5px);
            box-shadow: 0 10px 25px rgba(0, 0, 0, 0.3);
        }}

        .stat-card h3 {{
            color: #40e0d0;
            margin-bottom: 15px;
            font-size: 1.3rem;
            display: flex;
            align-items: center;
            gap: 10px;
        }}

        .stat-value {{
            font-size: 2.5rem;
            font-weight: 700;
            color: #e0f7fa;
            text-shadow: 0 2px 10px rgba(64, 224, 208, 0.3);
        }}

        .stat-label {{
            color: #b0bec5;
            font-size: 1rem;
            margin-top: 5px;
        }}

        .server-list {{
            margin-top: 30px;
            padding: 25px;
            background: rgba(30, 40, 50, 0.6);
            border-radius: 15px;
            border: 1px solid rgba(64, 224, 208, 0.2);
        }}

        .server-list h3 {{
            color: #40e0d0;
            margin-bottom: 20px;
            font-size: 1.5rem;
        }}

        .server-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
            gap: 15px;
            max-height: 300px;
            overflow-y: auto;
            padding-right: 10px;
        }}

        .server-grid::-webkit-scrollbar {{
            width: 8px;
        }}

        .server-grid::-webkit-scrollbar-track {{
            background: rgba(20, 30, 40, 0.8);
            border-radius: 4px;
        }}

        .server-grid::-webkit-scrollbar-thumb {{
            background: #40e0d0;
            border-radius: 4px;
        }}

        .server-item {{
            background: rgba(20, 30, 40, 0.8);
            padding: 15px;
            border-radius: 10px;
            border-left: 4px solid #40e0d0;
            transition: all 0.3s;
            cursor: pointer;
        }}

        .server-item:hover {{
            background: rgba(64, 224, 208, 0.1);
            transform: translateX(5px);
        }}

        .server-name {{
            font-weight: 600;
            color: #e0f7fa;
            margin-bottom: 5px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }}

        .server-metric {{
            font-size: 0.9rem;
            color: #b0bec5;
        }}

        .footer {{
            text-align: center;
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid rgba(64, 224, 208, 0.2);
            color: #78909c;
            font-size: 0.9rem;
        }}

        .highlight {{
            background-color: rgba(255, 255, 0, 0.2) !important;
            border-color: #ffeb3b !important;
        }}

        @media (max-width: 768px) {{
            .container {{
                padding: 15px;
            }}

            .header h1 {{
                font-size: 2rem;
            }}

            .controls {{
                flex-direction: column;
                align-items: stretch;
            }}

            .search-box {{
                width: 100%;
            }}

            #heatmap {{
                height: 700px;
            }}

            .stat-value {{
                font-size: 2rem;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📊 CPU Usage Dashboard</h1>
            <p>Тепловая карта загрузки процессоров на всех серверах. Цветовая шкала от синего (низкая нагрузка) до красного (высокая нагрузка)</p>
            <div class="date-info">
                <div class="date-chip">
                    <span>📅</span> <span>Дата: {df['timestamp'].dt.date.iloc[0] if len(df) > 0 else '7 декабря 2025'}</span>
                </div>
                <div class="date-chip">
                    <span>⏱️</span> <span>Интервал: 30 минут</span>
                </div>
                <div class="date-chip">
                    <span>🖥️</span> <span>Серверов: {len(servers)}</span>
                </div>
            </div>
        </div>

        <div class="controls">
            <div class="filter-section">
                <div class="filter-label">🔍 Поиск сервера:</div>
                <input type="text" id="serverSearch" class="search-box" placeholder="Введите имя сервера...">
            </div>

            <div class="legend">
                <div class="legend-item">
                    <div class="legend-color" style="background: #0d47a1;"></div>
                    <div class="legend-text">Низкая нагрузка (&lt; 5%)</div>
                </div>
                <div class="legend-item">
                    <div class="legend-color" style="background: #2196f3;"></div>
                    <div class="legend-text">Средняя нагрузка (5-15%)</div>
                </div>
                <div class="legend-item">
                    <div class="legend-color" style="background: #00e676;"></div>
                    <div class="legend-text">Нормальная нагрузка (15-30%)</div>
                </div>
                <div class="legend-item">
                    <div class="legend-color" style="background: #ff9800;"></div>
                    <div class="legend-text">Высокая нагрузка (30-50%)</div>
                </div>
                <div class="legend-item">
                    <div class="legend-color" style="background: #f44336;"></div>
                    <div class="legend-text">Критическая нагрузка (&gt; 50%)</div>
                </div>
            </div>
        </div>

        <div id="heatmap"></div>

        <div class="stats">
            <div class="stat-card">
                <h3>📈 Максимальная нагрузка</h3>
                <div class="stat-value" id="maxLoad">{max_load:.2f}%</div>
                <div class="stat-label" id="maxServer">{max_load_server} ({max_load_time})</div>
            </div>
            <div class="stat-card">
                <h3>📉 Средняя нагрузка</h3>
                <div class="stat-value" id="avgLoad">{avg_load:.2f}%</div>
                <div class="stat-label">По всем серверам</div>
            </div>
            <div class="stat-card">
                <h3>🔄 Минимальная нагрузка</h3>
                <div class="stat-value" id="minLoad">{min_load:.2f}%</div>
                <div class="stat-label" id="minServer">{min_load_server}</div>
            </div>
            <div class="stat-card">
                <h3>🚨 Пиковые значения</h3>
                <div class="stat-value" id="peakCount">{peak_count}</div>
                <div class="stat-label">Нагрузка &gt; 20%</div>
            </div>
        </div>

        <div class="server-list">
            <h3>🖥️ Список серверов</h3>
            <div class="server-grid" id="serverList">
                <!-- Список серверов будет сгенерирован динамически -->
            </div>
        </div>

        <div class="footer">
            <p>CPU Usage Dashboard • Данные за {df['timestamp'].dt.date.iloc[0] if len(df) > 0 else '7 декабря 2025'} • Обновлено: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            <p>Визуализация тепловой карты загрузки CPU на всех серверах</p>
        </div>
    </div>

    <script>
        // Данные для графика
        const servers = {json.dumps(servers)};
        const timePoints = {json.dumps(time_points)};
        const zMatrix = {json.dumps(z_matrix)};
        const hoverText = {json.dumps(hover_text)};

        // Находим максимальное значение для цветовой шкалы
        const maxZValue = Math.max(...zMatrix.flat());
        const zMax = Math.ceil(maxZValue / 5) * 5; // Округляем до ближайшего кратного 5

        // Создание тепловой карты
        const trace = {{
            z: zMatrix,
            x: timePoints,
            y: servers,
            type: 'heatmap',
            colorscale: [
                [0, '#0d47a1'],    // Темно-синий для низких значений
                [0.1, '#2196f3'],   // Синий
                [0.3, '#00e676'],   // Зеленый
                [0.6, '#ff9800'],   // Оранжевый
                [1, '#f44336']      // Красный для высоких значений
            ],
            hoverinfo: 'text',
            text: hoverText,
            hovertemplate: '%{{text}}<extra></extra>',
            zmin: 0,
            zmax: zMax,
            colorbar: {{
                title: 'Нагрузка CPU (%)',
                titleside: 'right',
                tickmode: 'array',
                tickvals: [0, zMax/4, zMax/2, zMax*3/4, zMax],
                ticktext: ['0%', `${{Math.round(zMax/4)}}%`, `${{Math.round(zMax/2)}}%`, `${{Math.round(zMax*3/4)}}%`, `${{Math.round(zMax)}}%`],
                len: 0.8
            }}
        }};

        const layout = {{
            title: {{
                text: 'Тепловая карта загрузки CPU по всем серверам',
                font: {{
                    size: 24,
                    color: '#e0f7fa'
                }},
                x: 0.05
            }},
            xaxis: {{
                title: {{
                    text: 'Время ({df['timestamp'].dt.date.iloc[0] if len(df) > 0 else '7 декабря 2025'})',
                    font: {{
                        size: 16,
                        color: '#b0bec5'
                    }}
                }},
                tickangle: -45,
                gridcolor: 'rgba(64, 224, 208, 0.1)',
                tickfont: {{
                    color: '#90a4ae'
                }},
                linecolor: 'rgba(64, 224, 208, 0.3)'
            }},
            yaxis: {{
                title: {{
                    text: 'Серверы',
                    font: {{
                        size: 16,
                        color: '#b0bec5'
                    }}
                }},
                gridcolor: 'rgba(64, 224, 208, 0.1)',
                tickfont: {{
                    color: '#90a4ae'
                }},
                linecolor: 'rgba(64, 224, 208, 0.3)'
            }},
            plot_bgcolor: 'rgba(15, 25, 35, 0.7)',
            paper_bgcolor: 'rgba(15, 25, 35, 0.7)',
            height: 800,
            margin: {{
                l: 180,
                r: 50,
                b: 150,
                t: 100,
                pad: 10
            }}
        }};

        const config = {{
            responsive: true,
            displayModeBar: true,
            displaylogo: false,
            modeBarButtonsToRemove: ['select2d', 'lasso2d'],
            modeBarButtonsToAdd: ['drawline', 'drawopenpath', 'eraseshape']
        }};

        // Рендерим график
        Plotly.newPlot('heatmap', [trace], layout, config);

        // Создаем список серверов
        const serverListContainer = document.getElementById('serverList');
        servers.forEach((server, index) => {{
            const serverItem = document.createElement('div');
            serverItem.className = 'server-item';
            serverItem.dataset.serverIndex = index;
            serverItem.innerHTML = `
                <div class="server-name">${{server}}</div>
                <div class="server-metric">Средняя: ${{(zMatrix[index].reduce((a, b) => a + b, 0) / zMatrix[index].filter(v => v > 0).length || 1).toFixed(2)}}%</div>
            `;

            // Добавляем клик для выделения строки на тепловой карте
            serverItem.addEventListener('click', () => {{
                // Снимаем выделение со всех элементов
                document.querySelectorAll('.server-item').forEach(item => {{
                    item.classList.remove('highlight');
                }});

                // Выделяем текущий элемент
                serverItem.classList.add('highlight');

                // Прокручиваем график к выбранному серверу
                Plotly.relayout('heatmap', {{
                    'yaxis.range': [Math.max(0, index - 10), Math.min(servers.length, index + 10)]
                }});
            }});

            serverListContainer.appendChild(serverItem);
        }});

        // Функция поиска серверов
        document.getElementById('serverSearch').addEventListener('input', function(e) {{
            const searchTerm = e.target.value.toLowerCase();
            const serverItems = document.querySelectorAll('.server-item');

            serverItems.forEach(item => {{
                const serverName = item.querySelector('.server-name').textContent.toLowerCase();
                if (serverName.includes(searchTerm)) {{
                    item.style.display = 'block';
                }} else {{
                    item.style.display = 'none';
                }}
            }});
        }});

        // Добавляем возможность масштабирования при клике на сервер
        document.getElementById('heatmap').on('plotly_click', function(data) {{
            if (data.points.length > 0) {{
                const point = data.points[0];
                const serverName = point.y;
                const time = point.x;
                const value = point.z;

                // Создаем красивое всплывающее окно
                const modal = document.createElement('div');
                modal.style.cssText = `
                    position: fixed;
                    top: 50%;
                    left: 50%;
                    transform: translate(-50%, -50%);
                    background: rgba(30, 40, 50, 0.95);
                    padding: 30px;
                    border-radius: 15px;
                    border: 2px solid #40e0d0;
                    z-index: 1000;
                    min-width: 300px;
                    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5);
                `;

                modal.innerHTML = `
                    <h3 style="color: #40e0d0; margin-bottom: 20px;">Детали нагрузки</h3>
                    <p style="color: #e0f7fa; margin: 10px 0;"><strong>Сервер:</strong> ${{serverName}}</p>
                    <p style="color: #e0f7fa; margin: 10px 0;"><strong>Время:</strong> ${{time}}</p>
                    <p style="color: #e0f7fa; margin: 10px 0;"><strong>Нагрузка CPU:</strong> <span style="color: #ff9800; font-weight: bold;">${{value.toFixed(2)}}%</span></p>
                    <button onclick="this.parentElement.remove()" style="
                        background: #40e0d0;
                        color: white;
                        border: none;
                        padding: 10px 20px;
                        border-radius: 5px;
                        cursor: pointer;
                        margin-top: 20px;
                        float: right;
                    ">Закрыть</button>
                `;

                document.body.appendChild(modal);

                // Закрытие по клику вне модального окна
                modal.addEventListener('click', function(e) {{
                    if (e.target === modal) {{
                        modal.remove();
                    }}
                }});
            }}
        }});

        // Автоматическое обновление графика при изменении размера окна
        window.addEventListener('resize', function() {{
            Plotly.Plots.resize(document.getElementById('heatmap'));
        }});
    </script>
</body>
</html>
'''

    # Сохранение HTML файла
    print(f"\nСохранение дашборда в {output_html_path}...")
    try:
        with open(output_html_path, 'w', encoding='utf-8') as f:
            f.write(html_template)

        print(f"✅ Дашборд успешно сохранен в {output_html_path}")
        print(f"📊 Серверов: {len(servers)}")
        print(f"⏰ Измерений: {len(df)}")
        print(f"📈 Максимальная нагрузка: {max_load:.2f}%")
        print(f"\nОткройте файл в браузере для просмотра интерактивного дашборда.")

        return output_html_path

    except Exception as e:
        print(f"❌ Ошибка при сохранении файла: {e}")
        return None


def create_excel_version(data_file_path, output_html_path='cpu_excel_dashboard.html'):
    """
    Альтернативная версия для чтения Excel файлов
    """
    try:
        print("Попытка чтения как Excel файла...")
        df = pd.read_excel(data_file_path)
        print(f"Успешно прочитан Excel файл с колонками: {df.columns.tolist()}")

        # Проверяем структуру данных
        print("\nПервые 5 строк данных:")
        print(df.head())

        # Сохраняем во временный файл и обрабатываем
        temp_file = 'temp_data.txt'
        df.to_csv(temp_file, sep='|', index=False)

        return create_cpu_heatmap_dashboard(temp_file, output_html_path)

    except Exception as e:
        print(f"Ошибка чтения Excel: {e}")
        return None


def create_text_version(data_file_path, output_html_path='cpu_text_dashboard.html'):
    """
    Версия для простого текстового файла
    """
    print("Создание дашборда из текстового файла...")

    try:
        # Пробуем разные кодировки
        encodings = ['utf-8', 'latin-1', 'cp1251', 'cp1252', 'iso-8859-1']

        for encoding in encodings:
            try:
                print(f"Пробуем кодировку: {encoding}")
                with open(data_file_path, 'r', encoding=encoding) as f:
                    content = f.read()
                print(f"✅ Успешно прочитано с кодировкой {encoding}")
                break
            except UnicodeDecodeError:
                continue
        else:
            print("❌ Не удалось определить кодировку")
            return None

        # Сохраняем в правильной кодировке
        temp_file = 'temp_utf8.txt'
        with open(temp_file, 'w', encoding='utf-8') as f:
            f.write(content)

        return create_cpu_heatmap_dashboard(temp_file, output_html_path)

    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return None


# Пример использования
if __name__ == "__main__":
    # Укажите путь к вашему файлу с данными
    data_file = "/Users/sweetd0ve/dashboard/data/processed/07.xlsx"  # или "07.txt"

    print("=" * 60)
    print("CPU Usage Dashboard Generator")
    print("=" * 60)

    try:
        # Пробуем разные методы в зависимости от расширения файла
        if data_file.lower().endswith('.xlsx') or data_file.lower().endswith('.xls'):
            print(f"Обработка Excel файла: {data_file}")
            dashboard_file = create_excel_version(data_file, "cpu_dashboard.html")

            if not dashboard_file:
                print("Пробуем обработать как текстовый файл...")
                dashboard_file = create_text_version(data_file, "cpu_dashboard.html")
        else:
            print(f"Обработка текстового файла: {data_file}")
            dashboard_file = create_cpu_heatmap_dashboard(data_file, "cpu_dashboard.html")

        if dashboard_file:
            print("\n" + "=" * 60)
            print("🎉 ДАШБОРД УСПЕШНО СОЗДАН!")
            print("=" * 60)
            print(f"\n📂 Файл: {dashboard_file}")
            print(f"🌐 Откройте файл в браузере (Chrome, Firefox, Edge)")
            print("\nВозможности дашборда:")
            print("  • 📊 Тепловая карта загрузки CPU")
            print("  • 🔍 Поиск по серверам")
            print("  • 📈 Детальная статистика")
            print("  • 🖱️ Интерактивные подсказки")
            print("  • 📱 Адаптивный дизайн")
        else:
            print("\n❌ Не удалось создать дашборд")
            print("\nРекомендации:")
            print("1. Убедитесь, что файл существует и доступен для чтения")
            print("2. Проверьте формат данных (должен быть как в примере)")
            print("3. Попробуйте конвертировать файл в UTF-8")
            print("4. Убедитесь, что есть данные о CPU usage")

    except Exception as e:
        print(f"\n❌ Критическая ошибка: {e}")
        print("\nПопробуйте:")
        print("1. Установить необходимые библиотеки: pip install pandas plotly numpy chardet openpyxl")
        print("2. Проверить путь к файлу")
        print("3. Конвертировать файл в UTF-8")