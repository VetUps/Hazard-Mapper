from fastapi import FastAPI, Depends, HTTPException, status, Response, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.params import Cookie, File, Form
from sqlalchemy.orm import Session
from starlette.responses import JSONResponse
from app.database import get_db, engine
from app import models, schemas, crud, security
from app.utils import gpx_utils
from datetime import timedelta
import base64
import os

# Инициализация API
app = FastAPI()

# Настройки
SESSION_EXPIRE_MINUTES = 60 * 24 * 7  # 7 дней

# CORS (для того, чтобы можно было отправлять запросы с браузера)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"], # Разрешает запросы только с указанных origins
    allow_credentials=True, # Разрешает передачу cookies
    allow_methods=["*"], # Разраешает все HTTP-методы (GET, POST и т.д.)
    allow_headers=["*"], # Разраешает все заголовки
)

# Создание таблиц
# models.Base.metadata.create_all(bind=engine)


@app.post("/register", response_model=schemas.User)
def register_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    """
    Эндпоинт для регистрации нового юзера по указанным данным
    :param user: Pydantic схема для валидации данных
    :param db: # Сессия с БД
    :return: Pydantic схема пользователя без пароля
    """
    db_user = crud.get_user_by_email(db, user.email)
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    return crud.create_user(db, user)


@app.post("/login")
async def login(
        response: Response,
        user: schemas.UserLogin,
        db: Session = Depends(get_db)
):
    """
    Эндпоинт для авторизации пользователя с установкой JWT токена в куки
    :param response: объект, создаваемый FastAPI для установки дополнительных параметров к ответу
    :param user: авторизовывающийся пользователь
    :param db: сессия с БД
    :return: response с дополнительным сообщением
    """
    # Проверка авторизации
    db_user = crud.authenticate_user(db, user.email, user.password)
    if not db_user:
        raise HTTPException(status_code=401, detail="Неверные данные")

    # Если авторизация удалась, то генерируем JWT токен
    session_token = security.create_session_token(
        data={"sub": str(db_user.id)},
        expires_delta=timedelta(minutes=SESSION_EXPIRE_MINUTES)
    )

    # Устанавливаем его в куки
    response.set_cookie(
        key="session_id",
        value=session_token,
        max_age=SESSION_EXPIRE_MINUTES * 60,
        httponly=True,
        secure=False,  # True in production
        samesite="lax",
    )

    # Возвращаем reponse
    return {"message": "Успешный вход"}


@app.post("/logout")
async def logout(response: Response):
    """
    Эндпоинт для выхода с аккаунта пользователя
    :param response: response: объект, создаваемый FastAPI для установки дополнительных параметров к ответу
    :return: response с дополнительным сообщением
    """
    # Отчищаем куки
    response.delete_cookie("session_id")
    # Возвращаем reponse
    return {"message": "Logout successful"}


@app.get("/users/me", response_model=schemas.User)
async def get_current_user(
        session_id: str = Cookie(lambda: None),
        db: Session = Depends(get_db)
):
    """
    Эндпоинт для получения текущего авторизованного пользователя
    :param session_id: название куки
    :param db: сессия с БД
    :return: пользователь без пароля
    """
    # Если куки не установлены, то вызваем ошибку
    if not session_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    # Иначе находим и возвращаем пользователя
    user_id = security.verify_session_token(session_id)
    user = crud.get_user(db, int(user_id))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@app.get("/protected")
async def protected_route(user: schemas.User = Depends(get_current_user)):
    return {"message": f"Hello {user.username}, this is protected!"}

@app.get("/tracks/load", response_model=schemas.TrackPaginate)
async def get_all_tracks(
        db: Session = Depends(get_db),
        skip: int = Query(0, ge=0, description="Количество пропускаемых записей"),
        limit: int = Query(10, le=100, description="Максимальное количество записей"),
):
    tracks = crud.get_tracks(db, skip=skip, limit=limit)
    total_tracks = db.query(models.Track).count()

    return {
        "tracks": tracks,
        "total": total_tracks,
        "skip": skip,
        "limit": limit
    }

@app.post("/tracks/upload")
async def upload_track(
    title: str = Form(...),
    description: str | None = Form(None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    # Проверка формата файла
    if not file.filename.endswith('.gpx'):
        raise HTTPException(400, "Invalid file format. Only GPX files are accepted.")

    # Чтение и парсинг GPX
    contents = await file.read()
    points, stats = gpx_utils.parse_gpx(contents.decode('utf-8'))

    # Генерация изображения
    image = gpx_utils.generate_track_image(points)
    region = gpx_utils.get_track_region(points)

    track_data_for_create = schemas.TrackCreate(
        title=title,
        description=description,
        region=region,
    )

    track = crud.create_track_with_points(
        db,
        track_data_for_create,
        points,
        image,
        current_user.id
    )

    image_base64 = base64.b64encode(image).decode('utf-8')

    return {
        "track": track,
        "points": points,
        "stats": stats
    }

@app.get("/tracks/{track_id}", response_model=schemas.TrackDetail)
def get_track_details(track_id: int, db: Session = Depends(get_db)):
    track = crud.get_track_with_details(db, track_id)
    if not track:
        raise HTTPException(404, "Трек не найден")
    return track
