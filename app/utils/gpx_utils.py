from typing import Tuple, List
import gpxpy
import gpxpy.gpx
import numpy as np
import pandas as pd
import geopandas as gpd
import contextily as ctx
from shapely.geometry import LineString
import matplotlib.pyplot as plt
import io
import geocoder
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas


def calculate_difficulty(distance_km, elevation_gain):
    """
    Рассчитывает сложность трека по шкале 1-5
    :param distance_km: общая длина трека
    :param elevation_gain: общий набор высоты на всём треке
    :return: число от 1 до 5
    """
    # Коэффициенты для расчета
    distance_factor = distance_km / 20  # 20 км = сложность 1
    elevation_factor = elevation_gain / 1000  # 1000м набора = сложность 1

    # Формула сложности (можно настроить)
    raw_score = distance_factor + elevation_factor * 1.5

    # Ограничиваем от 1 до 5
    difficulty = max(1, min(5, round(raw_score)))
    return difficulty

def parse_gpx(gpx_content: str) -> Tuple[List[dict], dict]:
    """
    Парсит .gpx контент
    :param gpx_content: .gpx контент, получаемый из файла
    :return: список точек (словарей) и характеристики трека
    """
    # Парсим трек
    gpx = gpxpy.parse(gpx_content)
    # Определяем списки с данными о треке
    points = []
    elevations = []
    times = []
    total_distance = 0.0

    # Проходимся по каждому треку
    for track in gpx.tracks:
        # По каждому сегменту
        for segment in track.segments:
            # Запоминаем прошлую точку
            prev_point = None
            # По каждой точке
            for point in segment.points:
                # Записываем в список точек параметры текущей
                points.append({
                    'latitude': point.latitude,
                    'longitude': point.longitude,
                    'elevation': point.elevation,
                    'time': point.time
                })

                # Если высота точки определена, то записываем высоту в список
                if point.elevation is not None:
                    elevations.append(point.elevation)

                # То же самое с временем
                if point.time:
                    times.append(point.time)

                # Если есть предыдущая точка, то измеряем расстояние до неё
                if prev_point:
                    total_distance += point.distance_2d(prev_point)
                prev_point = point

    # Рассчитываем набор высоты
    elevation_gain = 0
    prev_elevation = None
    elevations = []
    for point in points:
        if point['elevation'] is not None:
            elevations.append(point['elevation'])
            if prev_elevation is not None and point['elevation'] > prev_elevation:
                elevation_gain += point['elevation'] - prev_elevation
            prev_elevation = point['elevation']

    # Рассчитываем сложность
    distance_km = total_distance / 1000
    difficulty = calculate_difficulty(distance_km, elevation_gain)

    # Вычисляем характеристики трека
    stats = {
        'total_distance': total_distance,
        'elevation_gain': elevation_gain,
        'difficulty': difficulty,
        'avg_elevation': np.mean(elevations) if elevations else 0,
        'min_elevation': min(elevations) if elevations else 0,
        'max_elevation': max(elevations) if elevations else 0,
        'start_time': min(times) if times else None,
        'end_time': max(times) if times else None
    }

    # Возвращаем список точек и характеристики трека
    return points, stats

def generate_track_image(points: List[dict]) -> bytes:
    # Параметры изображения
    TARGET_WIDTH = 2000  # Ширина в пикселях
    TARGET_DPI = 300  # Качество вывода

    # Ваши координаты трека
    coordinates = [(point['longitude'], point['latitude']) for point in points]

    # Создаем GeoDataFrame
    geometry = LineString(coordinates)
    gdf = gpd.GeoDataFrame(geometry=[geometry], crs="EPSG:4326")
    gdf_web = gdf.to_crs(epsg=3857)

    # Рассчитываем границы и соотношение сторон
    minx, miny, maxx, maxy = gdf_web.total_bounds
    dx, dy = maxx - minx, maxy - miny
    aspect_ratio = dx / dy

    # Вычисляем размеры в пикселях
    width_in = TARGET_WIDTH / TARGET_DPI
    height_in = width_in / aspect_ratio

    # Создаем фигуру с точным контролем размеров
    fig = plt.figure(figsize=(width_in, height_in), dpi=TARGET_DPI)
    ax = fig.add_subplot(111)
    ax.set_axis_off()

    # Устанавливаем границы с отступом 5%
    padding = 0.05
    ax.set_xlim(minx - dx * padding, maxx + dx * padding)
    ax.set_ylim(miny - dy * padding, maxy + dy * padding)

    # Добавляем подложку высокого качества
    ctx.add_basemap(
        ax,
        source=ctx.providers.OpenTopoMap,
        crs=gdf_web.crs.to_string(),
        zoom='auto',
        reset_extent=False,
        interpolation='lanczos'
    )

    # Рисуем трек с правильными параметрами стиля
    line = gdf_web.geometry.iloc[0]

    # Для LineString
    if line.geom_type == 'LineString':
        x, y = line.xy
        ax.plot(
            x, y,
            color='red',
            linewidth=4,
            solid_capstyle='round',  # Скругленные концы
            solid_joinstyle='round',  # Скругленные углы
            antialiased=True
        )
    # Для MultiLineString
    elif line.geom_type == 'MultiLineString':
        for segment in line:
            x, y = segment.xy
            ax.plot(
                x, y,
                color='red',
                linewidth=4,
                solid_capstyle='round',
                solid_joinstyle='round',
                antialiased=True
            )

    # Генерируем изображение без сжатия
    canvas = FigureCanvas(fig)
    buf = io.BytesIO()
    canvas.print_figure(
        buf,
        format='png',
        dpi=TARGET_DPI,
        bbox_inches='tight',
        pad_inches=0,
        facecolor='white',
    )
    plt.close(fig)

    # Получаем бинарные данные
    image_data = buf.getvalue()
    buf.close()

    return image_data


def get_track_region(points: List[dict]) -> str | None:
    """
    Определение региона с использованием ArcGIS
    :param points: точки трека
    :return: Название региона или None
    """
    # Если точек не будет, то вернём None
    if not points:
        return None

    # Достаём первую точку трека
    first_point = points[0]
    lat, lng = first_point['latitude'], first_point['longitude']

    # Обратное геокодирование
    g = geocoder.arcgis(
        (lat, lng),
        method='reverse',
        lang='ru',
        timeout=10
    )

    # Если что-то пошло не так, тоже вернём None
    if not g.ok:
        return None

    # Извлекаем регион из сырых данных
    if g.raw and 'address' in g.raw:
        address = g.raw['address']
        # Пробуем разные ключи для региона
        return (
                address.get('Region')
                or address.get('Subregion')
                or address.get('State')
        )

    # Если не сработает прошлый вариант
    return (
            getattr(g, 'region', None)
            or getattr(g, 'state', None)
    )
