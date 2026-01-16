import streamlit as st


def apply_custom_styles():
    """Применение кастомных стилей"""
    with open("assets/style.css") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
