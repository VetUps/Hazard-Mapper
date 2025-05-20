import streamlit as st

# Определяем панель навигации по страницам
pg = st.navigation([st.Page('pages/tracks_load_page.py', title='Загрузка треков')])
# Запускаем главную страницу
pg.run()