import streamlit as st

pg = st.navigation([st.Page('tracks_load_page.py', title='Загрузка треков'),
                    st.Page('tracks_viewing_page.py', title='Просмотр существующих треков')])
pg.run()