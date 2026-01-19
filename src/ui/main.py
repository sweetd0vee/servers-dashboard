import os

import streamlit as st


# from assets.style import apply_custom_styles


# import os
# from dotenv import load_dotenv
# add to config DASHBOARD-BE_URL=http://127.0.0.1:8000

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
        base_dir = os.path.dirname(os.path.abspath(__file__))
        css_path = os.path.join(base_dir, "assets", "style.css")
        with open(css_path, encoding='utf-8') as f:
            css_content = f.read()
            st.markdown(f"<style>{css_content}</style>", unsafe_allow_html=True)
    except FileNotFoundError:
        st.error("CSS файл не найден. Проверьте путь к файлу.")
    except Exception as e:
        st.error(f"Ошибка при загрузке стилей: {e}")


# Применение стилей
apply_custom_styles()

from components.footer import show_footer

# Импорт компонентов
from components.header import show_header
from components.sidebar import show_sidebar


def main():
    # Отображение компонентов
    show_header()

    # Создание центрированных табов
    tab1, tab2, tab3, tab4 = st.tabs(["📈 Факт", "🔍 Сервер анализ", "🔧 АС анализ", "🔮 Прогноз"])

    # Импорт страниц
    from pages import analysis, as_analysis, fact, forecast

    # Вкладка 1: Факт
    # with tab1:
    #     fact.show()
    #
    # # Вкладка 2: Общий анализ по серверам
    # with tab2:
    #     analysis.show()
    #
    # # Вкладка 3: Анализ в срезе АС
    # with tab3:
    #     as_analysis.show()

    # Вкладка 4: Прогноз по АС
    with tab4:
        forecast.show()

    # Боковая панель
    with st.sidebar:
        show_sidebar()

    # Футер
    show_footer()


if __name__ == "__main__":
    main()
