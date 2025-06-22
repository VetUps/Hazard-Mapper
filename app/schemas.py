from typing import List

from fastapi import UploadFile
from fastapi.params import File, Form
from pydantic import BaseModel, EmailStr
from datetime import datetime, date

from app.models import TrackPoint


# Схемы пользователя
class UserBase(BaseModel):
    email: EmailStr
    username: str

class UserCreate(UserBase):
    password: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class User(UserBase):
    id: int
    is_active: bool
    created_at: datetime
    is_admin: bool

    class Config:
        orm_mode = True


# Схемы треков
class TrackBase(BaseModel):
    title: str
    region: str | None = None
    description: str | None = None
    total_distance: float
    elevation_gain: float
    difficulty: int

class TrackPointBase(BaseModel):
    point_index: int
    latitude: float
    longitude: float
    elevation: float | None = None
    point_time: datetime | None = None

class Track(TrackBase):
    id: int
    user_id: int
    created_at: datetime
    is_favorite: bool | None = None  # Будет заполнено только при запросе авторизованного пользователя

    class Config:
        orm_mode = True

class TrackCreate(TrackBase):
    pass

class TrackDetail(BaseModel):
    id: int
    user_id: int
    created_at: datetime
    points: List[TrackPointBase] = []
    image: str
    owner: User

    class Config:
        orm_mode = True

class TrackStats(BaseModel):
    total_distance: float
    avg_elevation: float
    min_elevation: float
    max_elevation: float

class TrackUpload(BaseModel):
    title: str = Form(...)
    description: str = Form(None)
    file: UploadFile = File(...)

class TrackPaginate(BaseModel):
    tracks: List[Track]
    total: int
    skip: int
    limit: int

class TrackPoint(TrackPointBase):
    id: int
    track_id: int

    class Config:
        orm_mode = True

# Схемы прогнозирования
class FireForecastBase(BaseModel):
    forecast_date: date
    temp: float | None = None
    humidity: float | None = None
    wind_speed: float | None = None
    ndvi: float | None = None
    evi: float | None = None
    psri: float | None = None
    ndwi: float | None = None
    msi: float | None = None
    danger_level: int

class FireForecastCreate(FireForecastBase):
    pass

class FireForecast(FireForecastBase):
    id: int
    track_id: int
    track_point_id: int
    calculated_at: datetime

    class Config:
        orm_mode = True


# Схемы комментариев
class CommentBase(BaseModel):
    content: str

class CommentCreate(CommentBase):
    pass

class Comment(CommentBase):
    id: int
    user_id: int
    track_id: int
    created_at: datetime

    class Config:
        orm_mode = True


# Схемы избранного
class FavoriteBase(BaseModel):
    track_id: int

class FavoriteCreate(FavoriteBase):
    pass

class Favorite(FavoriteBase):
    user_id: int
    created_at: datetime

    class Config:
        orm_mode = True