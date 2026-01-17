from datetime import datetime

import streamlit as st


def show_sidebar():
    """Отображение боковой панели"""
    with st.sidebar:
        st.markdown("## ℹ️ **Информация**")

        # Метрики
        st.markdown("### 📈 Ключевые метрики")
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Серверов", "10", delta=None)
        with col2:
            st.metric("Активных", "10", delta=None)

        st.divider()

        # Навигация
        st.markdown("### 🧭 Навигация")
        st.markdown("""
        - **📈 Факт**: Исторические данные
        - **🔮 Прогноз**: Прогноз нагрузки
        - **📊 Анализ**: Общая аналитика
        """)

        st.divider()