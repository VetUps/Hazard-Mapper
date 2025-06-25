from typing import List, Any

from sqlalchemy.orm import Session, joinedload
from app import models, schemas
from app.utils import gpx_utils
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# User CRUD-ы
def get_user(db: Session, user_id: int):
    return db.query(models.User).filter(models.User.id == user_id).first()

def get_all_users(db: Session, skip: int = 0, limit: int = 100, user_id: int = None):
    if user_id:
        return db.query(models.User).filter(models.User.id != user_id).all()
    return db.query(models.User).offset(skip).limit(limit).all()

def get_user_by_email(db: Session, email: str):
    return db.query(models.User).filter(models.User.email == email).first()

def get_user_by_username(db: Session, username: str):
    return db.query(models.User).filter(models.User.username == username).first()

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

def update_user(db: Session, user_data: schemas.UserUpdate, current_user: models.User):
    if user_data.username:
        current_user.username = user_data.username
    if user_data.email:
        current_user.email = user_data.email
    if user_data.password:
        hashed_password = pwd_context.hash(user_data.password)
        current_user.password_hash = hashed_password

    db.commit()
    db.refresh(current_user)
    return current_user

def update_user_active(db: Session, user_id: int, is_active: bool):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if user:
        user.is_active = is_active
        db.commit()
        db.refresh(user)
    return user

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


def update_track(db: Session, track_id: int, track_data: schemas.TrackUpdate):
    db_track = db.query(models.Track).filter(models.Track.id == track_id).first()

    if not db_track:
        return None

    if track_data.title:
        db_track.title = track_data.title
    if track_data.description is not None:
        db_track.description = track_data.description

    db.commit()
    db.refresh(db_track)
    return db_track

def get_tracks(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.Track).offset(skip).limit(limit).all()

def get_tracks_by_user(db: Session, user_id: int, skip: int = 0, limit: int = 100):
    return db.query(models.Track).filter(models.Track.user_id == user_id).offset(skip).limit(limit).all()


def create_track_with_points(
        db: Session,
        track_data: schemas.TrackCreate,
        points: list,
        image: bytes,
        user_id: int
):
    db_track = models.Track(
        title=track_data.title,
        region=track_data.region,
        description=track_data.description,
        total_distance=track_data.total_distance,
        elevation_gain=track_data.elevation_gain,
        difficulty=track_data.difficulty,
        user_id=user_id
    )
    db.add(db_track)
    db.commit()
    db.refresh(db_track)

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
            joinedload(models.Track.owner),
            joinedload(models.Track.comments).joinedload(models.Comment.author)
        ).filter(models.Track.id == track_id).first()

def delete_track(db: Session, track_id: int):
    track = get_track(db, track_id)
    db.delete(track)
    db.commit()
    return {"message":"Успех"}


# Избранное CRUD-ы
def add_to_favorites(db: Session, user_id: int, track_id: int):
    # Проверяем, не добавлен ли уже трек
    existing_fav = db.query(models.Favorite).filter(
        models.Favorite.user_id == user_id,
        models.Favorite.track_id == track_id
    ).first()

    if existing_fav:
        return existing_fav

    fav = models.Favorite(user_id=user_id, track_id=track_id)
    db.add(fav)
    db.commit()
    db.refresh(fav)
    return fav

def remove_from_favorites(db: Session, user_id: int, track_id: int):
    fav = db.query(models.Favorite).filter(
        models.Favorite.user_id == user_id,
        models.Favorite.track_id == track_id
    ).first()

    if fav:
        db.delete(fav)
        db.commit()
        return True
    return False

def get_favorite_tracks(db: Session, user_id: int, skip: int = 0, limit: int = 100):
    return db.query(models.Track).join(models.Favorite).filter(
        models.Favorite.user_id == user_id
    ).offset(skip).limit(limit).all()

def is_favorite(db: Session, user_id: int, track_id: int):
    return db.query(models.Favorite).filter(
        models.Favorite.user_id == user_id,
        models.Favorite.track_id == track_id
    ).first() is not None

# Комментарии CRUD-ы
def create_comment(db: Session, comment_data: schemas.CommentCreate, user_id: int, track_id: int):
    db_comment = models.Comment(
        content=comment_data.content,
        user_id=user_id,
        track_id=track_id
    )

    db.add(db_comment)
    db.commit()
    db.refresh(db_comment)
    return db_comment