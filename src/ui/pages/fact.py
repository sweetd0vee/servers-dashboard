import os
import sys
from datetime import datetime, timedelta

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# Добавляем путь для импорта
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

# Импортируем модули для загрузки данных из базы
try:
    from utils.alert_rules import AlertSeverity, ServerStatus, alert_system
    from utils.data_loader import generate_server_data, load_data_from_database
except ImportError:
    # Fallback для прямого импорта
    import importlib.util

    # Импортируем data_loader
    data_loader_path = os.path.join(parent_dir, 'utils', 'data_loader.py')
    if os.path.exists(data_loader_path):
        spec = importlib.util.spec_from_file_location("data_loader", data_loader_path)
        data_loader = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(data_loader)
        load_data_from_database = data_loader.load_data_from_database
        generate_server_data = data_loader.generate_server_data
    else:
        # Fallback на data_generator если data_loader не найден
        data_generator_path = os.path.join(parent_dir, 'utils', 'data_generator.py')
        spec = importlib.util.spec_from_file_location("data_generator", data_generator_path)
        data_generator = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(data_generator)
        generate_server_data = data_generator.generate_server_data
        load_data_from_database = None

    # Импортируем alert_rules
    alert_rules_path = os.path.join(parent_dir, 'utils', 'alert_rules.py')
    spec = importlib.util.spec_from_file_location("alert_rules", alert_rules_path)
    alert_rules = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(alert_rules)
    alert_system = alert_rules.alert_system
    ServerStatus = alert_rules.ServerStatus
    AlertSeverity = alert_rules.AlertSeverity


