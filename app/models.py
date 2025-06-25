from sqlalchemy import Column, Integer, String, Text, Boolean, TIMESTAMP, ForeignKey, Date, Float
from sqlalchemy.orm import relationship
from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(TIMESTAMP, server_default="CURRENT_TIMESTAMP")
    is_admin = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)

    tracks = relationship("Track", back_populates="owner")
    comments = relationship("Comment", back_populates="author")


class Track(Base):
    __tablename__ = "tracks"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String(255), nullable=False)
    region = Column(String(255))
    description = Column(Text)
    total_distance = Column(Float, default=0.0)  # общая дистанция в метрах
    elevation_gain = Column(Float, default=0.0)  # суммарный набор высоты
    difficulty = Column(Integer, default=0)  # общая сложность 1-5
    created_at = Column(TIMESTAMP, server_default="CURRENT_TIMESTAMP")

    owner = relationship("User", back_populates="tracks")
    points = relationship("TrackPoint", back_populates="track", cascade="all, delete-orphan", passive_deletes=True)
    comments = relationship("Comment", back_populates="track", cascade="all, delete-orphan", passive_deletes=True)
    images = relationship("TrackImage", back_populates="track", cascade="all, delete-orphan", passive_deletes=True)


class TrackPoint(Base):
    __tablename__ = "track_points"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    track_id = Column(Integer, ForeignKey("tracks.id"), nullable=False)
    point_index = Column(Integer, nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    elevation = Column(Float)
    point_time = Column(TIMESTAMP)

    track = relationship("Track", back_populates="points")


class TrackImage(Base):
    __tablename__ = "track_images"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    track_id = Column(Integer, ForeignKey("tracks.id"), nullable=False)
    image = Column(Text)  # Храним base64 или путь к файлу
    created_at = Column(TIMESTAMP, server_default="CURRENT_TIMESTAMP")

    track = relationship("Track", back_populates="images")


class Comment(Base):
    __tablename__ = "comments"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    track_id = Column(Integer, ForeignKey("tracks.id"), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(TIMESTAMP, server_default="CURRENT_TIMESTAMP")

    author = relationship("User", back_populates="comments")
    track = relationship("Track", back_populates="comments")


class Favorite(Base):
    __tablename__ = "favorites"

    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    track_id = Column(Integer, ForeignKey("tracks.id", ondelete="CASCADE"), primary_key=True)
    created_at = Column(TIMESTAMP, server_default="CURRENT_TIMESTAMP")