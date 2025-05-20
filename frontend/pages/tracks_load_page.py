# Импорты
import streamlit as st
import requests

# Запрос к API бля парсинга .gpx файла
def send_gpx():
    api_url = 'something right here'

    files = {'file': (uploaded_file.name, uploaded_file.getvalue(), 'application/gpx+xml')}
    result = requests.post(
        api_url,
        files=files
    )

    return result


# Заголовок страницы
st.title('Загрузка треков')

# Поле для выбора .gpx файлов
uploaded_file = st.file_uploader("Выберите GPX файл", type=['gpx'])

# Кнопка для построения карты трека
if st.button('Построить трек'):
    # Если файл выбран, отрпавляем запрос
    if uploaded_file is not None:
        try:
            # Отправляем запрос
            response = send_gpx()

            # Если код ответа 200 (т.е. успешно), то имитируем построение трека
            if response.status_code == 200:
                st.success("Трек успешно загружен")
                st.write("Ответ сервера:")
                st.json(response.json())
            # Иначе сообщаем об ошибке
            else:
                st.error(f"Ошибка при отправке файла: {response.status_code}")

        # Если не удаться отправить запрос, так же выводим ошибку
        except requests.exceptions.RequestException as e:
            st.error(f"Ошибка соединения с сервером: {e}")
    # Иначе просим пользователя выбрать файл
    else:
        st.warning("Пожалуйста, сначала выберите файл")