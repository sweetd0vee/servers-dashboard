import asyncio
import concurrent.futures
import streamlit as st
from functools import partial


# Настройка страницы
st.set_page_config(
    page_title="Анализ нагрузки серверов",
    page_icon="",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Инициализация состояния сессии для аутентификации
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'user' not in st.session_state:
    st.session_state.user = None
if 'access_token' not in st.session_state:
    st.session_state.access_token = None
if 'role' not in st.session_state:
    st.session_state.role = None


def apply_custom_styles():
    """Применение кастомных стилей"""
    try:
        with open(r"C:\Users\audit\Work\Arina\Servers\dashboard\src\ui\assets\style.css", encoding='utf-8') as f:
            css_content = f.read()
            st.markdown(f"<style>{css_content}</style>", unsafe_allow_html=True)
    except FileNotFoundError:
        st.error("CSS файл не найден. Проверьте путь к файлу.")
    except Exception as e:
        st.error(f"Ошибка при загрузке стилей: {e}")


# Применение стилей
apply_custom_styles()

# Импорт компонентов
from components.header import show_header
from components.sidebar import show_sidebar
from components.footer import show_footer


def main():
    # Отображение компонентов
    show_header()

    # Создание центрированных табов
    tab1, tab2, tab3, tab4 = st.tabs(["📈 Факт", "🔍 Сервер анализ", "🔧 АС анализ", "🔮 Прогноз"])

    # Импорт страниц
    from pages import fact, forecast, analysis, as_analysis
    
    # Инициализация session_state для хранения результатов
    if 'tab_results' not in st.session_state:
        st.session_state.tab_results = {}
    
    # Функция для асинхронной загрузки данных вкладки
    async def load_tab_content(tab_name, tab_function):
        try:
            # Здесь можно асинхронно загружать тяжелые данные
            # или выполнять долгие вычисления
            result = await asyncio.to_thread(tab_function.show)
            st.session_state.tab_results[tab_name] = result
            return result
        except Exception as e:
            st.error(f"Ошибка при загрузке вкладки {tab_name}: {e}")
            return None
    
    # Создаем контейнеры для каждой вкладки заранее
    tab_containers = {
        'tab1': tab1.container(),
        'tab2': tab2.container(),
        'tab3': tab3.container(),
        'tab4': tab4.container()
    }

    # Загрузка данных для всех вкладок (можно кэшировать)
    @st.cache_resource(ttl=300)  # Кэшируем на 5 минут
    def load_all_tabs_data():
        """Предварительная загрузка данных для всех вкладок"""
        # Здесь можно предзагрузить общие данные для всех вкладок
        return {
            'common_data': 'some_common_data',
            'timestamp': '2024-01-01'
        }
    
    # Предзагрузка общих данных
    common_data = load_all_tabs_data()
    
    # Создаем пул потоков для параллельного выполнения тяжелых операций
    def execute_in_threadpool(func, *args):
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(func, *args)
            return future.result()

    # Вкладка 1: Факт
    with tab_containers['tab1']:
        # Используем спиннер во время загрузки
        with st.spinner('Загрузка данных по факту...'):
            # Если нужно параллельно выполнять тяжелые операции
            fact_data = execute_in_threadpool(fact.load_data)
            fact.show(fact_data)
    
    # Вкладка 2: Общий анализ по серверам
    with tab_containers['tab2']:
        with st.spinner('Загрузка анализа серверов...'):
            analysis_data = execute_in_threadpool(analysis.load_data)
            analysis.show(analysis_data)
    
    # Вкладка 3: Анализ в срезе АС
    with tab_containers['tab3']:
        with st.spinner('Загрузка анализа АС...'):
            as_data = execute_in_threadpool(as_analysis.load_data)
            as_analysis.show(as_data)
    
    # Вкладка 4: Прогноз по АС
    with tab_containers['tab4']:
        with st.spinner('Загрузка прогноза...'):
            forecast_data = execute_in_threadpool(forecast.load_data)
            forecast.show(forecast_data)

    # Боковая панель
    with st.sidebar:
        show_sidebar()

    # Футер
    show_footer()


# Альтернативная версия с использованием асинхронности
async def main_async():
    """Асинхронная версия main (требует async-совместимого окружения)"""
    
    # Создаем табы
    tab1, tab2, tab3, tab4 = st.tabs(["📈 Факт", "🔍 Сервер анализ", "🔧 АС анализ", "🔮 Прогноз"])
    
    # Импорт страниц
    from pages import fact, forecast, analysis, as_analysis
    
    # Создаем задачи для параллельной загрузки данных
    tasks = [
        asyncio.create_task(fact.load_data_async()),
        asyncio.create_task(analysis.load_data_async()),
        asyncio.create_task(as_analysis.load_data_async()),
        asyncio.create_task(forecast.load_data_async())
    ]
    
    # Ждем загрузки всех данных параллельно
    fact_data, analysis_data, as_data, forecast_data = await asyncio.gather(*tasks)
    
    # Отображаем вкладки с уже загруженными данными
    with tab1:
        fact.show(fact_data)
    
    with tab2:
        analysis.show(analysis_data)
    
    with tab3:
        as_analysis.show(as_data)
    
    with tab4:
        forecast.show(forecast_data)


# Для использования асинхронной версии в Streamlit нужна обертка
if __name__ == "__main__":
    # Обычная версия
    main()
    
    # Или асинхронная (если настроено async окружение)
    # import asyncio
    # asyncio.run(main_async())