@st.cache_data(ttl=300)  # Cache for 5 minutes
def load_data_from_db(start_date: datetime = None, end_date: datetime = None, vm: str = None):
    """
    Load data from database with optional date range and VM filter

    Args:
        start_date: Start date for data loading
        end_date: End date for data loading
        vm: Optional VM name to filter

    Returns:
        DataFrame with server metrics
    """
    if load_data_from_database is None:
        # Fallback to generate_server_data if database loader not available
        df = generate_server_data()
        if start_date or end_date:
            if start_date:
                df = df[df['timestamp'] >= pd.Timestamp(start_date)]
            if end_date:
                df = df[df['timestamp'] <= pd.Timestamp(end_date)]
        if vm:
            df = df[df['server'] == vm]
        return df

    try:
        vms = [vm] if vm else None
        df = load_data_from_database(
            start_date=start_date,
            end_date=end_date,
            vms=vms
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
        if vm:
            df = df[df['server'] == vm]
        return df


@st.cache_data(ttl=300)
def load_all_servers():
    """Load list of all servers from database"""
    try:
        df = generate_server_data()
        if df.empty:
            return []
        return sorted(df['server'].unique().tolist())
    except Exception as e:
        st.warning(f"Ошибка загрузки списка серверов: {e}")
        return []


def get_recommendations(status, analysis_data, server_name):
    """Получить рекомендации для сервера"""
    if status == ServerStatus.OVERLOADED:
        return [
            "📈 Увеличить ресурсы: Рассмотреть добавление CPU и памяти",
            "🔄 Оптимизировать нагрузку: Перенести часть задач на другие серверы",
            "⚡ Проверить процессы: Найти и оптимизировать ресурсоемкие процессы",
            "🏗️ Масштабировать горизонтально: Добавить реплики сервиса"
        ]
    elif status == ServerStatus.UNDERLOADED:
        return [
            "📉 Уменьшить ресурсы: Снизить выделенные CPU и память для экономии",
            "🌀 Консолидировать нагрузки: Объединить сервисы с других серверов",
            "💤 Включить режим энергосбережения: Настроить sleep режимы",
            "🚫 Рассмотреть отключение: Если сервер не нужен постоянно"
        ]
    elif status == ServerStatus.NORMAL:
        return [
            "✅ Оптимальная конфигурация: Ресурсы используются эффективно",
            "📊 Продолжать мониторинг: Текущие настройки работают хорошо",
            "🔄 Плановые проверки: Регулярно проверять нагрузку"
        ]
    else:
        return ["📋 Собрать больше данных: Недостаточно информации для анализа"]


def analyze_all_servers(filtered_df):
    """Анализировать статус всех серверов за период"""
    if filtered_df.empty:
        return pd.DataFrame()

    servers = filtered_df['server'].unique()
    results = []

    for server in servers:
        server_data = filtered_df[filtered_df['server'] == server].copy()

        if server_data.empty:
            continue

        try:
            analysis_result = alert_system.analyze_server_status(server_data, server)

            # Рассчитываем средние значения метрик
            avg_cpu = server_data['cpu.usage.average'].mean() if 'cpu.usage.average' in server_data.columns else 0
            avg_memory = server_data['mem.usage.average'].mean() if 'mem.usage.average' in server_data.columns else 0
            avg_network = server_data['net.usage.average'].mean() if 'net.usage.average' in server_data.columns else 0

            # Считаем количество алертов по типам
            alerts = analysis_result.get('alerts', [])
            critical_alerts = len([a for a in alerts if a.rule.severity == AlertSeverity.CRITICAL])
            warning_alerts = len([a for a in alerts if a.rule.severity == AlertSeverity.WARNING])
            info_alerts = len([a for a in alerts if a.rule.severity == AlertSeverity.INFO])

            # Определяем статус
            status = analysis_result.get('status', ServerStatus.UNKNOWN)
            status_text = {
                ServerStatus.OVERLOADED: "🟥 ПЕРЕГРУЗКА",
                ServerStatus.UNDERLOADED: "🟨 ПРОСТОЙ",
                ServerStatus.NORMAL: "🟩 НОРМА",
                ServerStatus.UNKNOWN: "⚪ НЕТ ДАННЫХ"
            }.get(status, "⚪ НЕТ ДАННЫХ")

            # Добавляем рекомендации
            recommendations = get_recommendations(status, analysis_result, server)

            results.append({
                'Сервер': server,
                'Статус': status_text,
                'CPU (%)': f"{avg_cpu:.1f}",
                'Память (%)': f"{avg_memory:.1f}",
                'Сеть (%)': f"{avg_network:.1f}",
                'Критические алерты': critical_alerts,
                'Предупреждения': warning_alerts,
                'Информационные': info_alerts,
                'Всего алертов': len(alerts),
                'Рекомендации': recommendations[0] if recommendations else "Нет рекомендаций"
            })

        except Exception as e:
            st.warning(f"Ошибка анализа сервера {server}: {e}")
            results.append({
                'Сервер': server,
                'Статус': "⚪ ОШИБКА АНАЛИЗА",
                'CPU (%)': "N/A",
                'Память (%)': "N/A",
                'Сеть (%)': "N/A",
                'Критические алерты': 0,
                'Предупреждения': 0,
                'Информационные': 0,
                'Всего алертов': 0,
                'Рекомендации': f"Ошибка анализа: {str(e)[:50]}..."
            })

    return pd.DataFrame(results)


def show_alert_settings():
    """Настройка параметров алертов"""
    with st.expander("⚙️ **Настройка правил алертов**", expanded=True):
        st.markdown("### Пороговые значения")

        col1, col2, col3 = st.columns(3)

        with col1:
            st.markdown("**Загруженность**")
            cpu_high = st.number_input(
                "CPU > (%)",
                min_value=0,
                max_value=100,
                value=85,
                key="cpu_high_threshold"
            )

            mem_high = st.number_input(
                "Память > (%)",
                min_value=0,
                max_value=100,
                value=80,
                key="mem_high_threshold"
            )

            cpu_ready = st.number_input(
                "CPU Ready > (%)",
                min_value=0,
                max_value=100,
                value=10,
                key="cpu_ready_threshold"
            )

        with col2:
            st.markdown("**Простой**")
            cpu_low = st.number_input(
                "CPU < (%)",
                min_value=0,
                max_value=100,
                value=15,
                key="cpu_low_threshold"
            )

            mem_low = st.number_input(
                "Память < (%)",
                min_value=0,
                max_value=100,
                value=25,
                key="mem_low_threshold"
            )

            net_low = st.number_input(
                "Сеть < (%)",
                min_value=0,
                max_value=100,
                value=5,
                key="net_low_threshold"
            )

        with col3:
            st.markdown("**Норма**")
            cpu_min = st.number_input(
                "CPU мин (%)",
                min_value=0,
                max_value=100,
                value=15,
                key="cpu_min_normal"
            )

            cpu_max = st.number_input(
                "CPU макс (%)",
                min_value=0,
                max_value=100,
                value=85,
                key="cpu_max_normal"
            )

            disk_latency = st.number_input(
                "Задержка диска > (ms)",
                min_value=0,
                max_value=100,
                value=25,
                key="disk_latency_threshold"
            )

        # Временные параметры
        st.markdown("### Временные параметры")
        col_time1, col_time2 = st.columns(2)

        with col_time1:
            time_overload = st.slider(
                "Время для перегрузки (%)",
                min_value=0,
                max_value=100,
                value=20,
                key="time_overload"
            ) / 100

        with col_time2:
            time_underload = st.slider(
                "Время для простоя (%)",
                min_value=0,
                max_value=100,
                value=80,
                key="time_underload"
            ) / 100

        # Кнопки
        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            if st.button("💾 Сохранить настройки", use_container_width=True):
                try:
                    # Обновляем правила в системе
                    alert_system.update_rule("high_cpu_usage", thresholds={'high': cpu_high})
                    alert_system.update_rule("high_memory_usage", thresholds={'high': mem_high})
                    alert_system.update_rule("cpu_ready_time", thresholds={'high': cpu_ready})
                    alert_system.update_rule("low_cpu_usage", thresholds={'low': cpu_low})
                    alert_system.update_rule("low_memory_usage", thresholds={'low': mem_low})
                    alert_system.update_rule("low_network_usage", thresholds={'low': net_low})
                    alert_system.update_rule("normal_cpu_range", thresholds={'low': cpu_min, 'high': cpu_max})
                    alert_system.update_rule("high_disk_latency", thresholds={'high': disk_latency})

                    # Обновляем временные параметры
                    alert_system.update_rule("high_cpu_usage", time_percentage=time_overload)
                    alert_system.update_rule("high_memory_usage", time_percentage=time_overload)
                    alert_system.update_rule("cpu_ready_time", time_percentage=time_overload)
                    alert_system.update_rule("low_cpu_usage", time_percentage=time_underload)
                    alert_system.update_rule("low_memory_usage", time_percentage=time_underload)
                    alert_system.update_rule("low_network_usage", time_percentage=time_underload)

                    st.success("Настройки сохранены!")
                except Exception as e:
                    st.error(f"Ошибка при сохранении: {e}")

        with col_btn2:
            if st.button("🔄 Сбросить к default", use_container_width=True):
                try:
                    # Сбрасываем значения через интерфейс
                    st.session_state.cpu_high_threshold = 85
                    st.session_state.mem_high_threshold = 80
                    st.session_state.cpu_ready_threshold = 10
                    st.session_state.cpu_low_threshold = 15
                    st.session_state.mem_low_threshold = 25
                    st.session_state.net_low_threshold = 5
                    st.session_state.cpu_min_normal = 15
                    st.session_state.cpu_max_normal = 85
                    st.session_state.disk_latency_threshold = 25
                    st.session_state.time_overload = 20
                    st.session_state.time_underload = 80

                    st.success("Настройки сброшены к значениям по умолчанию!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Ошибка при сбросе: {e}")


def show_summary_statistics(results_df):
    """Показать сводную статистику по всем серверам"""
    if results_df.empty:
        return

    total_servers = len(results_df)
    overloaded = len(results_df[results_df['Статус'].str.contains('ПЕРЕГРУЗКА')])
    underloaded = len(results_df[results_df['Статус'].str.contains('ПРОСТОЙ')])
    normal = len(results_df[results_df['Статус'].str.contains('НОРМА')])

    st.markdown("### 📊 Сводная статистика")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Всего серверов", total_servers)
    with col2:
        st.metric("Нормальная работа", normal)
    with col3:
        st.metric("Перегружено", overloaded,
                  delta=f"{(overloaded / total_servers * 100):.1f}%" if total_servers > 0 else "0%")
    with col4:
        st.metric("Простаивает", underloaded,
                  delta=f"{(underloaded / total_servers * 100):.1f}%" if total_servers > 0 else "0%")


def show():
    """Страница фактических данных"""

    # Красивое отображение правил алертов
    with st.expander("**Правила анализа загруженности серверов**", expanded=False):
        st.markdown("#### Загруженный сервер")
        st.markdown(
            "**Критерий:** Более **20% времени** (из 336 интервалов) **хотя бы одна** метрика превышает пороги:")

        st.markdown("""
| Метрика | Порог | Источник данных |
|---------|-------|-----------------|
|Среднее использование CPU | **>85%** | `cpu.usage.average` |
|Среднее использование памяти | **>80%** | `mem.usage.average` |
|CPU Ready Time (в топ-20% пиковых интервалов) | **>10%** | `cpu.ready.summation` |
        """)

        st.markdown("#### Простаивающий сервер")
        st.markdown("**Критерий:** Более **80% времени** **все** метрики ниже порогов:")
        st.markdown("""
| Метрика | Порог | Источник данных |
|---------|-------|-----------------|
|Среднее использование CPU | **<15%** | `cpu.usage.average` |
|Среднее использование памяти | **<25%** | `mem.usage.average` |
|Среднее использование сети | **<5%** | `net.usage.average` |
        """)

        st.markdown("#### Нормальная работа сервера")
        st.markdown("**Оптимизированная настройка ресурсов:** **Все** метрики входят в оптимальные диапазоны:")
        st.markdown("""
| Метрика | Оптимальный диапазон | Источник данных |
|---------|----------------------|-----------------|
| Среднее использование CPU | **15–85%** | `cpu.usage.average` |
| Среднее использование памяти | **25–85%** | `mem.usage.average` |
| Среднее использование сети | **6–85%** | `net.usage.average` |
        """)

    # Показываем настройки алертов
    show_alert_settings()

    try:
        # Загружаем список серверов
        servers = load_all_servers()

        if not servers:
            st.warning("⚠️ Серверы не найдены в базе данных. Пожалуйста, убедитесь, что данные загружены.")
            st.info("💡 Используйте API или утилиты для загрузки данных в базу.")
            return

        st.markdown("### 📅 Выбор периода анализа")

        # Загружаем данные для определения диапазона дат
        initial_df = load_data_from_db()

        if initial_df.empty:
            st.warning("⚠️ В базе данных нет данных для анализа")
            return

        # Выбор дат
        min_date = pd.to_datetime(initial_df['timestamp']).min().date()
        max_date = pd.to_datetime(initial_df['timestamp']).max().date()

        col_date1, col_date2, col_btn = st.columns([1, 1, 2])
        with col_date1:
            start_date = st.date_input(
                "**Начальная дата:**",
                min_date,
                min_value=min_date,
                max_value=max_date,
                key="fact_start"
            )

        with col_date2:
            end_date = st.date_input(
                "**Конечная дата:**",
                max_date,
                min_value=min_date,
                max_value=max_date,
                key="fact_end"
            )

        with col_btn:
            analyze_btn = st.button(
                "🔍 Проанализировать все серверы",
                type="primary",
                use_container_width=True,
                key="analyze_all_servers"
            )

            if st.button(
                    "🔄 Обновить данные",
                    use_container_width=True,
                    key="refresh_all_data"
            ):
                load_data_from_db.clear()
                st.rerun()

        # Загружаем данные для выбранного диапазона дат
        if analyze_btn or 'fact_start' not in st.session_state:
            start_datetime = datetime.combine(start_date, datetime.min.time())
            end_datetime = datetime.combine(end_date, datetime.max.time())

            with st.spinner(f"📥 Загрузка данных за период с {start_date} по {end_date}..."):
                filtered_df = load_data_from_db(
                    start_date=start_datetime,
                    end_date=end_datetime
                )

            if not filtered_df.empty:
                with st.spinner("🔬 Анализ всех серверов..."):
                    results_df = analyze_all_servers(filtered_df)

                    if not results_df.empty:
                        # Показываем сводную статистику
                        show_summary_statistics(results_df)

                        st.markdown("### 📋 Результаты анализа серверов")

                        # Сортируем по статусу для удобства просмотра
                        status_order = {
                            "🟥 ПЕРЕГРУЗКА": 0,
                            "🟨 ПРОСТОЙ": 1,
                            "🟩 НОРМА": 2,
                            "⚪ НЕТ ДАННЫХ": 3,
                            "⚪ ОШИБКА АНАЛИЗА": 4
                        }

                        results_df['status_order'] = results_df['Статус'].map(status_order)
                        results_df = results_df.sort_values('status_order')
                        results_df = results_df.drop('status_order', axis=1)

                        # Отображаем таблицу с цветовым кодированием
                        st.dataframe(
                            results_df,
                            use_container_width=True,
                            hide_index=True,
                            column_config={
                                "Сервер": st.column_config.TextColumn("Сервер", width="medium"),
                                "Статус": st.column_config.TextColumn("Статус", width="small"),
                                "CPU (%)": st.column_config.ProgressColumn(
                                    "CPU (%)",
                                    help="Средняя загрузка CPU",
                                    format="%s%%",
                                    min_value=0,
                                    max_value=100,
                                    width="small"
                                ),
                                "Память (%)": st.column_config.ProgressColumn(
                                    "Память (%)",
                                    help="Средняя загрузка памяти",
                                    format="%s%%",
                                    min_value=0,
                                    max_value=100,
                                    width="small"
                                ),
                                "Сеть (%)": st.column_config.ProgressColumn(
                                    "Сеть (%)",
                                    help="Средняя загрузка сети",
                                    format="%s%%",
                                    min_value=0,
                                    max_value=100,
                                    width="small"
                                ),
                                "Рекомендации": st.column_config.TextColumn(
                                    "Рекомендации",
                                    width="large"
                                )
                            }
                        )

                        # Детальные рекомендации для каждого типа серверов
                        st.markdown("### 💡 Детальные рекомендации")

                        # Рекомендации для перегруженных серверов
                        overloaded_servers = results_df[results_df['Статус'].str.contains('ПЕРЕГРУЗКА')]
                        if not overloaded_servers.empty:
                            with st.expander(f"🟥 **Перегруженные серверы ({len(overloaded_servers)})**",
                                             expanded=False):
                                st.markdown("**Основные рекомендации:**")
                                st.markdown("""
                                1. **Увеличить ресурсы** - добавить CPU и память
                                2. **Оптимизировать нагрузку** - распределить задачи
                                3. **Масштабировать горизонтально** - добавить реплики
                                4. **Оптимизировать код/запросы** - снизить ресурсопотребление
                                """)

                                for _, server in overloaded_servers.iterrows():
                                    st.markdown(f"**{server['Сервер']}:** {server['Рекомендации']}")

                        # Рекомендации для простаивающих серверов
                        underloaded_servers = results_df[results_df['Статус'].str.contains('ПРОСТОЙ')]
                        if not underloaded_servers.empty:
                            with st.expander(f"🟨 **Простаивающие серверы ({len(underloaded_servers)})**",
                                             expanded=False):
                                st.markdown("**Основные рекомендации:**")
                                st.markdown("""
                                1. **Уменьшить ресурсы** - снизить выделенные CPU/память
                                2. **Консолидировать нагрузки** - перенести сервисы
                                3. **Перевести в режим энергосбережения**
                                4. **Рассмотреть возможность отключения**
                                """)

                                for _, server in underloaded_servers.iterrows():
                                    st.markdown(f"**{server['Сервер']}:** {server['Рекомендации']}")

                        # Статистика по алертам
                        total_alerts = results_df['Всего алертов'].sum()
                        critical_alerts = results_df['Критические алерты'].sum()

                        if total_alerts > 0:
                            st.markdown("### ⚠️ Сводка по алертам")

                            col_alert1, col_alert2, col_alert3 = st.columns(3)
                            with col_alert1:
                                st.metric("Всего алертов", total_alerts)
                            with col_alert2:
                                st.metric("Критические", critical_alerts,
                                          delta=f"{(critical_alerts / total_alerts * 100):.1f}%" if total_alerts > 0 else "0%")
                            with col_alert3:
                                st.metric("Серверов с алертами",
                                          len(results_df[results_df['Всего алертов'] > 0]))

                        # Экспорт результатов
                        st.markdown("### 📥 Экспорт результатов")

                        col_exp1, col_exp2 = st.columns(2)

                        with col_exp1:
                            # CSV экспорт
                            csv = results_df.to_csv(index=False, sep=';', encoding='utf-8-sig')
                            st.download_button(
                                label="📄 Скачать CSV",
                                data=csv,
                                file_name=f"server_analysis_{start_date}_{end_date}.csv",
                                mime="text/csv",
                                use_container_width=True
                            )

                        with col_exp2:
                            # JSON экспорт
                            json_data = results_df.to_json(orient='records', force_ascii=False, indent=2)
                            st.download_button(
                                label="📊 Скачать JSON",
                                data=json_data,
                                file_name=f"server_analysis_{start_date}_{end_date}.json",
                                mime="application/json",
                                use_container_width=True
                            )
                    else:
                        st.warning("Не удалось проанализировать данные серверов")
            else:
                st.info(f"📭 Нет данных за выбранный период ({start_date} - {end_date})")

    except Exception as e:
        st.error(f"Ошибка при загрузке данных: {e}")
        import traceback
        with st.expander("Детали ошибки"):
            st.code(traceback.format_exc())
        st.info("💡 Убедитесь, что база данных доступна и содержит данные.")
