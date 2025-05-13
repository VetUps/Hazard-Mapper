import streamlit as st
import requests

def send_gpx():
    api_url = 'something right here'

    files = {'file': (uploaded_file.name, uploaded_file.getvalue(), 'application/gpx+xml')}
    result = requests.post(
        api_url,
        files=files
    )

    return result


st.title('Загрузка треков')

uploaded_file = st.file_uploader("Выберите GPX файл", type=['gpx'])

if st.button('Построить трек'):
    if uploaded_file is not None:
        try:
            response = send_gpx()

            if response.status_code == 200:
                st.success("Трек успешно загружен")
                st.write("Ответ сервера:")
                st.json(response.json())
            else:
                st.error(f"Ошибка при отправке файла: {response.status_code}")

        except requests.exceptions.RequestException as e:
            st.error(f"Ошибка соединения с сервером: {e}")
    else:
        st.warning("Пожалуйста, сначала выберите файл")