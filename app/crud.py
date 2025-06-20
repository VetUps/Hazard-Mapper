from typing import List, Any

from sqlalchemy.orm import Session, joinedload
from app import models, schemas
from app.utils import gpx_utils
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# User CRUD-ы
def get_user(db: Session, user_id: int):
    return db.query(models.User).filter(models.User.id == user_id).first()

def get_user_by_email(db: Session, email: str):
    return db.query(models.User).filter(models.User.email == email).first()

def create_user(db: Session, user: schemas.UserCreate):
    hashed_password = pwd_context.hash(user.password)
    db_user = models.User(
        email=user.email,
        username=user.username,
        password_hash=hashed_password
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def authenticate_user(db: Session, email: str, password: str):
    user = get_user_by_email(db, email)
    if not user:
        return False
    if not pwd_context.verify(password, user.password_hash):
        return False
    return user

# Tracks CRUD-ы

def get_track(db: Session, track_id: int):
    return db.query(models.Track).filter(models.Track.id == track_id).first()

def get_tracks(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.Track).offset(skip).limit(limit).all()


def create_track_with_points(
        db: Session,
        track_data: schemas.TrackCreate,
        points: list,
        image: bytes,
        user_id: int
):
    # Создаем трек
    db_track = models.Track(
        title=track_data.title,
        region=track_data.region,
        description=track_data.description,
        user_id=user_id
    )
    db.add(db_track)
    db.commit()
    db.refresh(db_track)

    # Добавляем точки трека
    for i, point in enumerate(points):
        db_point = models.TrackPoint(
            track_id=db_track.id,
            point_index=i,
            latitude=point['latitude'],
            longitude=point['longitude'],
            elevation=point.get('elevation'),
            point_time=point.get('time')
        )
        db.add(db_point)

    # Добавляем изображение
    if image:
        db_image = models.TrackImage(
            track_id=db_track.id,
            image=image
        )
        db.add(db_image)

    db.commit()
    return db_track.id

def get_track_with_details(db: Session, track_id: int):
    return db.query(models.Track).\
        options(
            joinedload(models.Track.points),
            joinedload(models.Track.images),
            joinedload(models.Track.owner)
        ).filter(models.Track.id == track_id).first()