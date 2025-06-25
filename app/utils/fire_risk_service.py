import os
import glob
import pandas as pd
import numpy as np
from scipy.spatial import KDTree
import folium
import logging
from datetime import datetime
from app.database import get_db
from app import crud

# Настройка логгирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Конфигурация
FIRE_DATA_DIR = "app/fire_data"
SEARCH_RADIUS = 0.05  # Радиус поиска пожаров в градусах (~5.5 км)


def load_fire_data():
    logger.info("Загрузка данных о пожарах...")
    fire_dfs = []
    years = list(range(datetime.now().year - 1, 2014, -1))

    for year in years:
        for file in glob.glob(os.path.join(FIRE_DATA_DIR, f"*{year}*.csv")):
            try:
                df = pd.read_csv(file, low_memory=False)
                df = df.rename(columns={'bright_ti4': 'brightness', 'acq_date': 'date'})

                # Векторизованное преобразование типов
                for col in ['latitude', 'longitude', 'brightness', 'frp']:
                    if col in df:
                        df[col] = pd.to_numeric(df[col], errors='coerce')

                # Фильтрация и преобразование даты
                df = df.dropna(subset=['latitude', 'longitude', 'brightness', 'frp'])
                df['date'] = pd.to_datetime(df['date'], errors='coerce')
                df = df.dropna(subset=['date'])

                if not df.empty:
                    df['year'] = year
                    fire_dfs.append(df)
                    logger.info(f"Загружен {file}: {len(df)} записей")

            except Exception as e:
                logger.error(f"Ошибка чтения {file}: {str(e)}")

    if not fire_dfs:
        raise ValueError("Не удалось загрузить данные о пожарах")

    return pd.concat(fire_dfs, ignore_index=True)


def calculate_fire_risk(track_points):
    """Расчет пожароопасности для точек трека"""
    fire_data = load_fire_data()
    fire_coords = fire_data[['latitude', 'longitude']].values
    fire_tree = KDTree(fire_coords)
    risks = np.zeros(len(track_points))

    for i, point in enumerate(track_points):
        point_coord = [point.latitude, point.longitude]
        indices = fire_tree.query_ball_point(point_coord, r=SEARCH_RADIUS)

        if not indices:
            continue

        nearby = fire_data.iloc[indices]
        distances = np.linalg.norm(nearby[['latitude', 'longitude']].values - point_coord, axis=1)

        # Расчет факторов риска
        count_factor = min(len(nearby) / 20, 1.0)
        intensity_factor = nearby['frp'].mean() / 50
        brightness_factor = (nearby['brightness'].mean() - 300) / 200
        proximity_factor = (SEARCH_RADIUS - distances.min()) / SEARCH_RADIUS

        # Комбинированный риск
        risk_score = (
                0.4 * count_factor +
                0.3 * intensity_factor +
                0.2 * brightness_factor +
                0.1 * proximity_factor
        )
        risks[i] = np.clip(risk_score, 0.0, 1.0)

    return risks


def generate_risk_map(track_id: int, db):
    """Генерация карты с рисками для трека"""
    track = crud.get_track_with_details(db, track_id)
    if not track:
        raise ValueError("Трек не найден")

    points = [{"latitude": p.latitude, "longitude": p.longitude} for p in track.points]
    risks = calculate_fire_risk(track.points)

    # Создание карты
    map_center = [points[0]['latitude'], points[0]['longitude']]
    m = folium.Map(location=map_center, zoom_start=12)

    # Цветовая схема
    COLOR_SCALE = [
        (0.0, 'green'),
        (0.3, 'yellow'),
        (0.6, 'orange'),
        (0.8, 'red')
    ]

    # Добавление трека
    folium.PolyLine(
        [[p['latitude'], p['longitude']] for p in points],
        color='blue',
        weight=3
    ).add_to(m)

    # Добавление маркеров риска
    for point, risk in zip(points, risks):
        color = next(c for t, c in reversed(COLOR_SCALE) if risk >= t)
        folium.CircleMarker(
            location=[point['latitude'], point['longitude']],
            radius=6,
            color=color,
            fill=True,
            fill_opacity=0.8,
            popup=f"Риск: {risk:.2f}"
        ).add_to(m)

    # Маркеры начала/конца
    folium.Marker(
        [points[0]['latitude'], points[0]['longitude']],
        icon=folium.Icon(icon='play', color='green'),
        popup='Начало'
    ).add_to(m)

    folium.Marker(
        [points[-1]['latitude'], points[-1]['longitude']],
        icon=folium.Icon(icon='flag', color='red'),
        popup='Конец'
    ).add_to(m)

    # Легенда
    legend_html = '''
    <div style="position:fixed; bottom:50px; left:50px; background:white; padding:10px; border:2px solid grey; z-index:1000;">
        <b>Уровень риска:</b><br>
        <i style="background:green; width:20px; height:20px; display:inline-block;"></i> Низкий (0-0.3)<br>
        <i style="background:yellow; width:20px; height:20px; display:inline-block;"></i> Умеренный (0.3-0.6)<br>
        <i style="background:orange; width:20px; height:20px; display:inline-block;"></i> Высокий (0.6-0.8)<br>
        <i style="background:red; width:20px; height:20px; display:inline-block;"></i> Экстремальный (0.8-1.0)
    </div>
    '''
    m.get_root().html.add_child(folium.Element(legend_html))

    # Возвращаем только HTML карты
    return m._repr_html_()