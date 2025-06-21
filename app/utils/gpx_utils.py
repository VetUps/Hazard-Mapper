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

    # Вычисляем характеристики трека
    stats = {
        'total_distance': total_distance,
        'avg_elevation': np.mean(elevations) if elevations else 0,
        'min_elevation': min(elevations) if elevations else 0,
        'max_elevation': max(elevations) if elevations else 0,
        'start_time': min(times) if times else None,
        'end_time': max(times) if times else None
    }

    # Возвращаем список точек и характеристики трека
    return points, stats


def generate_track_image(points: List[dict]) -> bytes:
    """
    Генерация топографической карты с наложенным на неё треком
    :param points: точки трека
    :return: карта в виде байтов
    """
    # Координаты трека в формате (longitude, latitude)
    coordinates = [(point['longitude'], point['latitude']) for point in points]

    # Создаем GeoDataFrame для трека
    geometry = LineString(coordinates)
    gdf = gpd.GeoDataFrame(geometry=[geometry], crs="EPSG:4326")  # WGS84

    # Преобразуем координаты в Web Mercator (для совместимости с тайлами)
    gdf = gdf.to_crs(epsg=3857)

    # Создаем область карты на основе трека
    ax = gdf.plot(figsize=(10, 10), color="red", linewidth=3)

    # Добавляем топографическую подложку (OpenTopoMap)
    ctx.add_basemap(
        ax,
        source=ctx.providers.OpenTopoMap,
        zoom=14  # Масштаб (подберите под ваш трек)
    )

    # Убираем оси
    ax.set_axis_off()

    buffer = io.BytesIO()
    plt.savefig(buffer, format='png', bbox_inches='tight')
    plt.close()

    return buffer.getvalue()

def get_track_region(points: List[dict]) -> str | None:
    """
        Определение региона с использованием библиотеки geocoder
        :param points: точки трека
        :return: Название региона
    """
    # Получение первой точки трека
    first_point = points[0]
    # Определение региона по этой точке
    g = geocoder.osm((first_point['latitude'], first_point['longitude']), method='reverse')
    if g.ok:
        return g.get('state') or g.get('region') or g.get('autonomous_okrug')
    return None
